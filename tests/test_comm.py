import pytest  # type: ignore

from nxslib.comm import CommHandler
from nxslib.dev import Device, EDeviceFlags
from nxslib.intf.dummy import DummyDev
from nxslib.proto.iparse import EParseDataType
from nxslib.proto.parse import Parser


def test_nxslib_init():
    i = DummyDev()
    p = Parser()

    comm = CommHandler(i, p)
    assert isinstance(comm, CommHandler)


@pytest.fixture
def comm():
    i = DummyDev()
    p = Parser()
    return CommHandler(i, p)


def test_nxslib_connect(comm):
    # not connected - no info
    assert comm.dev is None

    comm.connect()
    assert comm.dev is not None
    assert isinstance(comm.dev, Device)

    # connect again
    comm.connect()
    assert comm.dev is not None
    assert isinstance(comm.dev, Device)

    comm.disconnect()
    assert comm.dev is None

    # disconnect again
    comm.disconnect()
    assert comm.dev is None


def test_nxslib_channels(comm):
    # not connected should raise error
    with pytest.raises(AssertionError):
        comm.channels_default_cfg()

    # connect
    comm.connect()

    # default configuration
    comm.channels_default_cfg()
    comm.channels_write()
    for chan in range(comm.dev.data.chmax):
        assert comm.ch_is_enabled(chan) is False
        assert comm.ch_div_get(chan) == 0

    # invalid interface use
    with pytest.raises(TypeError):
        comm.ch_enable("1")
    with pytest.raises(TypeError):
        comm.ch_disable("1")
    with pytest.raises(TypeError):
        comm.ch_divider("1", 0)
    with pytest.raises(ValueError):
        comm.ch_divider(1, 1000)

    # enable all channels
    comm.ch_enable_all()
    comm.channels_write()
    for chan in range(comm.dev.data.chmax):
        assert comm.ch_is_enabled(chan) is True
        assert comm.ch_div_get(chan) == 0

    # enable all once again
    comm.ch_enable_all()
    comm.channels_write()

    # disable channel
    comm.ch_disable(0)
    comm.channels_write()
    assert comm.ch_is_enabled(0) is False
    assert comm.ch_is_enabled(1) is True
    assert comm.ch_is_enabled(2) is True
    assert comm.ch_is_enabled(3) is True

    # disable channels
    comm.ch_disable([1, 3])
    comm.channels_write()

    # once again
    comm.ch_disable([1, 3])
    comm.channels_write()

    # divider
    comm.ch_divider(1, 1)
    comm.channels_write()
    assert comm.ch_div_get(0) == 0
    assert comm.ch_div_get(1) == 1
    assert comm.ch_div_get(2) == 0
    assert comm.ch_div_get(3) == 0

    # divider
    comm.ch_divider([0, 3], 3)
    comm.channels_write()
    assert comm.ch_div_get(0) == 3
    assert comm.ch_div_get(1) == 1
    assert comm.ch_div_get(2) == 0
    assert comm.ch_div_get(3) == 3
    # disconnect
    comm.disconnect()


def test_nxslib_stream_ch1(comm):
    # connect
    comm.connect()

    # default configuration
    comm.channels_default_cfg()

    # enable channel 1
    comm.ch_enable(1)
    comm.channels_write()

    # no stream - should be no data
    assert comm.stream_data() is None

    # start stream
    comm.stream_start()

    # get data
    data = comm.stream_data()
    assert data is not None
    assert data.flags == 0

    # should mach dummy dev channel 1
    i = 1.0
    for x in data.samples:
        assert x.chan == 1
        assert x.dtype == EParseDataType.NUM
        assert x.vdim == 1
        assert x.mlen == 0
        assert isinstance(x.data, tuple)
        assert x.data == (i,)
        i += 1.0
        assert x.meta == ()

    # do not stop stream but disconnect
    comm.disconnect()


