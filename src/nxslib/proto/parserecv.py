"""Module containing the NxScope receiver protocol logic."""

import struct
from typing import TYPE_CHECKING

from nxslib.proto.iframe import EParseError, EParseId, ICommFrame
from nxslib.proto.iparse import DParseStreamData, EParseDataType
from nxslib.proto.iparserecv import ICommParseRecv, ParseRecvCb
from nxslib.proto.parse import EParseIdSetFlags, dsfmt_get, msfmt_get
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
    ):
        """Initialize the receiver side parser."""
        if not isinstance(cb, ParseRecvCb):
            raise TypeError

        self._recv_cb = cb
        self._frame = frame()

    def _cmninfo_data_encode(self, dev: "Device") -> bytes:
        """Encode cmninfo frame data."""
        _bytes = b""

        # general info
        _bytes = struct.pack("BBB", dev.chmax, dev.flags, dev.rxpadding)

        return _bytes

    def _chinfo_data_encode(self, chan: "DeviceChannel") -> bytes:
        """Encode info frame data."""
        _bytes = b""

        # chan info
        nlen = len(chan.name)
        _bytes += struct.pack(
            f"?BBBB{nlen}s",
            chan.en,
            chan.dtype,
            chan.vdim,
            chan.div,
            chan.mlen,
            bytes(chan.name, "utf-8"),
        )

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
            _, dsfmt, scale, dtype = dsfmt_get(sample.dtype)

            # meta format
            msfmt = msfmt_get(sample.mlen)

            # pack data - always as little-endian
            fmt = "<" + "b"
            if sample.vdim:
                fmt += str(sample.vdim) + dsfmt

            if dtype == EParseDataType.NUM:
                # scale numeric data
                vect_scale_l = [x * scale for x in sample.data]
                _bytes += struct.pack(fmt, sample.chan, *vect_scale_l)
            elif dtype == EParseDataType.CHAR:
                # string data
                vect_scale_t = (bytes(sample.data[0], "utf"),)
                _bytes += struct.pack(fmt, sample.chan, *vect_scale_t)
            else:
                # no data - encode channel num
                _bytes += struct.pack(fmt, sample.chan)

            # add metadata
            if len(msfmt) > 0:
                _bytes += struct.pack(msfmt, *sample.meta)

        # do not return bytes if no sample data
        if cntr == 0:
            return None

        return _bytes

    def _recv_cb_cmninfo(self, data: bytes) -> None:
        """Handle recv cmninfo request."""
        if len(data) != 0:
            raise ValueError
        self._recv_cb.cmninfo(data)

    def _recv_cb_chinfo(self, data: bytes) -> None:
        """Handle recv chinfo request."""
        if len(data) != 1:
            raise ValueError
        self._recv_cb.chinfo(data)

    def _recv_cb_enable(self, data: bytes) -> None:
        """Handle recv enable request."""
        if len(data) == 0:
            raise ValueError
        self._recv_cb.enable(data)

    def _recv_cb_div(self, data: bytes) -> None:
        """Handle recv div request."""
        if len(data) == 0:
            raise ValueError
        self._recv_cb.div(data)

    def _recv_cb_start(self, data: bytes) -> None:
        """Handle recv start request."""
        if len(data) != 1:
            raise ValueError
        self._recv_cb.start(data)

    def _recv_cb_handle(self, fid: EParseId, fdata: bytes) -> None:
        # STREAM frames are not accepted here
        if fid == EParseId.STREAM:
            raise ValueError
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
            raise ValueError

    def frame_start_decode(self, data: bytes) -> bool:
        """Hecode start frame."""
        return struct.unpack("?", data[0:1])[0]

    def frame_set_decode(self, data: bytes) -> tuple:
        """Decode set type frame."""
        return struct.unpack("BB", data)

    def frame_enable_decode(self, data: bytes, info: "Device") -> list[bool]:
        """Decode enable frame."""
        # decode set frame
        flags, chan = self.frame_set_decode(data[:2])

        if flags == EParseIdSetFlags.BULK.value:
            fmt = str(info.chmax) + "?"
            ret = list(struct.unpack(fmt, data[2 : 2 + info.chmax]))
        elif flags == EParseIdSetFlags.SINGLE.value:
            fmt = "?"
            en = struct.unpack(fmt, data[2:3])[0]
            ret = info.channels_en
            ret[chan] = bool(en)
        elif flags == EParseIdSetFlags.ALL.value:
            fmt = "?"
            en = struct.unpack(fmt, data[2:3])[0]
            ret = [en for i in range(info.chmax)]
        else:
            raise ValueError

        return ret

    def frame_div_decode(self, data: bytes, info: "Device") -> list:
        """Decode divider frame."""
        # decode set frame
        flags, chan = self.frame_set_decode(data[:2])

        if flags == EParseIdSetFlags.BULK.value:
            fmt = str(info.chmax) + "b"
            ret = list(struct.unpack(fmt, data[2 : 2 + info.chmax]))
        elif flags == EParseIdSetFlags.SINGLE.value:
            fmt = "b"
            div = struct.unpack(fmt, data[2:3])[0]
            ret = info.channels_div
            ret[chan] = div
        elif flags == EParseIdSetFlags.ALL.value:
            fmt = "b"
            div = struct.unpack(fmt, data[2:3])[0]
            ret = [div for i in range(info.chmax)]
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
