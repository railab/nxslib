"""Module containing the NxScope handler."""

import queue
from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import time
from typing import TYPE_CHECKING, Any, Deque, Tuple

from nxslib.comm import CommHandler
from nxslib.logger import logger
from nxslib.proto.iparse import dsfmt_get
from nxslib.thread import ThreadCommon

if TYPE_CHECKING:
    from nxslib.dev import Device, DeviceChannel
    from nxslib.intf.iintf import ICommInterface
    from nxslib.proto.iparse import ICommParse


###############################################################################
# Data: DNxscopeStream
###############################################################################


@dataclass
class DNxscopeStream:
    """Stream data item."""

    data: tuple[Any, ...]
    meta: tuple[Any, ...]

    def __str__(self) -> str:
        """Human-readable stream item."""
        return str(self.data) + ", " + str(self.meta)

    def __repr__(self) -> str:
        """Represent stream item as string."""
        return str(self.data) + ", " + str(self.meta)


###############################################################################
# Data: DChannelState
###############################################################################


@dataclass(frozen=True)
class DChannelState:
    """Channels runtime state snapshot."""

    enabled_channels: tuple[int, ...]
    dividers: tuple[int, ...]


###############################################################################
# Data: DDeviceCapabilities
###############################################################################


@dataclass(frozen=True)
class DDeviceCapabilities:
    """Device capabilities snapshot."""

    chmax: int
    flags: int
    rxpadding: int
    div_supported: bool
    ack_supported: bool


###############################################################################
# Data: DStreamStats
###############################################################################


@dataclass(frozen=True)
class DStreamStats:
    """Stream runtime stats snapshot."""

    connected: bool
    stream_started: bool
    overflow_count: int
    bitrate: float


###############################################################################
# Class: _BitrateTracker
###############################################################################


class _BitrateTracker:
    """Helper for bitrate calculation with moving average."""

    def __init__(self, window_seconds: float = 5.0) -> None:
        """Initialize bitrate tracker.

        :param window_seconds: Time window for moving average
        """
        self.bytes_received: int = 0
        self.last_timestamp: float = 0.0
        self.samples: Deque[Tuple[float, int]] = deque()
        self.window_seconds: float = window_seconds
        self._lock = Lock()

    def update(self, bytes_count: int) -> None:
        """Update tracker with new byte count.

        :param bytes_count: Number of bytes received
        """
        with self._lock:
            now = time()
            self.bytes_received += bytes_count
            self.samples.append((now, bytes_count))

            # Remove samples older than window
            cutoff = now - self.window_seconds
            while self.samples and self.samples[0][0] < cutoff:
                self.samples.popleft()

            self.last_timestamp = now

    def get_bitrate(self) -> float:
        """Calculate current bitrate.

        :return: Bytes per second over the window period
        """
        with self._lock:
            if not self.samples:
                return 0.0

            now = time()
            oldest_time = self.samples[0][0]
            time_span = now - oldest_time

            if time_span < 0.1:  # Less than 100ms of data
                return 0.0

            total_bytes = sum(count for _, count in self.samples)
            return total_bytes / time_span


###############################################################################
# Class: NxscopeHandler
###############################################################################


