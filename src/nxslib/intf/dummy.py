"""Module containing the NxScope dummy interface implementation."""

import math
import queue
import random
import time
from threading import Event, Lock

from nxslib.dev import (
    DDeviceChannelFuncData,
    Device,
    DeviceChannel,
    EDeviceChannelType,
    EDeviceFlags,
    IDeviceChannelFunc,
)
from nxslib.intf.iintf import ICommInterface
from nxslib.logger import logger
from nxslib.proto.iparse import DParseStreamData
from nxslib.proto.iparserecv import ParseRecvCb
from nxslib.proto.parserecv import ParseRecv
from nxslib.thread import ThreadCommon

###############################################################################
# Dummy nxslib device
###############################################################################


class ChannelFunc0(IDeviceChannelFunc):
    """Generate random data for channel."""

    def reset(self) -> None:
        """Reset handler."""

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        data = (random.random(),)
        return DDeviceChannelFuncData(data=data)


class ChannelFunc1(IDeviceChannelFunc):
    """Generate triangle waveform."""

    _cntr = 0

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        self._cntr += 1
        if self._cntr > 1000:
            self._cntr = 0

        data = (self._cntr,)
        return DDeviceChannelFuncData(data=data)


class ChannelFunc2(IDeviceChannelFunc):
    """Generate triange waveform."""

    _cntr = 0
    _sign = 1

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0
        self._sign = 1

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        self._cntr += 1 * self._sign
        if self._cntr > 1000:
            self._sign *= -1
        elif self._cntr < -1000:
            self._sign *= -1

        data = (self._cntr,)
        return DDeviceChannelFuncData(data=data)


class ChannelFunc3(IDeviceChannelFunc):
    """Generate vector random data."""

    def reset(self) -> None:
        """Reset handler."""

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        data = random.random(), random.random()
        return DDeviceChannelFuncData(data=data)


class ChannelFunc4(IDeviceChannelFunc):
    """Generate vector random data."""

    def reset(self) -> None:
        """Reset handler."""

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        data = random.random(), random.random(), random.random()
        return DDeviceChannelFuncData(data=data)


class ChannelFunc5(IDeviceChannelFunc):
    """Generate static data."""

    def reset(self) -> None:
        """Reset handler."""

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        data = (1.0, 0.0, -1.0)
        return DDeviceChannelFuncData(data=data)


class ChannelFunc6(IDeviceChannelFunc):
    """Generate string data."""

    _cntr = 0

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData | None:
        """Get sample data."""
        # start from 0 - we want at leas one 'hello' emitted
        if not self._cntr % 10000:
            self._cntr += 1
            text = "hello" + "\0" * 59
            data = (text,)
            return DDeviceChannelFuncData(data=data)
        self._cntr += 1
        return None


class ChannelFunc7(IDeviceChannelFunc):
    """Generate static vector data."""

    _cntr = 0

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        data = (1, 0, -1)
        self._cntr += 1
        self._cntr %= 255
        return DDeviceChannelFuncData(data=data, meta=(self._cntr,))


class ChannelFunc8(IDeviceChannelFunc):
    """Generate hello message in meta data."""

    def reset(self) -> None:
        """Reset handler."""

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        data = ()
        meta = list(b"hello" + b"\x00" * 11)  # align to 16B
        return DDeviceChannelFuncData(data=data, meta=tuple(meta))


class ChannelFunc9(IDeviceChannelFunc):
    """Generate 3-phase sine wave."""

    _cntr = 0

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        x = 2 * math.pi * self._cntr / 500
        data = (
            math.sin(x),
            math.sin(x + (2 * math.pi / 3)),
            math.sin(x + (4 * math.pi / 3)),
        )
        self._cntr += 1
        self._cntr %= 500

        return DDeviceChannelFuncData(data=data)


