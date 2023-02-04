import pytest  # type: ignore

from nxslib.proto.iframe import EParseError, ICommFrame
from nxslib.proto.protoframe import ProtoFrame


def test_nxslibproto_init():
    proto = ProtoFrame()
    assert isinstance(proto, ProtoFrame)
    assert isinstance(proto, ICommFrame)

    # create frame - invalid id size
    with pytest.raises(ValueError):
        _ = proto.frame_create(2500, None)

    # no data
    _bytes = bytes([0x55, 0x4, 0x00])
    hdr = proto.hdr_decode(_bytes)
    assert hdr.err is EParseError.HDR

    # no data
    _bytes = None
    hdr = proto.hdr_decode(_bytes)
    assert hdr.err is EParseError.HDR

    # no data
    _bytes = b""
    hdr = proto.hdr_decode(_bytes)
    assert hdr.err is EParseError.HDR

    # valid hdr
    _bytes = bytes([0x55, 0x4, 0x00, 0x00])
    hdr = proto.hdr_decode(_bytes)
    assert hdr.flen == 4
    assert hdr.fid == 0
    assert hdr.err is EParseError.NOERR

    # create frame - no data
    _id = 1
    data = None
    frame_encoded = proto.frame_create(_id, data)
    # decode frame
    frame_decoded = proto.frame_decode(frame_encoded)
    assert frame_decoded.fid == _id
    assert frame_decoded.data == b""
    assert hdr.err is EParseError.NOERR

    # create frame - no data
    _id = 1
    data = b""
    frame_encoded = proto.frame_create(_id, data)
    # decode frame
    frame_decoded = proto.frame_decode(frame_encoded)
    assert frame_decoded.fid == _id
    assert frame_decoded.data == b""
    assert hdr.err is EParseError.NOERR

    # create frame - some data
    _id = 1
    data = b"abblllaa"
    frame_encoded = proto.frame_create(_id, data)
    # decode frame
    frame_decoded = proto.frame_decode(frame_encoded)
    assert frame_decoded.fid == _id
    assert frame_decoded.data == data
    assert hdr.err is EParseError.NOERR

    # create frame - invalid id
    _id = 200
    data = b"abblllaa"
    frame_encoded = proto.frame_create(_id, data)
    frame_decoded = proto.frame_decode(frame_encoded)
    assert frame_decoded.err is EParseError.HDR

    _id = 1
    data = b"abblllaa"

    # invalid crc
    frame_encoded = proto.frame_create(_id, data)
    frame_encoded = list(frame_encoded)
    frame_encoded[-1] = 0xFF
    frame_encoded = bytes(frame_encoded)
    frame_decoded = proto.frame_decode(frame_encoded)
    assert frame_decoded.err is EParseError.FOOT

    # no crc
    frame_encoded = proto.frame_create(_id, data)
    frame_encoded = list(frame_encoded)
    frame_encoded = frame_encoded[:-2]
    frame_encoded = bytes(frame_encoded)
    frame_decoded = proto.frame_decode(frame_encoded)
    assert frame_decoded.err is EParseError.FOOT

    # invalid sof
    frame_encoded = proto.frame_create(_id, data)
    frame_encoded = list(frame_encoded)
    frame_encoded[0] = 0x00
    frame_encoded = bytes(frame_encoded)
    frame_decoded = proto.frame_decode(frame_encoded)
    assert frame_decoded.err is EParseError.HDR
