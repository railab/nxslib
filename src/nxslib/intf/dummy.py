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
    """Generate triangle waveform."""

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
        # start from 0 - we want at least one 'hello' emitted
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


class ChannelFunc10(IDeviceChannelFunc):
    """Generate a deterministic multi-tone signal for FFT tests."""

    _cntr = 0

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        x = 2 * math.pi * self._cntr / 256.0
        data = (
            0.8 * math.sin(3.0 * x)
            + 0.4 * math.sin(11.0 * x)
            + 0.2 * math.sin(19.0 * x),
        )
        self._cntr += 1
        self._cntr %= 256

        return DDeviceChannelFuncData(data=data)


class ChannelFunc11(IDeviceChannelFunc):
    """Generate deterministic chirp-like data for spectrogram tests."""

    _cntr = 0

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        t = self._cntr / 1000.0
        phase = 2.0 * math.pi * (3.0 * t + 20.0 * t * t)
        data = (math.sin(phase),)
        self._cntr += 1
        self._cntr %= 1000

        return DDeviceChannelFuncData(data=data)


class ChannelFunc12(IDeviceChannelFunc):
    """Generate deterministic Gaussian-like scalar samples for histograms."""

    _seed = 12345

    def reset(self) -> None:
        """Reset handler."""
        self._rng = random.Random(self._seed)

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        data = (self._rng.gauss(0.0, 1.0),)
        return DDeviceChannelFuncData(data=data)


class ChannelFunc13(IDeviceChannelFunc):
    """Generate deterministic bi-modal samples for histogram tests."""

    _cntr = 0
    _seed = 23456

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0
        self._rng = random.Random(self._seed)

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        if self._cntr % 2:
            base = -2.5
        else:
            base = 2.5

        data = (base + self._rng.gauss(0.0, 0.2),)
        self._cntr += 1
        return DDeviceChannelFuncData(data=data)


class ChannelFunc14(IDeviceChannelFunc):
    """Generate correlated (x, y) data for XY/Lissajous plots."""

    _cntr = 0

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        x = 2 * math.pi * self._cntr / 500
        data = (
            math.sin(3.0 * x),
            math.sin(4.0 * x + math.pi / 5.0),
        )
        self._cntr += 1
        self._cntr %= 500

        return DDeviceChannelFuncData(data=data)


class ChannelFunc15(IDeviceChannelFunc):
    """Generate (theta, radius) tuples for polar plot tests."""

    _cntr = 0

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        theta = (2.0 * math.pi * self._cntr / 360.0) % (2.0 * math.pi)
        radius = 1.0 + 0.35 * math.sin(5.0 * theta)
        data = (theta, radius)
        self._cntr += 1
        self._cntr %= 360

        return DDeviceChannelFuncData(data=data)


class ChannelFunc16(IDeviceChannelFunc):
    """Generate a single rising step for trigger tests."""

    _cntr = 0
    _step_at = 200

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        value = 0.0 if self._cntr < self._step_at else 1.0
        self._cntr += 1
        return DDeviceChannelFuncData(data=(value,))


class ChannelFunc17(IDeviceChannelFunc):
    """Generate a single falling step for trigger tests."""

    _cntr = 0
    _step_at = 200

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        value = 1.0 if self._cntr < self._step_at else 0.0
        self._cntr += 1
        return DDeviceChannelFuncData(data=(value,))


class ChannelFunc18(IDeviceChannelFunc):
    """Generate periodic square pulse train (20%% duty)."""

    _cntr = 0
    _period = 100
    _high = 20

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        phase = self._cntr % self._period
        value = 1.0 if phase < self._high else 0.0
        self._cntr += 1
        return DDeviceChannelFuncData(data=(value,))


class ChannelFunc19(IDeviceChannelFunc):
    """Generate sparse one-sample pulses for trigger tests."""

    _cntr = 0
    _period = 250

    def reset(self) -> None:
        """Reset handler."""
        self._cntr = 0

    def get(self, _: int) -> DDeviceChannelFuncData:
        """Get sample data."""
        value = 1.0 if (self._cntr % self._period) == 0 else 0.0
        self._cntr += 1
        return DDeviceChannelFuncData(data=(value,))