DUMMY_DEV_CHANNELS = [
    DeviceChannel(
        0,
        EDeviceChannelType.FLOAT.value,
        1,
        "chan0",
        func=ChannelFunc0(),
    ),
    DeviceChannel(
        1,
        EDeviceChannelType.FLOAT.value,
        1,
        "chan1",
        func=ChannelFunc1(),
    ),
    DeviceChannel(
        2,
        EDeviceChannelType.FLOAT.value,
        1,
        "chan2",
        func=ChannelFunc2(),
    ),
    DeviceChannel(
        3,
        EDeviceChannelType.FLOAT.value,
        2,
        "chan3",
        func=ChannelFunc3(),
    ),
    DeviceChannel(
        4,
        EDeviceChannelType.FLOAT.value,
        3,
        "chan4",
        func=ChannelFunc4(),
    ),
    DeviceChannel(
        5,
        EDeviceChannelType.FLOAT.value,
        3,
        "chan5",
        func=ChannelFunc5(),
    ),
    DeviceChannel(
        6,
        EDeviceChannelType.CHAR.value,
        64,
        "chan6",
        func=ChannelFunc6(),
    ),
    DeviceChannel(
        7,
        EDeviceChannelType.INT8.value,
        3,
        "chan7",
        mlen=1,
        func=ChannelFunc7(),
    ),
    DeviceChannel(
        8,
        EDeviceChannelType.NONE.value,
        0,
        "chan8",
        mlen=16,
        func=ChannelFunc8(),
    ),
    DeviceChannel(
        9,
        EDeviceChannelType.FLOAT.value,
        3,
        "chan9",
        func=ChannelFunc9(),
    ),
    DeviceChannel(
        10,
        EDeviceChannelType.UNDEF.value,
        0,
        "",
        func=None,
    ),
]
DUMMY_DEV_CHMAX = len(DUMMY_DEV_CHANNELS)
DUMMY_DEV_FLAGS = (
    EDeviceFlags.DIVIDER_SUPPORT.value + EDeviceFlags.ACK_SUPPORT.value
)

###############################################################################
# Class: DummyDev
###############################################################################


