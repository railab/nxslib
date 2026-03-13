import numpy as np

from nxslib.dev import Device, DeviceChannel, EDeviceChannelType
from nxslib.proto.iframe import DParseFrame, EParseId, ICommFrame
from nxslib.proto.iparse import DsfmtItem, EParseDataType
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


def test_nxslibparse_stream_user():
    user = {
        EDeviceChannelType.USER1.value: DsfmtItem(
            1, "iiii", None, EParseDataType.NUM, None, True
        ),
        EDeviceChannelType.USER2.value: DsfmtItem(
            1, "ccc", None, EParseDataType.CHAR, None, True
        ),
        EDeviceChannelType.USER3.value: DsfmtItem(
            1,
            "ccii",
            None,
            EParseDataType.COMPLEX,
            [
                EParseDataType.CHAR,
                EParseDataType.CHAR,
                EParseDataType.NUM,
                EParseDataType.NUM,
            ],
            True,
        ),
    }
    parse = Parser(user_types=user)
    chans = [
        DeviceChannel(
            0, EDeviceChannelType.USER1.value, 16, "chan0", mlen=0, func=None
        ),
        DeviceChannel(
            1,
            EDeviceChannelType.USER2.value,
            3,
            "chan1",
            mlen=0,
            func=None,
        ),
        DeviceChannel(
            2, EDeviceChannelType.USER3.value, 10, "chan3", mlen=0, func=None
        ),
        DeviceChannel(
            3, EDeviceChannelType.USER3.value, 10, "chan2", mlen=1, func=None
        ),
    ]
    d = Device(4, 0b11, 0, chans)

    # chan 0 sample

    data = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    data += b"\x00\x00\x00\x00"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 0
    assert sdata.samples[0].dtype == EParseDataType.NUM
    assert sdata.samples[0].vdim == 16
    assert sdata.samples[0].mlen == 0
    assert sdata.samples[0].data == (0, 0, 0, 0)
    assert sdata.samples[0].meta == ()

    # chan 1 sample
    data = b"\x00\x01abc"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 1
    assert sdata.samples[0].dtype == EParseDataType.CHAR
    assert sdata.samples[0].vdim == 3
    assert sdata.samples[0].mlen == 0
    assert sdata.samples[0].data == (b"a", b"b", b"c")
    assert sdata.samples[0].meta == ()

    # chan 2 sample
    data = b"\x00\x02ab\x00\x00\x00\x00\x00\x00\x00\x00"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 2
    assert sdata.samples[0].dtype == EParseDataType.COMPLEX
    assert sdata.samples[0].vdim == 10
    assert sdata.samples[0].mlen == 0
    assert sdata.samples[0].data == (b"a", b"b", 0, 0)
    assert sdata.samples[0].meta == ()

    # chan 3 sample
    data = b"\x00\x03ab\x00\x00\x00\x00\x00\x00\x00\x00\x01"
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode(frame, d)
    assert sdata.flags == 0
    assert sdata.samples[0].chan == 3
    assert sdata.samples[0].dtype == EParseDataType.COMPLEX
    assert sdata.samples[0].vdim == 10
    assert sdata.samples[0].mlen == 1
    assert sdata.samples[0].data == (b"a", b"b", 0, 0)
    assert sdata.samples[0].meta == (1,)


