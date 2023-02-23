"""Module containing the NxScope handler."""

import queue
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any

from nxslib.comm import CommHandler
from nxslib.logger import logger
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
# Class: NxscopeHandler
###############################################################################


class NxscopeHandler:
    """A class used to manage NxScope device."""

    def __init__(self, intf: "ICommInterface", parse: "ICommParse") -> None:
        """Initialize the Nxslib handler."""
        self._connected: bool = False
        self._comm = CommHandler(intf, parse)

        self._thrd = ThreadCommon(self._stream_thread, name="stream")

        self._sub_q: list[list[queue.Queue[list[DNxscopeStream]]]] = []
        self._queue_lock: Lock = Lock()

        self._stream_started: bool = False

        self._ovf_cntr: int = 0

    def __del__(self) -> None:
        """Make sure to disconnect from dev."""
        self.disconnect()

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
                self._ovf_cntr += 1

            for data in sdata.samples:
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
        self._ovf_cntr = 0

    @property
    def dev(self) -> "Device | None":
        """Get device info."""
        return self._comm.dev

    def connect(self) -> "Device | None":
        """Connect with a NxScope device."""
        if self._connected is True:
            logger.info("WARNING: ALREADY CONNECTED!")
            return self._comm.dev

        logger.info("pintf.py: connect")
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

        Before starting the stream, the bufferd channel configuration
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
