from nxslib.dev import Device, DeviceChannel, EDeviceChannelType
from nxslib.proto.iframe import EParseId, ICommFrame
from nxslib.proto.iparse import DParseFrame, EParseDataType
from nxslib.proto.parse import Parser


def test_nxslibparse_frame():
    # create parser
    parse = Parser()
    assert isinstance(parse, Parser)

    assert parse.frame is not None
    assert isinstance(parse.frame, ICommFrame)

    # valid start frame
    assert parse.frame_start(True) is not None

    # valid start frame
    assert parse.frame_start(False) is not None

    # valid cmninfo frame
    assert parse.frame_cmninfo() is not None

    # valid chinfo frame
    assert parse.frame_chinfo(1) is not None

    # valid enable frame
    assert parse.frame_enable((0, False), 3) is not None
    assert parse.frame_enable([False, True, False], 3) is not None
    assert parse.frame_enable([False, False, False], 3) is not None

    # valid div frame
    assert parse.frame_div((0, 0), 3) is not None
    assert parse.frame_div([2, 2, 0], 3) is not None
    assert parse.frame_div([3, 3, 3], 3) is not None


def test_nxslibparse_decode():
    parse = Parser()

    # cmn info
    assert parse.frame_cmninfo_decode(None) is None
    frame = DParseFrame(EParseId.CHINFO, b"\x00\x00\x00")
    assert parse.frame_cmninfo_decode(frame) is None
    frame = DParseFrame(EParseId.CMNINFO, b"\x00\x00\x00")
    assert parse.frame_cmninfo_decode(frame) is not None

    # ch info
    assert parse.frame_chinfo_decode(None, 1) is None
    frame = DParseFrame(EParseId.CMNINFO, b"\x00\x00\x00")
    assert parse.frame_chinfo_decode(frame, 1) is None
    frame = DParseFrame(EParseId.CHINFO, b"\x00\x00\x00\x00\x00\x00")
    assert parse.frame_chinfo_decode(frame, 1) is not None

    # ack frame
    assert parse.frame_ack_decode(None) is None
    frame = DParseFrame(EParseId.CMNINFO, b"\x00\x00\x00\x00")
    assert parse.frame_ack_decode(frame) is None
    frame = DParseFrame(EParseId.ACK, b"\x00\x00\x00\x00")
    assert parse.frame_ack_decode(frame) is not None
    frame = DParseFrame(EParseId.ACK, b"\x00\x00\x00\x01")
    assert parse.frame_ack_decode(frame) is not None


def test_nxslibparse_stream():
    parse = Parser()
    chans = [
        DeviceChannel(
            0, EDeviceChannelType.NONE.value, 0, "chan0", mlen=0, func=None
        ),
        DeviceChannel(
            1,
            EDeviceChannelType.UINT8.value,
            1,
            "chan1",
            mlen=0,
            func=None,
        ),
        DeviceChannel(
            2, EDeviceChannelType.NONE.value, 0, "chan2", mlen=1, func=None
        ),
        DeviceChannel(
            3, EDeviceChannelType.CHAR.value, 2, "chan3", mlen=1, func=None
        ),
        DeviceChannel(
            4, EDeviceChannelType.CHAR.value, 2, "chan4", mlen=0, func=None
        ),
    ]
    d = Device(5, 0b11, 0, chans)

    # invalid frame type
    data = b"\x00"
    frame = DParseFrame(EParseId.CMNINFO, None)
    assert parse.frame_stream_decode(frame, d) is None

    # no data
    data = b""
    frame = DParseFrame(EParseId.STREAM, data)
    assert parse.frame_stream_decode(frame, d) is None

    # no frame
    assert parse.frame_stream_decode(None, d) is None

    # no samples
    data = b"\x00"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples == []
    data = b"\x01"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 1
    assert sdata.samples == []

    # chan 0 sample
    data = b"\x00\x00"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 0
    assert sdata.samples[0].dtype == EParseDataType.NONE
    assert sdata.samples[0].vdim == 0
    assert sdata.samples[0].mlen == 0
    assert sdata.samples[0].data == ()
    assert sdata.samples[0].meta == ()

    # chan 1 sample
    data = b"\x00\x01\x01"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 1
    assert sdata.samples[0].dtype == EParseDataType.NUM
    assert sdata.samples[0].vdim == 1
    assert sdata.samples[0].mlen == 0
    assert sdata.samples[0].data == (1,)
    assert sdata.samples[0].meta == ()

    # chan 2 sample
    data = b"\x00\x02\x01"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 2
    assert sdata.samples[0].dtype == EParseDataType.NONE
    assert sdata.samples[0].vdim == 0
    assert sdata.samples[0].mlen == 1
    assert sdata.samples[0].data == ()
    assert sdata.samples[0].meta == (1,)

    # chan 3 sample
    data = b"\x00\x03a\x00\x01"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 3
    assert sdata.samples[0].dtype == EParseDataType.CHAR
    assert sdata.samples[0].vdim == 2
    assert sdata.samples[0].mlen == 1
    assert sdata.samples[0].data == ("a\x00",)
    assert sdata.samples[0].meta == (1,)

    # chan 4 sample
    data = b"\x00\x04a\x00"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 4
    assert sdata.samples[0].dtype == EParseDataType.CHAR
    assert sdata.samples[0].vdim == 2
    assert sdata.samples[0].mlen == 0
    assert sdata.samples[0].data == ("a\x00",)
    assert sdata.samples[0].meta == ()
