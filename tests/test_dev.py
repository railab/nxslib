import pytest  # type: ignore

from nxslib.dev import (
    DDeviceChannelData,
    Device,
    DeviceChannel,
    IDeviceChannelFunc,
)


class DevChannelFunc(IDeviceChannelFunc):
    _cntr = 0

    def reset(self):
        self._cntr = 0

    def get(self, cntr):
        ret = self._cntr
        self._cntr += 1
        return ret


def test_devchanneldata():
    data = DDeviceChannelData(0, 0, 0, "test")
    assert data.chan == 0
    assert data._type == 0
    assert data.dtype == 0
    assert data.vdim == 0
    assert data.name == "test"
    assert data.en is False
    assert data.div == 0
    assert data.mlen == 0
    assert data.critical is False
    assert data.type_res == 0
    assert data.is_valid is False
    assert data.is_numerical is False

    data = DDeviceChannelData(1, 0x82, 3, "test", True, 1, 8)
    assert data.chan == 1
    assert data._type == 0x82
    assert data.dtype == 2
    assert data.vdim == 3
    assert data.name == "test"
    assert data.en is True
    assert data.div == 1
    assert data.mlen == 8
    assert data.critical is True
    assert data.type_res == 0
    assert data.is_valid is True
    assert data.is_numerical is True


# test channel init
def test_nxsdevchannel_init():
    # func must be callable or None
    with pytest.raises(AssertionError):
        DeviceChannel(1, 2, 3, "chan0", func=1)

    ch = DeviceChannel(0, 0, 0, None, func=None)
    assert isinstance(ch, DeviceChannel)
    assert ch.chan == 0
    assert ch.dtype == 0
    assert ch.type_res == 0
    assert ch.vdim == 0
    assert ch.name == ""
    assert ch.en is False
    assert ch.div == 0
    assert ch.mlen == 0
    assert ch.data_get() is None

    ch = DeviceChannel(1, 1, 2, "chan0", en=True, div=1, mlen=4, func=None)
    assert isinstance(ch, DeviceChannel)
    assert ch.chan == 1
    assert ch.dtype == 1
    assert ch.type_res == 0
    assert ch.vdim == 2
    assert ch.name == "chan0"
    assert ch.en is True
    assert ch.div == 1
    assert ch.mlen == 4
    assert ch.data_get() is None

    ch = DeviceChannel(0, 1, 2, "func0", func=DevChannelFunc())
    assert isinstance(ch, DeviceChannel)
    assert ch.data_get() == 0


# test channel attrubutes
def test_nxsdevchannel_attributes():
    ch = DeviceChannel(0, 0, 0, None, func=None)
    assert isinstance(ch, DeviceChannel)
    assert ch.chan == 0
    assert ch.dtype == 0
    assert ch.type_res == 0
    assert ch.vdim == 0
    assert ch.name == ""
    assert ch.en is False
    assert ch.div == 0
    assert ch.mlen == 0
    assert ch.data_get() is None

    ch.en = False
    assert ch.en is False
    ch.en = True
    assert ch.en is True

    ch.div = 10
    assert ch.div == 10
    ch.div = 0
    assert ch.div == 0

    ch.mlen = 10
    assert ch.mlen == 10
    ch.mlen = 0
    assert ch.mlen == 0


# test channel data function
def test_nxsdevchannel_func():
    # no data function
    ch1 = DeviceChannel(0, 1, 2, "chan0", func=None)
    assert ch1.data_get() is None
    assert ch1.data_get() is None
    assert ch1.data_get() is None

    # simple data function (cntr + 1)
    ch2 = DeviceChannel(0, 1, 2, "chan0", func=DevChannelFunc())
    assert ch2.data_get() == 0
    assert ch2.data_get() == 1
    assert ch2.data_get() == 2
    assert ch2.data_get() == 3
    ch2.reset()
    assert ch2.data_get() == 0


# test dev init
def test_nxsdev_init():
    # channels must be defined
    with pytest.raises(AssertionError):
        d = Device(1, 0, 0, [])
    with pytest.raises(AssertionError):
        d = Device(1, 0, 0, [1])
    # the same channel ids
    with pytest.raises(AssertionError):
        d = Device(
            2,
            0,
            0,
            [
                DeviceChannel(0, 1, 2, "chan0", func=None),
                DeviceChannel(0, 1, 2, "chan1", func=None),
            ],
        )

    d = Device(0, 0, 0, [])
    assert isinstance(str(d), str)
    assert d.chmax == 0
    assert d.flags == 0
    assert d.rxpadding == 0
    assert d.div_supported is False
    assert d.ack_supported is False
    assert d.channels_en == []
    assert d.channels_div == []
    assert d.channel_get(0) is None
    assert d.channel_get(1) is None
    assert d.channel_get(2) is None

    d = Device(1, 0, 1, [DeviceChannel(0, 1, 2, "chan0", func=None)])
    assert isinstance(str(d), str)
    assert d.chmax == 1
    assert d.flags == 0
    assert d.rxpadding == 1
    assert d.div_supported is False
    assert d.ack_supported is False
    assert d.channels_en == [False]
    assert d.channels_div == [0]
    assert d.channel_get(0) is not None
    assert d.channel_get(1) is None
    assert d.channel_get(2) is None

    d = Device(
        2,
        0b11,
        0,
        [
            DeviceChannel(0, 1, 2, "chan0", func=None),
            DeviceChannel(1, 1, 2, "chan1", func=None),
        ],
    )
    assert isinstance(str(d), str)
    assert d.chmax == 2
    assert d.flags == 0b11
    assert d.rxpadding == 0
    assert d.div_supported is True
    assert d.ack_supported is True
    assert d.channels_en == [False, False]
    assert d.channels_div == [0, 0]
    assert d.channel_get(0) is not None
    assert d.channel_get(1) is not None
    assert d.channel_get(2) is None