def test_nxslibparse_stream_numpy():
    parse = Parser()
    chans = [
        DeviceChannel(
            0,
            EDeviceChannelType.INT16.value,
            1,
            "chan0",
            mlen=4,
            func=None,
        ),
        DeviceChannel(
            1,
            EDeviceChannelType.INT16.value,
            1,
            "chan1",
            mlen=4,
            func=None,
        ),
    ]
    dev = Device(2, 0, 0, chans)

    # flags=1, then 3 interleaved samples with metadata
    # ch0:10 meta1, ch1:20 meta2, ch0:30 meta3
    data = (
        b"\x01"
        + b"\x00\x0a\x00\x01\x00\x00\x00"
        + b"\x01\x14\x00\x02\x00\x00\x00"
        + b"\x00\x1e\x00\x03\x00\x00\x00"
    )
    frame = DParseFrame(EParseId.STREAM, data)

    sdata = parse.frame_stream_decode_numpy(frame, dev)
    assert sdata is not None
    assert sdata.flags == 1
    assert len(sdata.blocks) == 2

    b0 = sdata.blocks[0]
    assert b0.chan == 0
    assert b0.dtype == EParseDataType.NUM
    assert b0.data.shape == (2, 1)
    assert np.array_equal(b0.data[:, 0], np.array([10, 30], dtype=np.int16))
    assert b0.meta is not None
    assert np.array_equal(b0.meta[:, 0], np.array([1, 3], dtype=np.uint32))

    b1 = sdata.blocks[1]
    assert b1.chan == 1
    assert b1.dtype == EParseDataType.NUM
    assert b1.data.shape == (1, 1)
    assert np.array_equal(b1.data[:, 0], np.array([20], dtype=np.int16))
    assert b1.meta is not None
    assert np.array_equal(b1.meta[:, 0], np.array([2], dtype=np.uint32))


def test_nxslibparse_stream_numpy_guard_branches():
    parse = Parser()
    chan = DeviceChannel(
        0,
        EDeviceChannelType.INT16.value,
        1,
        "chan0",
        mlen=0,
        func=None,
    )
    dev = Device(1, 0, 0, [chan])

    assert parse.frame_stream_decode_numpy(None, dev) is None
    assert (
        parse.frame_stream_decode_numpy(
            DParseFrame(EParseId.CMNINFO, b"\x00"), dev
        )
        is None
    )
    assert (
        parse.frame_stream_decode_numpy(DParseFrame(EParseId.STREAM, b""), dev)
        is None
    )


def test_nxslibparse_stream_numpy_scaled_and_object_paths():
    parse = Parser()
    chans = [
        DeviceChannel(
            0,
            EDeviceChannelType.UB8.value,
            1,
            "scaled",
            mlen=8,
            func=None,
        ),
        DeviceChannel(
            1,
            EDeviceChannelType.CHAR.value,
            2,
            "char",
            mlen=3,
            func=None,
        ),
    ]
    dev = Device(2, 0, 0, chans)

    data = (
        b"\x00"
        + b"\x00\x80\x01\x01\x00\x00\x00\x00\x00\x00\x00"
        + b"\x01ab\x11\x22\x33"
    )
    frame = DParseFrame(EParseId.STREAM, data)
    sdata = parse.frame_stream_decode_numpy(frame, dev)

    assert sdata is not None
    assert len(sdata.blocks) == 2

    scaled = sdata.blocks[0]
    assert scaled.data.dtype == np.float64
    assert scaled.meta is not None
    assert scaled.meta.dtype == np.uint64
    assert np.isclose(float(scaled.data[0, 0]), 1.5)
    assert int(scaled.meta[0, 0]) == 1

    chars = sdata.blocks[1]
    assert chars.data.dtype == np.object_
    assert chars.meta is not None
    assert chars.meta.dtype == np.uint8
    assert chars.data[0, 0] == "ab"
    assert np.array_equal(
        chars.meta[0, :],
        np.array([0x11, 0x22, 0x33], dtype=np.uint8),
    )


def test_nxslibparse_stream_numpy_object_path_zero_vdim():
    parse = Parser()
    chan = DeviceChannel(
        0,
        EDeviceChannelType.NONE.value,
        0,
        "none",
        mlen=0,
        func=None,
    )
    dev = Device(1, 0, 0, [chan])
    frame = DParseFrame(EParseId.STREAM, b"\x00\x00")
    sdata = parse.frame_stream_decode_numpy(frame, dev)
    assert sdata is not None
    assert len(sdata.blocks) == 1
    block = sdata.blocks[0]
    assert block.data.shape == (1, 0)
