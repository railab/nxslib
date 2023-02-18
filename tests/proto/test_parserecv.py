import pytest  # type: ignore

from nxslib.dev import Device, DeviceChannel, EDeviceChannelType
from nxslib.proto.iframe import EParseId
from nxslib.proto.iparse import (
    DParseStreamData,
    DsfmtItem,
    EParseDataType,
    EParseIdSetFlags,
)
from nxslib.proto.iparserecv import ParseRecvCb
from nxslib.proto.parse import Parser
from nxslib.proto.parserecv import ParseRecv
from nxslib.proto.serialframe import SerialFrame


def cb_cmninfo(data):
    assert len(data) == 0


def cb_chinfo(data):
    assert len(data) == 1


def cb_enable(data):
    assert len(data) > 1


def cb_div(data):
    assert len(data) > 1


def cb_start(data):
    assert len(data) == 1


def test_nxslibparserecv_fames():
    # invalid recv_cb
    recv_cb = {}
    with pytest.raises(AssertionError):
        recv = ParseRecv(recv_cb, SerialFrame)

    recv_cb = {"test": cb_cmninfo}
    with pytest.raises(AssertionError):
        recv = ParseRecv(recv_cb, SerialFrame)

    recv_cb = ParseRecvCb(cb_cmninfo, cb_chinfo, cb_enable, cb_div, cb_start)
    recv = ParseRecv(recv_cb, SerialFrame)
    assert isinstance(recv, ParseRecv)

    # no data
    _bytes = None
    assert recv.recv_handle(_bytes) is None

    # not sufficient data
    _bytes = bytes([0x01])
    assert recv.recv_handle(_bytes) is None

    # not hdr data
    _bytes = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    assert recv.recv_handle(_bytes) is None

    # error in hdr
    _bytes = bytes([0x55, 0x04, 0x00, 0xFF, 0x00, 0x00])
    assert recv.recv_handle(_bytes) is None

    # invalid hdr len
    _bytes = bytes([0x00, 0x00, 0x55, 0x00, 0x00, 0x00])
    assert recv.recv_handle(_bytes) is None

    # create parser
    parser = Parser(SerialFrame)

    # valid cmninfo frame
    _bytes = parser.frame_cmninfo()
    assert recv.recv_handle(_bytes) is None

    # valid chinfo frame
    _bytes = parser.frame_chinfo(1)
    assert recv.recv_handle(_bytes) is None

    # valid enable frame
    _bytes = parser.frame_enable((0, False), 3)  # single
    assert recv.recv_handle(_bytes) is None
    _bytes = parser.frame_enable([False, True, False], 3)  # bulk
    assert recv.recv_handle(_bytes) is None
    _bytes = parser.frame_enable([False, False, False], 3)  # all
    assert recv.recv_handle(_bytes) is None

    # valid div frame
    _bytes = parser.frame_div((0, 0), 3)  # single
    assert recv.recv_handle(_bytes) is None
    _bytes = parser.frame_div([2, 2, 0], 3)  # bulk
    assert recv.recv_handle(_bytes) is None
    _bytes = parser.frame_div([3, 3, 3], 3)  # all
    assert recv.recv_handle(_bytes) is None

    # valid start frame
    _bytes = parser.frame_start(True)
    assert recv.recv_handle(_bytes) is None

    frame = SerialFrame()

    # invalid data
    _bytes = frame.frame_create(EParseId.CMNINFO, None)
    _bytes = list(_bytes)  # invalid footer
    _bytes[-1] = _bytes[-1] + 1
    _bytes = bytes(_bytes)
    assert recv.recv_handle(_bytes) is None
    _bytes = frame.frame_create(EParseId.CMNINFO, b"\x00")
    with pytest.raises(AssertionError):
        recv.recv_handle(_bytes)
    _bytes = frame.frame_create(EParseId.CHINFO, b"\x00\x00")
    with pytest.raises(AssertionError):
        recv.recv_handle(_bytes)
    _bytes = frame.frame_create(EParseId.ENABLE, None)
    with pytest.raises(AssertionError):
        recv.recv_handle(_bytes)
    _bytes = frame.frame_create(EParseId.DIV, None)
    with pytest.raises(AssertionError):
        recv.recv_handle(_bytes)
    _bytes = frame.frame_create(EParseId.START, None)
    with pytest.raises(AssertionError):
        recv.recv_handle(_bytes)
    _bytes = frame.frame_create(EParseId.STREAM, None)
    with pytest.raises(AssertionError):
        recv.recv_handle(_bytes)
    _bytes = frame.frame_create(EParseId.INVALID, None)
    with pytest.raises(AssertionError):
        recv.recv_handle(_bytes)


