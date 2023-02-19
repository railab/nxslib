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
    nxslib.stream_unsub(q0_0)
    nxslib.stream_unsub(q0_1)

    # configure channels
    nxslib.channels_default_cfg()
    # enable/disable
    nxslib.ch_enable([0])
    nxslib.ch_disable([0])
    nxslib.ch_enable([0])
    # divider
    nxslib.ch_divider([0], 1)

    # subscribe to streams
    q0_0 = nxslib.stream_sub(0)
    q0_1 = nxslib.stream_sub(0)

    # start stream
    nxslib.stream_start()

    # wait for data but channels no enabled
    data = q0_0.get(block=True, timeout=1)
    print(data)
    print(data[0])
    assert data
    data = q0_1.get(block=True, timeout=1)
    print(data)
    print(data[0])
    assert data

    # stop stream
    nxslib.stream_stop()

    # subscribe to streams
    nxslib.stream_unsub(q0_0)
    nxslib.stream_unsub(q0_1)

    # disconnect
    nxslib.disconnect()


def test_nxslib_channels_runtime():
    intf = DummyDev()
    parse = Parser()
    comm = CommHandler(intf, parse)
    nxslib = NxscopeHandler()

    nxslib.intf_connect(comm)

    # connect
    nxslib.connect()

    # force default state
    nxslib.channels_default_cfg(writenow=True)

    # get device handlers
    dev0 = nxslib.dev_channel_get(0)
    dev1 = nxslib.dev_channel_get(1)
    dev2 = nxslib.dev_channel_get(2)

    assert dev0.en is False
    assert dev1.en is False
    assert dev2.en is False
    assert dev0.div == 0
    assert dev1.div == 0
    assert dev2.div == 0

    # subscribe to streams
    q0 = nxslib.stream_sub(0)
    q1 = nxslib.stream_sub(1)
    q2 = nxslib.stream_sub(2)

    nxslib.channels_default_cfg(writenow=True)

    # start stream without channels configured
    nxslib.stream_start()

    nxslib.channels_default_cfg(writenow=True)

    assert dev0.en is False
    assert dev1.en is False
    assert dev2.en is False
    assert dev0.div == 0
    assert dev1.div == 0
    assert dev2.div == 0

    # wait for data but channels no enabled
    with pytest.raises(queue.Empty):
        _ = q0.get(block=True, timeout=0.5)
    with pytest.raises(queue.Empty):
        _ = q1.get(block=True, timeout=0.5)
    with pytest.raises(queue.Empty):
        _ = q2.get(block=True, timeout=0.5)

    # reconfig
    nxslib.ch_enable(0, writenow=True)
    nxslib.ch_divider(0, 1, writenow=True)

    assert dev0.en is True
    assert dev1.en is False
    assert dev2.en is False
    assert dev0.div == 1
    assert dev1.div == 0
    assert dev2.div == 0

    # wait for data
    data = q0.get(block=True, timeout=0.5)
    assert data
    with pytest.raises(queue.Empty):
        _ = q1.get(block=True, timeout=0.5)
    with pytest.raises(queue.Empty):
        _ = q2.get(block=True, timeout=0.5)

    # reconfig
    nxslib.ch_enable(1, writenow=True)
    nxslib.ch_divider(1, 5, writenow=True)

    assert dev0.en is True
    assert dev1.en is True
    assert dev2.en is False
    assert dev0.div == 1
    assert dev1.div == 5
    assert dev2.div == 0

    # wait for data
    data = q0.get(block=True, timeout=0.5)
    assert data
    data = q1.get(block=True, timeout=0.5)
    assert data
    with pytest.raises(queue.Empty):
        _ = q2.get(block=True, timeout=0.5)

    # reconfig
    nxslib.ch_disable(0, writenow=True)
    nxslib.ch_divider(0, 0, writenow=True)
    nxslib.ch_enable(1, writenow=True)
    nxslib.ch_divider(1, 10, writenow=True)

    assert dev0.en is False
    assert dev1.en is True
    assert dev2.en is False
    assert dev0.div == 0
    assert dev1.div == 10
    assert dev2.div == 0

    nxslib.ch_enable(0, writenow=True)
    nxslib.ch_divider(0, 5, writenow=True)
    nxslib.ch_enable(1, writenow=True)
    nxslib.ch_divider(1, 5, writenow=True)
    nxslib.ch_enable(2, writenow=True)
    nxslib.ch_divider(2, 5, writenow=True)

    assert dev0.en is True
    assert dev1.en is True
    assert dev2.en is True
    assert dev0.div == 5
    assert dev1.div == 5
    assert dev2.div == 5

    # stop stream
    nxslib.stream_stop()

    nxslib.stream_unsub(q0)
    nxslib.stream_unsub(q1)
    nxslib.stream_unsub(q2)

    # disconnect
    nxslib.disconnect()
