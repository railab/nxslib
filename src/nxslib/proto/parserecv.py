"""Module containing the NxScope receiver protocol logic."""

import struct
from typing import TYPE_CHECKING, Any

from nxslib.proto.iframe import EParseError, EParseId, ICommFrame
from nxslib.proto.iparse import (
    DParseStreamData,
    DsfmtItem,
    EParseDataType,
    EParseIdSetFlags,
    dsfmt_get,
    msfmt_get,
)
from nxslib.proto.iparserecv import ICommParseRecv, ParseRecvCb
from nxslib.proto.serialframe import SerialFrame

if TYPE_CHECKING:
    from nxslib.dev import Device, DeviceChannel

###############################################################################
# Class: ParseRecv
###############################################################################


class ParseRecv(ICommParseRecv):
    """A class used to a represent nxslib receiver parser."""

    def __init__(
        self,
        cb: ParseRecvCb,
        frame: type[ICommFrame] = SerialFrame,
        user_types: dict[int, DsfmtItem] | None = None,
    ):
        """Initialize the receiver side parser.

        :param cb: recevier callbacks
        :param frame: instance of the frame parser
        """
        self._recv_cb = cb
        self._frame = frame()
        self._user_types = user_types

    def _cmninfo_data_encode(self, dev: "Device") -> bytes:
        """Encode cmninfo frame data."""
        _bytes = b""

        # general info
        _bytes = struct.pack(
            "BBB", dev.data.chmax, dev.data.flags, dev.data.rxpadding
        )

        return _bytes

    def _chinfo_data_encode(self, chan: "DeviceChannel") -> bytes:
        """Encode info frame data."""
        _bytes = b""

        # chan info
        nlen = len(chan.data.name)
        _bytes += struct.pack(
            f"?BBBB{nlen}s",
            chan.data.en,
            chan.data.dtype,
            chan.data.vdim,
            chan.data.div,
            chan.data.mlen,
            bytes(chan.data.name, "utf-8"),
        )

        return _bytes

    def _stream_bytes_get(
        self, decode: DsfmtItem, sample: DParseStreamData
    ) -> bytes:
        # pack data - always as little-endian
        fmt = "<" + "b"
        if sample.vdim:
            if not decode.user:
                fmt += str(sample.vdim) + decode.dsfmt
            else:
                # NxScope compatibility:
                #   ignore vdim and use format string only
                fmt += decode.dsfmt

        if decode.dtype == EParseDataType.NUM:
            if decode.scale:
                # scale numeric data
                vect_scale_l = [x * decode.scale for x in sample.data]
            else:
                # not scaled
                vect_scale_l = list(sample.data)
            _bytes = struct.pack(fmt, sample.chan, *vect_scale_l)
        elif decode.dtype == EParseDataType.CHAR:
            # string data
            vect_scale_t = (bytes(sample.data[0], "utf"),)
            _bytes = struct.pack(fmt, sample.chan, *vect_scale_t)
        elif decode.dtype is EParseDataType.NONE:
            # no data - encode channel num
            _bytes = struct.pack(fmt, sample.chan)
        else:
            assert decode.dtype is EParseDataType.COMPLEX
            _bytes = struct.pack(fmt, sample.chan, *sample.data)

        return _bytes

    def _stream_data_encode(
        self, data: list[DParseStreamData]
    ) -> bytes | None:
        """Encode stream frame data."""
        flags = 0
        _bytes = b""

        # pack flags
        _bytes += struct.pack("b", flags)

        # pack samples
        cntr = 0
        for sample in data:
            # next sample if no data and no meta
            if not sample.data and not sample.meta:
                continue

            # sample data included
            cntr += 1

            # sample format
            decode = dsfmt_get(sample.dtype, self._user_types)

            # meta format
            msfmt = msfmt_get(sample.mlen)

            # get bytes
            _bytes += self._stream_bytes_get(decode, sample)

            # add metadata
            if len(msfmt) > 0:
                _bytes += struct.pack(msfmt, *sample.meta)

        # do not return bytes if no sample data
        if cntr == 0:
            return None

        return _bytes

    def _recv_cb_cmninfo(self, data: bytes) -> None:
        """Handle recv cmninfo request."""
        assert len(data) == 0
        self._recv_cb.cmninfo(data)

    def _recv_cb_chinfo(self, data: bytes) -> None:
        """Handle recv chinfo request."""
        assert len(data) == 1
        self._recv_cb.chinfo(data)

    def _recv_cb_enable(self, data: bytes) -> None:
        """Handle recv enable request."""
        assert len(data) != 0
        self._recv_cb.enable(data)

    def _recv_cb_div(self, data: bytes) -> None:
        """Handle recv div request."""
        assert len(data) != 0
        self._recv_cb.div(data)

    def _recv_cb_start(self, data: bytes) -> None:
        """Handle recv start request."""
        assert len(data) == 1
        self._recv_cb.start(data)

    def _recv_cb_handle(self, fid: EParseId, fdata: bytes) -> None:
        # STREAM frames are not accepted here
        if fid == EParseId.CMNINFO:
            self._recv_cb_cmninfo(fdata)
        elif fid == EParseId.CHINFO:
            self._recv_cb_chinfo(fdata)
        elif fid == EParseId.START:
            self._recv_cb_start(fdata)
        elif fid == EParseId.ENABLE:
            self._recv_cb_enable(fdata)
        elif fid == EParseId.DIV:
            self._recv_cb_div(fdata)
        else:
            raise AssertionError

    def frame_start_decode(self, data: bytes) -> Any:
        """Hecode start frame."""
        return struct.unpack("?", data[0:1])[0]

    def frame_set_decode(self, data: bytes) -> tuple[Any, ...]:
        """Decode set type frame."""
        return struct.unpack("BB", data)

    def frame_enable_decode(self, data: bytes, dev: "Device") -> list[bool]:
        """Decode enable frame."""
        # decode set frame
        flags, chan = self.frame_set_decode(data[:2])

        if flags == EParseIdSetFlags.BULK.value:
            fmt = str(dev.data.chmax) + "?"
            ret = list(struct.unpack(fmt, data[2 : 2 + dev.data.chmax]))
        elif flags == EParseIdSetFlags.SINGLE.value:
            fmt = "?"
            en = struct.unpack(fmt, data[2:3])[0]
            ret = dev.channels_en
            ret[chan] = bool(en)
        elif flags == EParseIdSetFlags.ALL.value:
            fmt = "?"
            en = struct.unpack(fmt, data[2:3])[0]
            ret = [en for i in range(dev.data.chmax)]
        else:
            raise ValueError

        return ret

    def frame_div_decode(self, data: bytes, dev: "Device") -> list[int]:
        """Decode divider frame."""
        # decode set frame
        flags, chan = self.frame_set_decode(data[:2])

        if flags == EParseIdSetFlags.BULK.value:
            fmt = str(dev.data.chmax) + "b"
            ret = list(struct.unpack(fmt, data[2 : 2 + dev.data.chmax]))
        elif flags == EParseIdSetFlags.SINGLE.value:
            fmt = "b"
            div = struct.unpack(fmt, data[2:3])[0]
            ret = dev.channels_div
            ret[chan] = div
        elif flags == EParseIdSetFlags.ALL.value:
            fmt = "b"
            div = struct.unpack(fmt, data[2:3])[0]
            ret = [div for i in range(dev.data.chmax)]
        else:
            raise ValueError

        return ret

    def frame_cmninfo_encode(self, dev: "Device") -> bytes:
        """Encode common info frame."""
        _bytes = self._cmninfo_data_encode(dev)
        return self._frame.frame_create(EParseId.CMNINFO, _bytes)

    def frame_chinfo_encode(self, chan: "DeviceChannel") -> bytes:
        """Encode channel info frame."""
        _bytes = self._chinfo_data_encode(chan)
        return self._frame.frame_create(EParseId.CHINFO, _bytes)

    def frame_stream_encode(
        self, data: list[DParseStreamData]
    ) -> bytes | None:
        """Encode stream data frame."""
        _bytes = self._stream_data_encode(data)
        if _bytes is not None:
            return self._frame.frame_create(EParseId.STREAM, _bytes)
        return None

    def frame_ack_encode(self, data: int) -> bytes:
        """Encode ACK frame."""
        _bytes = struct.pack("i", data)
        return self._frame.frame_create(EParseId.ACK, _bytes)

    def recv_handle(self, data: bytes) -> None:
        """Handle received frame."""
        if data is None:
            return

        hdr_start = self._frame.hdr_find(data)
        if hdr_start < 0:
            return

        if (len(data) - hdr_start) < (
            self._frame.hdr_len + self._frame.foot_len
        ):
            return

        # crop data
        data = data[hdr_start:]

        # decode hdr
        hdr = self._frame.hdr_decode(data)
        if hdr.err is not EParseError.NOERR:
            return

        # validate hdr
        if self._frame.foot_validate(data[: hdr.flen]) is False:
            return

        # get frame data
        fdata = data[self._frame.hdr_len : hdr.flen - self._frame.foot_len]

        # handle frame
        self._recv_cb_handle(hdr.fid, fdata)

        return
