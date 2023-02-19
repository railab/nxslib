"""Module containing the NxScope handler."""

import queue
import time
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any

from nxslib.logger import logger
from nxslib.thread import ThreadCommon

if TYPE_CHECKING:
    from nxslib.comm import CommHandler
    from nxslib.dev import Device, DeviceChannel
    from nxslib.proto.iparse import DParseStream


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
# Class: NxscopeHandler
###############################################################################


class NxscopeHandler:
    """A class used to manage NxScope device."""

    def __init__(self) -> None:
        """Initialize the Nxslib handler."""
        self._comm: "CommHandler"

        self._thrd = ThreadCommon(self._stream_thread, name="stream")

        self._sub_q: list[list[queue.Queue[list[DNxscopeStream]]]] = []
        self._queue_lock: Lock = Lock()

        self._stream_started: bool = False
        self._connected: bool = False

        self._ovf_cntr: int = 0

    def __del__(self) -> None:
        """Make sure to disconnect from dev."""
        self.disconnect()

    def _nxslib_start(self) -> bool:
        """Send nxslib start request."""
        assert self._comm

        self._reset_stats()

        ret = self._comm.stream_start()
        if ret is None:  # pragma: no cover
            return False

        return ret.state

    def _nxslib_stop(self) -> bool:
        """Send nxslib stop request."""
        assert self._comm

        ret = self._comm.stream_stop()
        if ret is None:  # pragma: no cover
            return False

        return ret.state

    def _nxslib_stream(self) -> "DParseStream | None":
        """Get nxslib stream data."""
        assert self._comm
        return self._comm.stream_data()

    def _stream_thread(self) -> None:
        """Stream thread."""
        assert self._comm
        assert self.dev

        chmax = self.dev.chmax

        # get stream data
        sdata = self._nxslib_stream()
        if sdata is None:
            # wait some time to free resources
            # this allow us handle properly ACK frames that are
            # captured by stream logic
            time.sleep(0.01)
        else:
            stream = sdata.samples
            flags = sdata.flags

            if self._comm.flags_is_overflow(flags) is True:  # pragma: no cover
                logger.info("stream flags: OVERFLOW!")
                self._ovf_cntr += 1

            samples: list[list[DNxscopeStream]]
            samples = [[] for _ in range(chmax)]

            for data in stream:
                chan = data.chan
                val = data.data
                meta = data.meta
                # channel enabled
                if self._comm.ch_is_enabled(chan) is True:  # pragma: no cover
                    samples[chan].append(DNxscopeStream(val, meta))

            with self._queue_lock:
                # send all samples at once
                for chan in range(chmax):
                    if len(samples[chan]) > 0:
                        # send for all subscribers
                        for que in self._sub_q[chan]:
                            que.put(samples[chan])

    def _reset_stats(self) -> None:
        self._ovf_cntr = 0

    @property
    def dev(self) -> "Device | None":
        """Get device info."""
        assert self._comm
        return self._comm.dev

    @property
    def intf_is_connected(self) -> bool:
        """Get connection status."""
        try:
            if self._comm is not None:
                return True
            return False  # pragma: no cover
        except AttributeError:
            return False

    def connect(self) -> "Device | None":
        """Connect with a NxScope device."""
        assert self._comm

        if self._connected is True:
            logger.info("WARNING: ALREADY CONNECTED!")
            return self._comm.dev

        logger.info("pintf.py: connect")
        self._comm.connect()

        # create lists for samples queues
        assert self.dev
        self._sub_q = [[] for _ in range(self.dev.chmax)]
        self._connected = True

        return self._comm.dev

    def disconnect(self) -> None:
        """Disconnect from a NxScope device."""
        if self._connected is True:
            assert self._comm
            # stop stream
            self.stream_stop()
            # disconnect
            self._comm.disconnect()

    def intf_connect(self, comm: "CommHandler") -> None:
        """Connect a NxScope communication handler.

        :param comm: communication handler
        """
        assert comm
        self._comm = comm

    def dev_channel_get(self, chid: int) -> "DeviceChannel | None":
        """Get a channel info.

        :param chid: the channel ID
        """
        assert self.dev
        return self.dev.channel_get(chid)

    def stream_start(self) -> None:
        """Start a data stream.

        Before starting the stream, the bufferd channel configuration
        is applied to the device.
        """
        assert self._comm

        if not self._stream_started:
            # initialize stream
            self.channels_write()

            # start request for nxslib
            self._nxslib_start()

            # start stream thread
            self._thrd.thread_start()

            self._stream_started = True

    def stream_stop(self) -> None:
        """Stop a data stream."""
        assert self._comm

        if self._stream_started is True:
            # stop request for nxslib
            self._nxslib_stop()

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
        assert self._comm
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
        assert self._comm
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
        assert self._comm
        self._comm.ch_disable(chans)

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
        assert self._comm
        self._comm.ch_divider(chans, div)

        if writenow:
            # write channels configuration
            self.channels_write()

    def channels_write(self) -> None:
        """Write channels configuration."""
        assert self._comm
        self._comm.channels_write()