class DummyDev(ICommInterface):
    """A class used to represent a dummy interface."""

    def __init__(
        self,
        chmax: int = 0,
        flags: int = DUMMY_DEV_FLAGS,
        channels: list[DeviceChannel] | None = None,
        rxpadding: int = 16,
        stream_sleep: float = 0.001,
        stream_snum: int = 100,
    ) -> None:
        """Intitialize a dummy NxScope interface.

        :param chmax: the number of supported channels
        :param flags: the device flags
        :param channels: a device channels list
        :param rxpadding: rxpadding - doesn't matter here
        :param stream_sleep: samples thread parameter
        :param stream_snum: samples thread parameter
        """
        super().__init__()
        self._thrd_stream = ThreadCommon(
            self._thread_stream, name="dummy_stream"
        )
        self._thrd_recv = ThreadCommon(self._thread_recv, name="dummy_recv")

        # default device
        if not channels:
            chmax = DUMMY_DEV_CHMAX
            channels = DUMMY_DEV_CHANNELS
        assert channels

        self._dummydev = Device(chmax, flags, rxpadding, channels)
        self._dummydev_lock = Lock()
        self._stream_sleep = stream_sleep
        self._stream_snum = stream_snum
        self._qwrite: queue.Queue[bytes] = queue.Queue()
        self._qread: queue.Queue[bytes] = queue.Queue()

        self._stream_started = Event()

        self._parse: ParseRecv | None = None

    def __del__(self) -> None:
        """Make sure that interface is stoped."""
        self.stop()

    def _cmninfo_cb(self, data: bytes) -> None:
        assert self._parse

        with self._dummydev_lock:
            _bytes = self._parse.frame_cmninfo_encode(self._dummydev)
        self._qread.put(_bytes)

    def _chinfo_cb(self, data: bytes) -> None:
        assert self._parse

        with self._dummydev_lock:
            chan = self._dummydev.channel_get(data[0])
            assert chan
            _bytes = self._parse.frame_chinfo_encode(chan)

        self._qread.put(_bytes)

    def _enable_cb(self, data: bytes) -> None:
        assert self._parse

        with self._dummydev_lock:
            enables = self._parse.frame_enable_decode(data, self._dummydev)
            for chid, en in enumerate(enables):
                chan = self._dummydev.channel_get(chid)
                assert chan
                chan.data.en = en

            if self._dummydev.data.ack_supported:
                _bytes = self._parse.frame_ack_encode(0)
                self._qread.put(_bytes)

    def _div_cb(self, data: bytes) -> None:
        assert self._parse

        with self._dummydev_lock:
            dividers = self._parse.frame_div_decode(data, self._dummydev)
            for chid, div in enumerate(dividers):
                chan = self._dummydev.channel_get(chid)
                assert chan
                chan.data.div = div

            if self._dummydev.data.ack_supported:
                _bytes = self._parse.frame_ack_encode(0)
                self._qread.put(_bytes)

    def _start_cb(self, data: bytes) -> None:
        assert self._parse

        start = self._parse.frame_start_decode(data)

        # start/stop stream
        if start is True:
            self._stream_started.set()
        else:
            self._stream_started.clear()

        with self._dummydev_lock:
            # send ACK after action
            if self._dummydev.data.ack_supported:
                _bytes = self._parse.frame_ack_encode(0)
                self._qread.put(_bytes)

    def _stream_data_get(self, snum: int) -> list[DParseStreamData]:
        samples = []

        with self._dummydev_lock:
            for _ in range(snum):
                for chid in range(self._dummydev.data.chmax):
                    chan = self._dummydev.channel_get(chid)
                    assert chan

                    if chan.data.en is True:
                        data = chan.data_get()
                        if data:
                            sample = DParseStreamData(
                                chan=chid,
                                dtype=chan.data.dtype,
                                vdim=chan.data.vdim,
                                mlen=chan.data.mlen,
                                data=data.data,
                                meta=data.meta,
                            )
                            samples.append(sample)
        return samples

    def _thread_stream(self) -> None:
        assert self._parse
        if self._stream_started.wait(timeout=1.0):
            samples = self._stream_data_get(self._stream_snum)
            frame = self._parse.frame_stream_encode(samples)
            if frame is not None:  # pragma: no cover
                self._qread.put(frame)
            time.sleep(self._stream_sleep)

    def _thread_recv(self) -> None:
        assert self._parse

        data = None
        try:
            # NOTE: timeout must be not zero otherwise we have
            #       deadlock when thread stop is requested
            data = self._qwrite.get(block=True, timeout=1.0)
        except queue.Empty:
            pass

        if data is not None:
            self._parse.recv_handle(data)

    def stop(self) -> None:
        """Stop the interface."""
        logger.debug("Stop dummy interface")
        self._thrd_stream.thread_stop()
        self._thrd_recv.thread_stop()

        # get all pending data from queues
        try:
            _ = self._qwrite.get_nowait()
        except queue.Empty:
            pass

        try:
            _ = self._qread.get_nowait()
        except queue.Empty:
            pass

        if self._parse is not None:
            del self._parse
            self._parse = None

    def start(self) -> None:
        """Start the interface."""
        logger.debug("Start dummy interface")

        recv_cb = ParseRecvCb(
            cmninfo=self._cmninfo_cb,
            chinfo=self._chinfo_cb,
            enable=self._enable_cb,
            div=self._div_cb,
            start=self._start_cb,
        )
        self._parse = ParseRecv(recv_cb)

        with self._dummydev_lock:
            # reset dev state
            self._dummydev.reset()

        self._thrd_recv.thread_start()
        self._thrd_stream.thread_start()

    def drop_all(self) -> None:
        """Drop all frames."""

    def _read(self) -> bytes:
        """Interface specific read method."""
        data = b""
        try:
            data = self._qread.get(block=True, timeout=1)
        except queue.Empty:
            pass

        return data

    def _write(self, data: bytes) -> None:
        """Interface specific write method.

        :param data: bytes to send
        """
        self._qwrite.put(data)