DUMMY_DEV_CHANNELS = [
    DeviceChannel(
        0,
        EDeviceChannelType.FLOAT.value,
        1,
        "noise_uniform_scalar",
        func=ChannelFunc0(),
    ),
    DeviceChannel(
        1,
        EDeviceChannelType.FLOAT.value,
        1,
        "ramp_saw_up",
        func=ChannelFunc1(),
    ),
    DeviceChannel(
        2,
        EDeviceChannelType.FLOAT.value,
        1,
        "ramp_triangle",
        func=ChannelFunc2(),
    ),
    DeviceChannel(
        3,
        EDeviceChannelType.FLOAT.value,
        2,
        "noise_uniform_vec2",
        func=ChannelFunc3(),
    ),
    DeviceChannel(
        4,
        EDeviceChannelType.FLOAT.value,
        3,
        "noise_uniform_vec3",
        func=ChannelFunc4(),
    ),
    DeviceChannel(
        5,
        EDeviceChannelType.FLOAT.value,
        3,
        "static_vec3",
        func=ChannelFunc5(),
    ),
    DeviceChannel(
        6,
        EDeviceChannelType.CHAR.value,
        64,
        "text_hello_sparse",
        func=ChannelFunc6(),
    ),
    DeviceChannel(
        7,
        EDeviceChannelType.INT8.value,
        3,
        "static_vec3_meta_counter",
        mlen=1,
        func=ChannelFunc7(),
    ),
    DeviceChannel(
        8,
        EDeviceChannelType.NONE.value,
        0,
        "meta_hello_only",
        mlen=16,
        func=ChannelFunc8(),
    ),
    DeviceChannel(
        9,
        EDeviceChannelType.FLOAT.value,
        3,
        "sine_three_phase",
        func=ChannelFunc9(),
    ),
    DeviceChannel(
        10,
        EDeviceChannelType.UNDEF.value,
        0,
        "",
        func=None,
    ),
    DeviceChannel(
        11,
        EDeviceChannelType.FLOAT.value,
        1,
        "fft_multitone",
        func=ChannelFunc10(),
    ),
    DeviceChannel(
        12,
        EDeviceChannelType.FLOAT.value,
        1,
        "fft_chirp",
        func=ChannelFunc11(),
    ),
    DeviceChannel(
        13,
        EDeviceChannelType.FLOAT.value,
        1,
        "hist_gaussian",
        func=ChannelFunc12(),
    ),
    DeviceChannel(
        14,
        EDeviceChannelType.FLOAT.value,
        1,
        "hist_bimodal",
        func=ChannelFunc13(),
    ),
    DeviceChannel(
        15,
        EDeviceChannelType.FLOAT.value,
        2,
        "xy_lissajous",
        func=ChannelFunc14(),
    ),
    DeviceChannel(
        16,
        EDeviceChannelType.FLOAT.value,
        2,
        "polar_theta_radius",
        func=ChannelFunc15(),
    ),
    DeviceChannel(
        17,
        EDeviceChannelType.FLOAT.value,
        1,
        "step_up_once",
        func=ChannelFunc16(),
    ),
    DeviceChannel(
        18,
        EDeviceChannelType.FLOAT.value,
        1,
        "step_down_once",
        func=ChannelFunc17(),
    ),
    DeviceChannel(
        19,
        EDeviceChannelType.FLOAT.value,
        1,
        "pulse_square_20p",
        func=ChannelFunc18(),
    ),
    DeviceChannel(
        20,
        EDeviceChannelType.FLOAT.value,
        1,
        "pulse_single_sparse",
        func=ChannelFunc19(),
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
        thread_timeout: float = 1.0,
    ) -> None:
        """Initialize a dummy NxScope interface.

        :param chmax: the number of supported channels
        :param flags: the device flags
        :param channels: a device channels list
        :param rxpadding: rxpadding - doesn't matter here
        :param stream_sleep: samples thread parameter
        :param stream_snum: samples thread parameter
        :param thread_timeout: timeout for blocking thread operations
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
        self._thread_timeout = thread_timeout
        self._qwrite: queue.Queue[bytes] = queue.Queue()
        self._qread: queue.Queue[bytes] = queue.Queue()

        self._stream_started = Event()
        self._div_counters = [0 for _ in range(self._dummydev.data.chmax)]

        self._parse: ParseRecv | None = None

    def __enter__(self) -> "DummyDev":
        """Start on context manager entry."""
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        """Stop on context manager exit."""
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
                self._div_counters[chid] = 0

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
                        div = int(chan.data.div)
                        take = True
                        if div > 0:
                            counter = self._div_counters[chid]
                            take = (counter % (div + 1)) == 0
                            self._div_counters[chid] = counter + 1

                        if not take:
                            continue

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
        if self._stream_started.wait(timeout=self._thread_timeout):
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
            data = self._qwrite.get(block=True, timeout=self._thread_timeout)
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
            self._div_counters = [0 for _ in range(self._dummydev.data.chmax)]

        self._thrd_recv.thread_start()
        self._thrd_stream.thread_start()

    def drop_all(self) -> None:
        """Drop all frames."""

    def _read(self) -> bytes:
        """Interface specific read method."""
        data = b""
        try:
            data = self._qread.get(block=True, timeout=self._thread_timeout)
        except queue.Empty:
            pass

        return data

    def _write(self, data: bytes) -> None:
        """Interface specific write method.

        :param data: bytes to send
        """
        self._qwrite.put(data)
