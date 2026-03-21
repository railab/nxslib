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
    ChannelFunc10,
    ChannelFunc11,
    ChannelFunc12,
    ChannelFunc13,
    ChannelFunc14,
    ChannelFunc15,
    ChannelFunc16,
    ChannelFunc17,
    ChannelFunc18,
    ChannelFunc19,
    ChannelFunc20,
    ChannelFunc21,
    ChannelFunc22,
    ChannelFunc23,
    ChannelFunc24,
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

    c = ChannelFunc10()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc11()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc12()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc13()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc14()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc15()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc16()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc17()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc18()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc19()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc20()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc21()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc22()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc23()
    c.reset()
    assert isinstance(c.get(0), DDeviceChannelFuncData)
    for x in range(1001):
        _ = c.get(x)

    c = ChannelFunc24()
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


def test_dummy_special_channels_are_deterministic():
    c_fft = ChannelFunc10()
    c_hist = ChannelFunc12()
    c_bimodal = ChannelFunc13()
    c_xy = ChannelFunc14()
    c_polar = ChannelFunc15()

    c_fft.reset()
    c_hist.reset()
    c_bimodal.reset()
    c_xy.reset()
    c_polar.reset()

    fft_first = [
        c_fft.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]
    hist_first = [
        c_hist.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]
    bimodal_first = [
        c_bimodal.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]
    xy_first = [c_xy.get(i).data for i in range(8)]  # type: ignore[union-attr]
    polar_first = [
        c_polar.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]

    c_fft.reset()
    c_hist.reset()
    c_bimodal.reset()
    c_xy.reset()
    c_polar.reset()

    fft_second = [
        c_fft.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]
    hist_second = [
        c_hist.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]
    bimodal_second = [
        c_bimodal.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]
    xy_second = [
        c_xy.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]
    polar_second = [
        c_polar.get(i).data for i in range(8)
    ]  # type: ignore[union-attr]

    assert fft_first == fft_second
    assert hist_first == hist_second
    assert bimodal_first == bimodal_second
    assert xy_first == xy_second
    assert polar_first == polar_second


def test_dummy_hist_bimodal_crosses_zero():
    c = ChannelFunc13()
    c.reset()
    vals = [c.get(i).data[0] for i in range(20)]  # type: ignore[union-attr]
    assert min(vals) < 0.0
    assert max(vals) > 0.0


def test_dummy_xy_channel_is_2d_and_bounded():
    c = ChannelFunc14()
    c.reset()
    vals = [c.get(i).data for i in range(30)]  # type: ignore[union-attr]
    assert all(len(v) == 2 for v in vals)
    assert all(-1.0 <= v[0] <= 1.0 for v in vals)
    assert all(-1.0 <= v[1] <= 1.0 for v in vals)


def test_dummy_polar_channel_ranges():
    c = ChannelFunc15()
    c.reset()
    vals = [c.get(i).data for i in range(30)]  # type: ignore[union-attr]
    assert all(len(v) == 2 for v in vals)
    assert all(0.0 <= v[0] <= 2.0 * 3.141592653589793 for v in vals)
    assert all(v[1] > 0.0 for v in vals)


def test_dummy_trigger_channels_smoke():
    c_up = ChannelFunc16()
    c_down = ChannelFunc17()
    c_sq = ChannelFunc18()
    c_sparse = ChannelFunc19()
    c_up.reset()
    c_down.reset()
    c_sq.reset()
    c_sparse.reset()

    assert isinstance(c_up.get(0), DDeviceChannelFuncData)
    assert isinstance(c_down.get(0), DDeviceChannelFuncData)
    assert isinstance(c_sq.get(0), DDeviceChannelFuncData)
    assert isinstance(c_sparse.get(0), DDeviceChannelFuncData)
