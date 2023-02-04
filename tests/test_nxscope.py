import queue

import pytest  # type: ignore

from nxslib.comm import CommHandler
from nxslib.intf.dummy import DummyDev
from nxslib.nxscope import NxscopeHandler
from nxslib.proto.parse import Parser


def test_nxslib_init():
    nxslib = NxscopeHandler()
    assert isinstance(nxslib, NxscopeHandler)


def test_nxslib_nointf():
    nxslib = NxscopeHandler()

    with pytest.raises(AttributeError):
        _ = nxslib.dev_channel_get(0)
    with pytest.raises(AttributeError):
        nxslib.connect()
    with pytest.raises(AttributeError):
        nxslib.stream_start()
    with pytest.raises(AttributeError):
        nxslib.stream_stop()


def test_nxslib_intf():
    intf = DummyDev()
    parse = Parser()
    comm = CommHandler(intf, parse)
    nxslib = NxscopeHandler()

    assert nxslib.intf_is_connected is False
    nxslib.intf_connect(comm)
    assert nxslib.intf_is_connected is True


def test_nxslib_connect():
    intf = DummyDev()
    parse = Parser()
    comm = CommHandler(intf, parse)
    nxslib = NxscopeHandler()

    nxslib.intf_connect(comm)

    # connect
    nxslib.connect()
    # connect once agian
    nxslib.connect()

    assert nxslib.dev is not None
    for chan in range(nxslib.dev.chmax):
        assert nxslib.dev_channel_get(chan) is not None

    # disconnect
    nxslib.disconnect()
    # disconnect once agian
    nxslib.disconnect()

    assert nxslib.dev is None
    with pytest.raises(AssertionError):
        _ = nxslib.dev_channel_get(0)


def test_nxslib_stream():
    intf = DummyDev()
    parse = Parser()
    comm = CommHandler(intf, parse)
    nxslib = NxscopeHandler()

    nxslib.intf_connect(comm)

    # connect
    nxslib.connect()

    # start stream
    nxslib.stream_start()
    # start stream once again
    nxslib.stream_start()

    # stop stream
    nxslib.stream_stop()
    # stop stream once again
    nxslib.stream_stop()

    # subscribe to streams
    q0_0 = nxslib.stream_sub(0)
    q0_1 = nxslib.stream_sub(0)

    # disable channels
    comm.ch_disable_all()

    # start stream
    nxslib.stream_start()

    # channels disabled
    for ch in range(comm.dev.chmax):
        assert comm.ch_is_enabled(ch) is False

    # wait for data but channels no enabled
    with pytest.raises(queue.Empty):
        _ = q0_0.get(block=True, timeout=0.5)
    with pytest.raises(queue.Empty):
        _ = q0_1.get(block=True, timeout=0.5)

    # stop stream
    nxslib.stream_stop()

    # unsub from streams
    nxslib.stream_unsub(0, q0_0)
    nxslib.stream_unsub(0, q0_1)

    # configure channels
    nxslib.nxslib_channels_default_cfg()
    nxslib.nxslib_ch_enable([0])
    nxslib.nxslib_ch_divider([0], 1)

    # subscribe to streams
    q0_0 = nxslib.stream_sub(0)
    q0_1 = nxslib.stream_sub(0)

    # start stream
    nxslib.stream_start()

    # wait for data but channels no enabled
    data = q0_0.get(block=True, timeout=1)
    assert data
    data = q0_1.get(block=True, timeout=1)
    assert data

    # stop stream
    nxslib.stream_stop()

    # subscribe to streams
    q0_0 = nxslib.stream_sub(0)
    q0_1 = nxslib.stream_sub(0)

    # disconnect
    nxslib.disconnect()


def test_nxslib_channels_configure():
    intf = DummyDev()
    parse = Parser()
    comm = CommHandler(intf, parse)
    nxslib = NxscopeHandler()

    nxslib.intf_connect(comm)

    # connect
    nxslib.connect()

    # no configured channels at default
    assert nxslib.chanlist == []

    # configure channels
    nxslib.channels_configure([], [])
    nxslib.channels_configure([0], [1])
    nxslib.channels_configure([1], [2])
    nxslib.channels_configure([1, 2], [1, 1])
    nxslib.channels_configure([1, 2, 3], 1)
    nxslib.channels_configure([1, 2, 3], [1, 2, 3])
    nxslib.channels_configure("all", 4)

    # unsupported channel type
    with pytest.raises(TypeError):
        nxslib.channels_configure(None, 1)

    # unsupported channel string
    with pytest.raises(TypeError):
        nxslib.channels_configure("bal", 1)

    # unsupported channel
    with pytest.raises(TypeError):
        nxslib.channels_configure(256, 1)

    # channels len != div len
    with pytest.raises(TypeError):
        nxslib.channels_configure([1, 2, 3], [1, 2])

    # disconnect
    nxslib.disconnect()