def test_nxslib_stream_ch1ch2(comm):
    # connect
    comm.connect()

    # default configuration
    comm.channels_default_cfg()

    # enable channel 1 and 2
    comm.ch_enable([1, 2])
    comm.channels_write()

    # no stream - should be no data
    assert comm.stream_data() is None

    # start stream
    comm.stream_start()

    # get data
    data = comm.stream_data()
    assert data is not None
    assert data.flags == 0

    # we expect data from ch1 and ch2
    ch1_cntr = 0
    ch2_cntr = 0
    for x in data.samples:
        if x.chan == 1:
            ch1_cntr += 1
        if x.chan == 2:
            ch2_cntr += 1

    assert ch1_cntr > 0
    assert ch2_cntr > 0

    # do not stop stream but disconnect
    comm.disconnect()


def test_nxslib_stream_ch6(comm):
    # connect again
    comm.connect()

    # default configuration
    comm.channels_default_cfg()

    # enable channel 6
    comm.ch_enable(6)
    comm.channels_write()

    # no stream - should be no data
    assert comm.stream_data() is None

    # start stream
    comm.stream_start()

    # get data
    data = comm.stream_data()
    assert data is not None
    assert data.flags == 0

    # should mach dummy dev channel 6 - we should capture at least one message
    for x in data.samples:
        assert x.chan == 6
        assert x.dtype == EParseDataType.CHAR
        assert x.vdim == 64
        assert x.mlen == 0
        assert isinstance(x.data[0], str)
        assert x.data == ("hello" + "\0" * 59,)
        assert x.meta == ()

    # stop stream
    comm.stream_stop()

    # disconnect
    comm.disconnect()


def test_nxslib_stream_ch7(comm):
    # connect again
    comm.connect()

    # default configuration
    comm.channels_default_cfg()

    # enable channel 7
    comm.ch_enable(7)
    comm.channels_write()

    # no stream - should be no data
    assert comm.stream_data() is None

    # start stream
    comm.stream_start()

    # get data
    data = comm.stream_data()
    assert data is not None
    assert data.flags == 0

    # should mach dummy dev channel 7
    i = 1
    for x in data.samples:
        assert x.chan == 7
        assert x.dtype == EParseDataType.NUM
        assert x.vdim == 3
        assert x.mlen == 1
        assert isinstance(x.data, tuple)
        assert x.data == (1, 0, -1)
        assert x.meta == (i,)
        i += 1

    # stop stream
    comm.stream_stop()

    # disconnect
    comm.disconnect()


def test_nxslib_stream_ch8(comm):
    # connect again
    comm.connect()

    # default configuration
    comm.channels_default_cfg()

    # enable channel 8
    comm.ch_enable(8)
    comm.channels_write()

    # no stream - should be no data
    assert comm.stream_data() is None

    # start stream
    comm.stream_start()

    # get data
    data = comm.stream_data()
    assert data is not None
    assert data.flags == 0

    # should mach dummy dev channel 7
    for x in data.samples:
        assert x.chan == 8
        assert x.dtype == EParseDataType.NONE
        assert x.vdim == 0
        assert x.mlen == 16
        assert x.data == ()
        assert x.meta == (
            104,
            101,
            108,
            108,
            111,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )  # hello

    # stop stream
    comm.stream_stop()

    # disconnect
    comm.disconnect()


def test_nxslib_nodiv(comm):
    i = DummyDev(flags=EDeviceFlags.ACK_SUPPORT.value)
    p = Parser()
    comm = CommHandler(i, p)

    # connect
    comm.connect()

    # default configuration
    comm.channels_default_cfg()
    comm.channels_write()

    comm.ch_enable(0)
    comm.ch_divider(1, 1)
    comm.channels_write()
    assert comm.ch_is_enabled(0) is True
    assert comm.ch_div_get(0) == 0

    # disconnect
    comm.disconnect()


def test_nxslib_noack(comm):
    i = DummyDev(flags=EDeviceFlags.DIVIDER_SUPPORT.value)
    p = Parser()
    comm = CommHandler(i, p)

    # connect
    comm.connect()

    # default configuration
    comm.channels_default_cfg()
    comm.channels_write()

    comm.ch_enable(0)
    comm.ch_divider(1, 1)
    comm.channels_write()
    assert comm.ch_is_enabled(0) is True
    assert comm.ch_div_get(0) == 0

    # disconnect
    comm.disconnect()
