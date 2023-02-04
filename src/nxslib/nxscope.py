"""Module containing the NxScope handler."""

import queue
import time
from threading import Lock

from nxslib.comm import CommHandler
from nxslib.dev import Device, DeviceChannel
from nxslib.logger import logger
from nxslib.proto.iparse import DParseStream
from nxslib.thread import ThreadCommon

###############################################################################
# Class: NxscopeHandler
###############################################################################


class NxscopeHandler:
    """A class used to manage NxScope device."""

    def __init__(self) -> None:
        """Initialize the Nxslib handler."""
        self._comm: CommHandler

        self._chanlist: list[DeviceChannel] = []

        self._thrd = ThreadCommon(self._stream_thread)

        self._sub_q: list[list[queue.Queue[list[tuple]]]] = []
        self._queue_lock: Lock = Lock()

        self._stream_started: bool = False
        self._connected: bool = False

        self._ovf_cntr: int = 0

    def __del__(self):
        """Make sure to disconnect from dev."""
        self.disconnect()

    def _nxslib_stream_init(self) -> None:
        """Send nxslib stream initialization data."""
        assert self._comm
        self._comm.stream_init()

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

    def _nxslib_stream(self) -> DParseStream | None:
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

            samples: list[list[tuple]]
            samples = [[] for _ in range(chmax)]

            for data in stream:
                chan = data.chan
                val = data.data
                meta = data.meta
                # channel enabled
                if self._comm.ch_is_enabled(chan) is True:  # pragma: no cover
                    samples[chan].append((val, meta))

            with self._queue_lock:
                # send all samples at once
                for chan in range(chmax):
                    if len(samples[chan]) > 0:
                        # send for all subscribers
                        for que in self._sub_q[chan]:
                            que.put(samples[chan])

    def _reset_stats(self) -> None:
        self._ovf_cntr = 0

    def _chanlist_gen(self, channels: str | list[int]) -> list[DeviceChannel]:
        assert self.dev

        # convert special key 'all'
        if isinstance(channels, str):
            if channels == "all":
                chanlist = list(range(self.dev.chmax))
            else:
                raise TypeError
        else:
            assert all(isinstance(x, int) for x in channels)
            chanlist = channels

        # get channels data
        ret = []
        for chan in chanlist:
            assert isinstance(chan, int)
            channel = self.dev_channel_get(chan)
            assert channel
            ret.append(channel)

        return ret

    def _chanlist_enable(self):
        for channel in self._chanlist:
            # ignore not valid channels
            if not channel.is_valid:
                logger.info(
                    "NOTE: channel %d not valid - ignore", channel.chan
                )
                continue

            # enable channel
            self.nxslib_ch_enable(channel.chan)

    def _chanlist_div(self, div: int | list[int]):
        if isinstance(div, int):
            for channel in self._chanlist:
                self.nxslib_ch_divider(channel.chan, div)
        else:
            assert isinstance(div, list)
            # divider list configuration must cover all configured channels
            if len(div) != len(self._chanlist):
                raise TypeError
            for i, channel in enumerate(self._chanlist):
                self.nxslib_ch_divider(channel.chan, div[i])

    @property
    def dev(self) -> Device | None:
        """Get device info."""
        assert self._comm
        return self._comm.dev

    @property
    def chanlist(self) -> list[DeviceChannel]:
        """Get configured channels list."""
        return self._chanlist

    @property
    def intf_is_connected(self) -> bool:
        """Get connection status."""
        try:
            if self._comm is not None:
                return True
            return False  # pragma: no cover
        except AttributeError:
            return False

    def connect(self) -> Device | None:
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
            self._comm.disconnect()

    def nxslib_channels_default_cfg(self) -> None:
        """Set default channels configuration."""
        assert self._comm
        self._comm.channels_default_cfg()

    def nxslib_ch_enable(self, chans: list | int) -> None:
        """Enable a given channels."""
        assert self._comm
        self._comm.ch_enable(chans)

    def nxslib_ch_divider(self, chans: list | int, div: int) -> None:
        """Configure divider for a given channels."""
        assert self._comm
        self._comm.ch_divider(chans, div)

    def intf_connect(self, comm: CommHandler) -> None:
        """Connect a NxScope communication handler."""
        assert comm
        self._comm = comm

    def dev_channel_get(self, chid: int) -> DeviceChannel | None:
        """Get a channel info."""
        assert self.dev
        return self.dev.channel_get(chid)

    def stream_start(self, force: bool = False) -> None:
        """Start NxScope stream."""
        assert self._comm

        if not self._stream_started or force:
            # initialize stream
            self._nxslib_stream_init()

            # start request for nxslib
            self._nxslib_start()

            # start stream thread
            self._thrd.thread_start()

            self._stream_started = True

    def stream_stop(self, force: bool = False) -> None:
        """Stop NxScope stream."""
        assert self._comm

        if self._stream_started is True or force is True:
            # stop request for nxslib
            self._nxslib_stop()

            # stop stream thread
            self._thrd.thread_stop()

            self._stream_started = False

    def stream_sub(self, chan: int) -> queue.Queue:
        """Subscribe to a given channel."""
        subq: queue.Queue[list[tuple]] = queue.Queue()

        with self._queue_lock:
            self._sub_q[chan].append(subq)

        return subq

    def stream_unsub(self, chan: int, subq: queue.Queue):
        """Unsubscribe from a given channel."""
        with self._queue_lock:
            self._sub_q[chan].remove(subq)

    def channels_configure(
        self, channels: str | list[int], div: int | list[int] = 0
    ) -> None:
        """Configure channels."""
        assert self.dev

        logger.info("configure channels = %s divider = %d", str(channels), div)

        self._chanlist = self._chanlist_gen(channels)
        if not self._chanlist:
            return

        # default channels configuration
        self.nxslib_channels_default_cfg()

        # enable channels
        self._chanlist_enable()

        # set divider for channels
        self._chanlist_div(div)

        return
