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
    ch = DDeviceChannelData(0, 0, 0, "test")
    assert ch.chan == 0
    assert ch._type == 0
    assert ch.dtype == 0
    assert ch.vdim == 0
    assert ch.name == "test"
    assert ch.en is False
    assert ch.div == 0
    assert ch.mlen == 0
    assert ch.critical is False
    assert ch.type_res == 0
    assert ch.is_valid is False
    assert ch.is_numerical is False

    ch = DDeviceChannelData(1, 0x82, 3, "test", True, 1, 8)
    assert ch.chan == 1
    assert ch._type == 0x82
    assert ch.dtype == 2
    assert ch.vdim == 3
    assert ch.name == "test"
    assert ch.en is True
    assert ch.div == 1
    assert ch.mlen == 8
    assert ch.critical is True
    assert ch.type_res == 0
    assert ch.is_valid is True
    assert ch.is_numerical is True

    with pytest.raises(TypeError):
        ch.chan = 1
    with pytest.raises(TypeError):
        ch._type = 1
    with pytest.raises(TypeError):
        ch._dtype = 1
    with pytest.raises(TypeError):
        ch.vdim = 1
    with pytest.raises(TypeError):
        ch.name = "yolo"
    with pytest.raises(TypeError):
        ch.mlen = "yolo"

    ch.en = True
    ch.en = False
    ch.div = 10
    ch.div = 1


# test channel init
def test_nxsdevchannel_init():
    ch = DeviceChannel(0, 0, 0, None, func=None)
    assert isinstance(ch, DeviceChannel)
    assert ch.data.chan == 0
    assert ch.data.dtype == 0
    assert ch.data.type_res == 0
    assert ch.data.vdim == 0
    assert ch.data.name == ""
    assert ch.data.en is False
    assert ch.data.div == 0
    assert ch.data.mlen == 0
    assert ch.data_get() is None

    ch = DeviceChannel(1, 1, 2, "chan0", en=True, div=1, mlen=4, func=None)
    assert isinstance(ch, DeviceChannel)
    assert ch.data.chan == 1
    assert ch.data.dtype == 1
    assert ch.data.type_res == 0
    assert ch.data.vdim == 2
    assert ch.data.name == "chan0"
    assert ch.data.en is True
    assert ch.data.div == 1
    assert ch.data.mlen == 4
    assert ch.data_get() is None

    ch = DeviceChannel(0, 1, 2, "func0", func=DevChannelFunc())
    assert isinstance(ch, DeviceChannel)
    assert ch.data_get() == 0


# test channel attrubutes
def test_nxsdevchannel_attributes():
    ch = DeviceChannel(0, 0, 0, None, func=None)
    assert isinstance(ch, DeviceChannel)
    assert ch.data.chan == 0
    assert ch.data.dtype == 0
    assert ch.data.type_res == 0
    assert ch.data.vdim == 0
    assert ch.data.name == ""
    assert ch.data.en is False
    assert ch.data.div == 0
    assert ch.data.mlen == 0
    assert ch.data_get() is None

    ch.data.en = False
    assert ch.data.en is False
    ch.data.en = True
    assert ch.data.en is True

    ch.data.div = 10
    assert ch.data.div == 10
    ch.data.div = 0
    assert ch.data.div == 0

    with pytest.raises(TypeError):
        ch.data.mlen = 10
    with pytest.raises(TypeError):
        ch.data.chan = 10
    with pytest.raises(TypeError):
        ch.data._type = 10
    with pytest.raises(TypeError):
        ch.data.vdim = 10
    with pytest.raises(TypeError):
        ch.data.name = 10
    with pytest.raises(TypeError):
        ch.data.mlen = 10


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
    assert d.data.chmax == 0
    assert d.data.flags == 0
    assert d.data.rxpadding == 0
    assert d.data.div_supported is False
    assert d.data.ack_supported is False
    assert d.channels_en == []
    assert d.channels_div == []
    assert d.channel_get(0) is None
    assert d.channel_get(1) is None
    assert d.channel_get(2) is None

    d = Device(1, 0, 1, [DeviceChannel(0, 1, 2, "chan0", func=None)])
    assert isinstance(str(d), str)
    assert d.data.chmax == 1
    assert d.data.flags == 0
    assert d.data.rxpadding == 1
    assert d.data.div_supported is False
    assert d.data.ack_supported is False
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
    assert d.data.chmax == 2
    assert d.data.flags == 0b11
    assert d.data.rxpadding == 0
    assert d.data.div_supported is True
    assert d.data.ack_supported is True
    assert d.channels_en == [False, False]
    assert d.channels_div == [0, 0]
    assert d.channel_get(0) is not None
    assert d.channel_get(1) is not None
    assert d.channel_get(2) is None

    with pytest.raises(TypeError):
        d.data.chmax = 10
    with pytest.raises(TypeError):
        d.data.flags = 1
    with pytest.raises(TypeError):
        d.data.rxpadding = 1
