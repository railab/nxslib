from nxslib.dev import (
    DDeviceChannelFuncData,
    DeviceChannel,
    EDeviceChannelType,
)
from nxslib.intf.dummy import (
    ChannelFunc0,
    ChannelFunc1,
    ChannelFunc2,
    ChannelFunc3,
    ChannelFunc4,
    ChannelFunc5,
    ChannelFunc6,
    ChannelFunc7,
    ChannelFunc8,
    ChannelFunc9,
    DummyDev,
)
from nxslib.intf.iintf import ICommInterface


def test_nxslibdummy_init():
    # default dummy
    d = DummyDev()
    assert isinstance(d, DummyDev)
    assert isinstance(d, ICommInterface)

    # empty dev
    d = DummyDev(0, 0, 0, [])
    assert isinstance(d, DummyDev)
    d = DummyDev(0, 0, 0, None)
    assert isinstance(d, DummyDev)

    # custom channels
    d = DummyDev(1, 0, [DeviceChannel(0, 1, 0, "")])
    assert isinstance(d, DummyDev)

    # stop without start
    d.stop()

    # write padding
    d.drop_all()
    d.start()
    assert d.read() == b""

    d.write(b"aaaa")
    d.stop()


def test_dummy_channelfunc():  # noqa: C901
    c = ChannelFunc0()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc1()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc2()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(3003):
        _ = c.get(x)

    c = ChannelFunc3()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc4()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc5()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc6()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc7()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc8()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc9()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)


def test_dummy_divider_affects_stream_rate():
    channel = DeviceChannel(
        chan=0,
        _type=EDeviceChannelType.FLOAT.value,
        vdim=1,
        name="chan0",
        en=True,
        div=0,
        func=ChannelFunc0(),
    )
    dev = DummyDev(chmax=1, channels=[channel], stream_snum=1)

    full_rate = dev._stream_data_get(20)
    assert len(full_rate) == 20

    channel.data.div = 4
    dev._div_counters = [0]
    reduced_rate = dev._stream_data_get(20)
    assert len(reduced_rate) == 4