def test_nxslibparserecv_decode():
    recv_cb = ParseRecvCb(cb_cmninfo, cb_chinfo, cb_enable, cb_div, cb_start)
    recv = ParseRecv(recv_cb, SerialFrame)
    parser = Parser(SerialFrame)
    frame = SerialFrame()
    d = Device(
        3,
        0b11,
        0,
        [
            DeviceChannel(0, 1, 2, "chan0", func=None),
            DeviceChannel(1, 1, 2, "chan1", func=None),
            DeviceChannel(2, 1, 2, "chan2", func=None),
        ],
    )

    assert d.channels_en == [False, False, False]
    assert d.channels_div == [0, 0, 0]

    # valid enable frame
    _bytes = parser.frame_enable((0, False), 3)  # single
    assert recv.frame_enable_decode(_bytes[frame.hdr_len :], d) == [
        False,
        False,
        False,
    ]
    _bytes = parser.frame_enable([False, True, False], 3)  # bulk
    assert recv.frame_enable_decode(_bytes[frame.hdr_len :], d) == [
        False,
        True,
        False,
    ]
    _bytes = parser.frame_enable([False, False, False], 3)  # all
    assert recv.frame_enable_decode(_bytes[frame.hdr_len :], d) == [
        False,
        False,
        False,
    ]

    # valid div frame
    _bytes = parser.frame_div((0, 0), 3)  # single
    assert recv.frame_div_decode(_bytes[frame.hdr_len :], d) == [0, 0, 0]
    _bytes = parser.frame_div([2, 2, 0], 3)  # bulk
    assert recv.frame_div_decode(_bytes[frame.hdr_len :], d) == [2, 2, 0]
    _bytes = parser.frame_div([3, 3, 3], 3)  # all
    assert recv.frame_div_decode(_bytes[frame.hdr_len :], d) == [3, 3, 3]

    # invalid set types
    _bytes = bytes([EParseIdSetFlags.INVALID, 0, 0])
    with pytest.raises(ValueError):
        recv.frame_enable_decode(_bytes, d)
    _bytes = bytes([EParseIdSetFlags.INVALID, 0, 0])
    with pytest.raises(ValueError):
        recv.frame_div_decode(_bytes, d)


def test_nxslibparserecv_encode():
    recv_cb = ParseRecvCb(cb_cmninfo, cb_chinfo, cb_enable, cb_div, cb_start)
    recv = ParseRecv(recv_cb, SerialFrame)

    # empty data
    samples = []
    assert recv.frame_stream_encode(samples) is None

    # samples with vect but no meta
    samples = [DParseStreamData(0, 2, 1, 0, (1,), ())]
    assert recv.frame_stream_encode(samples) is not None
    samples = [
        DParseStreamData(0, 2, 1, 0, (1,), ()),
        DParseStreamData(0, 2, 1, 0, (2,), ()),
    ]
    assert recv.frame_stream_encode(samples) is not None

    # samples with meta but no vect
    samples = [DParseStreamData(0, 1, 0, 1, (), (1,))]
    assert recv.frame_stream_encode(samples) is not None
    samples = [
        DParseStreamData(0, 1, 0, 1, (), (1,)),
        DParseStreamData(0, 1, 0, 1, (), (1,)),
    ]
    assert recv.frame_stream_encode(samples) is not None

    # samples with no vect and no meta
    samples = [DParseStreamData(0, 1, 0, 0, (), ())]
    assert recv.frame_stream_encode(samples) is None
    samples = [
        DParseStreamData(0, 1, 0, 0, (), ()),
        DParseStreamData(0, 1, 0, 0, (), ()),
    ]
    assert recv.frame_stream_encode(samples) is None


def test_nxslibparserecv_encode_user():
    recv_cb = ParseRecvCb(cb_cmninfo, cb_chinfo, cb_enable, cb_div, cb_start)
    user = {
        EDeviceChannelType.USER1.value: DsfmtItem(
            1, "iiii", None, EParseDataType.NUM, None, True
        ),
        EDeviceChannelType.USER2.value: DsfmtItem(
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
    recv = ParseRecv(recv_cb, SerialFrame, user)

    # empty data
    samples = []
    assert recv.frame_stream_encode(samples) is None

    # samples for USER1
    samples = [DParseStreamData(0, 2, 1, 0, (1,), ())]
    assert recv.frame_stream_encode(samples) is not None
    samples = [
        DParseStreamData(
            0, EDeviceChannelType.USER1.value, 16, 0, (1, 2, 3, 4), ()
        ),
        DParseStreamData(
            0, EDeviceChannelType.USER2.value, 10, 0, (b"c", b"c", 1, 2), ()
        ),
    ]
    assert recv.frame_stream_encode(samples) is not None