class NxscopeHandler:
    """A class used to manage NxScope device."""

    def __init__(
        self,
        intf: "ICommInterface",
        parse: "ICommParse",
        enable_bitrate_tracking: bool = False,
        drop_timeout: float = 0.1,
        stream_data_timeout: float = 1.0,
    ) -> None:
        """Initialize the Nxslib handler.

        :param intf: Communication interface
        :param parse: Protocol parser
        :param enable_bitrate_tracking: Enable bitrate tracking
            (default: False)
        :param drop_timeout: timeout used in _drop_all_frames queue drains
        :param stream_data_timeout: timeout used in stream_data() frame wait
        """
        self._connected: bool = False
        self._comm = CommHandler(
            intf,
            parse,
            drop_timeout=drop_timeout,
            stream_data_timeout=stream_data_timeout,
        )

        self._thrd = ThreadCommon(self._stream_thread, name="stream")

        self._sub_q: list[list[queue.Queue[list[DNxscopeStream]]]] = []
        self._queue_lock: Lock = Lock()

        self._stream_started: bool = False

        self._ovf_cntr: int = 0
        self._stats_lock: Lock = Lock()
        self._bitrate_tracker: _BitrateTracker | None = (
            _BitrateTracker() if enable_bitrate_tracking else None
        )

    def __del__(self) -> None:
        """Make sure to disconnect from dev."""
        self.disconnect()  # pragma: no cover

    def _stream_start(self) -> bool:
        """Start stream request."""
        self._reset_stats()

        ret = self._comm.stream_start()
        if ret is None:  # pragma: no cover
            return False

        return ret.state

    def _stream_stop(self) -> bool:
        """Stop stream request."""
        ret = self._comm.stream_stop()
        if ret is None:  # pragma: no cover
            return False

        return ret.state

    def _stream_thread(self) -> None:
        """Stream thread."""
        assert self.dev
        chmax = self.dev.data.chmax

        samples: list[list[DNxscopeStream]]
        samples = [[] for _ in range(chmax)]

        # get stream data
        sdata = self._comm.stream_data()
        if sdata:
            if (
                self._comm.flags_is_overflow(sdata.flags) is True
            ):  # pragma: no cover
                logger.info("stream flags: OVERFLOW!")
                with self._stats_lock:
                    self._ovf_cntr += 1

            # Track bytes for all samples
            for data in sdata.samples:
                # Track bytes for bitrate calculation for all samples
                # Get channel info to get correct type
                ch = self.dev_channel_get(data.chan)
                if ch:
                    dsfmt = dsfmt_get(ch.data.dtype)
                    data_bytes = dsfmt.slen * ch.data.vdim
                    meta_bytes = ch.data.mlen
                    total_bytes = data_bytes + meta_bytes
                    if self._bitrate_tracker is not None:
                        self._bitrate_tracker.update(total_bytes)

                # channel enabled
                if (
                    self._comm.ch_is_enabled(data.chan) is True
                ):  # pragma: no cover
                    samples[data.chan].append(
                        DNxscopeStream(data.data, data.meta)
                    )

            with self._queue_lock:
                # send all samples at once
                for data.chan in range(chmax):
                    if len(samples[data.chan]) > 0:
                        # send for all subscribers
                        for que in self._sub_q[data.chan]:
                            que.put(samples[data.chan])

    def _reset_stats(self) -> None:
        with self._stats_lock:
            self._ovf_cntr = 0
        if self._bitrate_tracker is not None:
            self._bitrate_tracker = _BitrateTracker()

    @property
    def dev(self) -> "Device | None":
        """Get device info."""
        return self._comm.dev

    @property
    def connected(self) -> bool:
        """Check if device is connected."""
        return self._connected

    @property
    def stream_started(self) -> bool:
        """Check if stream is started."""
        return self._stream_started

    @property
    def overflow_count(self) -> int:
        """Get overflow counter."""
        with self._stats_lock:
            return self._ovf_cntr

    def get_bitrate(self) -> float:
        """Calculate current bitrate with moving average.

        :return: Bytes per second over the window period, or 0.0 if
        tracking disabled
        """
        if self._bitrate_tracker is None:
            return 0.0
        return self._bitrate_tracker.get_bitrate()

    def get_enabled_channels(self, applied: bool = True) -> tuple[int, ...]:
        """Get enabled channels state.

        :param applied: get currently-applied values when True, otherwise get
            buffered values that will be applied on next channels_write
        """
        return self._comm.get_enabled_channels(applied=applied)

    def get_channel_divider(self, chid: int, applied: bool = True) -> int:
        """Get divider for a channel.

        :param chid: channel ID
        :param applied: get currently-applied value when True, otherwise get
            buffered value that will be applied on next channels_write
        """
        return self._comm.ch_div_get(chid, applied=applied)

    def get_channel_dividers(self, applied: bool = True) -> tuple[int, ...]:
        """Get divider values for all channels.

        :param applied: get currently-applied values when True, otherwise get
            buffered values that will be applied on next channels_write
        """
        return self._comm.get_channel_dividers(applied=applied)

    def get_channels_state(self, applied: bool = True) -> DChannelState:
        """Get channels state snapshot."""
        return DChannelState(
            enabled_channels=self.get_enabled_channels(applied=applied),
            dividers=self.get_channel_dividers(applied=applied),
        )

    def get_device_capabilities(self) -> DDeviceCapabilities:
        """Get device capabilities snapshot."""
        assert self.dev
        data = self.dev.data
        return DDeviceCapabilities(
            chmax=data.chmax,
            flags=data.flags,
            rxpadding=data.rxpadding,
            div_supported=data.div_supported,
            ack_supported=data.ack_supported,
        )

    def get_stream_stats(self) -> DStreamStats:
        """Get stream stats snapshot."""
        return DStreamStats(
            connected=self.connected,
            stream_started=self.stream_started,
            overflow_count=self.overflow_count,
            bitrate=self.get_bitrate(),
        )

    def connect(self) -> "Device | None":
        """Connect with a NxScope device."""
        if self._connected is True:
            logger.info("WARNING: ALREADY CONNECTED!")
            return self._comm.dev

        logger.info("Connecting to NxScope device")
        self._comm.connect()

        # create lists for samples queues
        assert self.dev
        self._sub_q = [[] for _ in range(self.dev.data.chmax)]
        self._connected = True

        return self._comm.dev

    def disconnect(self) -> None:
        """Disconnect from a NxScope device."""
        if self._connected is True:
            # stop stream
            self.stream_stop()
            # disable all channels now
            self.ch_disable_all(True)
            # disconnect
            self._comm.disconnect()
            self._connected = False

    def dev_channel_get(self, chid: int) -> "DeviceChannel | None":
        """Get a channel info.

        :param chid: the channel ID
        """
        assert self.dev
        return self.dev.channel_get(chid)

    def stream_start(self) -> None:
        """Start a data stream.

        Before starting the stream, the buffered channel configuration
        is applied to the device.
        """
        if not self._stream_started:
            # initialize stream
            self.channels_write()

            # start request for nxslib
            self._stream_start()

            # start stream thread
            self._thrd.thread_start()

            self._stream_started = True

    def stream_stop(self) -> None:
        """Stop a data stream."""
        if self._stream_started is True:
            # stop request for nxslib
            self._stream_stop()

            # stop stream thread
            self._thrd.thread_stop()

            self._stream_started = False

    def stream_sub(self, chan: int) -> queue.Queue[list[DNxscopeStream]]:
        """Subscribe to a given channel.

        :param chid: the channel ID
        """
        subq: queue.Queue[list[DNxscopeStream]] = queue.Queue()

        with self._queue_lock:
            self._sub_q[chan].append(subq)

        return subq

    def stream_unsub(self, subq: queue.Queue[list[DNxscopeStream]]) -> None:
        """Unsubscribe from a given channel.

        :param subq: the queue instance that was used with the channel
        """
        with self._queue_lock:
            for i, sub in enumerate(self._sub_q):
                if subq in sub:
                    self._sub_q[i].remove(subq)

    def channels_default_cfg(self, writenow: bool = False) -> None:
        """Set default channels configuration.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.
        :param writenow: write channels configuration now
        """
        self._comm.channels_default_cfg()

        if writenow:
            # write channels configuration
            self.channels_write()

    def ch_enable(
        self, chans: list[int] | int, writenow: bool = False
    ) -> None:
        """Enable a given channels.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.

        :param chans: single channel ID or list with channels IDs
        :param writenow: write channels configuration now
        """
        self._comm.ch_enable(chans)

        if writenow:
            # write channels configuration
            self.channels_write()

    def ch_disable(
        self, chans: list[int] | int, writenow: bool = False
    ) -> None:
        """Disable a given channels.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.

        :param chans: single channel ID or list with channels IDs
        :param writenow: write channels configuration now
        """
        self._comm.ch_disable(chans)

        if writenow:
            # write channels configuration
            self.channels_write()

    def ch_disable_all(self, writenow: bool = False) -> None:
        """Disable all channels.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.

        :param writenow: write channels configuration now
        """
        self._comm.ch_disable_all()

        if writenow:
            # write channels configuration
            self.channels_write()

    def ch_divider(
        self, chans: list[int] | int, div: int, writenow: bool = False
    ) -> None:
        """Configure divider for a given channels.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.

        :param chans: single channel ID or list with channels IDs
        :param div: divider value to be set
        :param writenow: write channels configuration now
        """
        self._comm.ch_divider(chans, div)

        if writenow:
            # write channels configuration
            self.channels_write()

    def channels_write(self) -> None:
        """Write channels configuration."""
        self._comm.channels_write()
