"""Module containing the NxScope data parser."""

import struct
from typing import Any

from nxslib.dev import Device, DeviceChannel
from nxslib.proto.iframe import DParseFrame, EParseId, ICommFrame
from nxslib.proto.iparse import (
    DParseStream,
    DParseStreamData,
    DsfmtItem,
    EParseDataType,
    EParseIdSetFlags,
    ICommParse,
    ParseAck,
    ParseCmninfo,
    dsfmt_get,
    msfmt_get,
)
from nxslib.proto.serialframe import SerialFrame

###############################################################################
# Class: Parser
###############################################################################


class Parser(ICommParse):
    """A class used to a represent NxScope parser."""

    def __init__(
        self,
        frame: type[ICommFrame] = SerialFrame,
        user_types: dict[int, DsfmtItem] | None = None,
    ) -> None:
        """Initialize the Nxslib parser.

        :param frame: instance of the frame parser
        """
        self._frame = frame()
        self._user_types = user_types

    def _frame_set_data(self, flags: int, chan: int = 0) -> bytes:
        return struct.pack("BB", flags, chan)

    def _frame_set_single(
        self, _id: EParseId, data: bytes, chan: int
    ) -> bytes:
        """Set single channel frame."""
        assert len(data) == 1
        _bytes = self._frame_set_data(EParseIdSetFlags.SINGLE, chan)
        _bytes += data
        return self._frame.frame_create(_id, _bytes)

    def _frame_set_bulk(self, _id: EParseId, data: bytes) -> bytes:
        """Set bulk frame."""
        assert len(data) > 0
        _bytes = self._frame_set_data(EParseIdSetFlags.BULK)
        _bytes += data
        return self._frame.frame_create(_id, _bytes)

    def _frame_set_all(self, _id: EParseId, data: bytes) -> bytes:
        """Set all frame."""
        assert len(data) == 1
        _bytes = self._frame_set_data(EParseIdSetFlags.ALL)
        _bytes += data
        return self._frame.frame_create(_id, _bytes)

    def _stream_data_get(
        self, decode: DsfmtItem, unpacked: tuple[Any, ...]
    ) -> tuple[Any, ...]:
        if decode.dtype == EParseDataType.NUM and decode.scale:
            # scale numerical data if scaling factor available
            retdata = tuple(x / decode.scale for x in unpacked)

        elif decode.dtype is EParseDataType.CHAR and len(unpacked) == 1:
            # decode bytes to string if possible
            retdata = (unpacked[0].decode(),)

        else:
            # otherwise return without formating
            retdata = unpacked

        return retdata

    @property
    def frame(self) -> ICommFrame:
        """Get the frame handler."""
        return self._frame

    def frame_start(self, start: bool) -> bytes:
        """Create a start frame."""
        _bytes = struct.pack("?", start)
        return self._frame.frame_create(EParseId.START, _bytes)

    def frame_cmninfo(self) -> bytes:
        """Create a cmninfo frame."""
        return self._frame.frame_create(EParseId.CMNINFO, None)

    def frame_chinfo(self, chan: int) -> bytes:
        """Create a chinfo frame."""
        _bytes = struct.pack("b", chan)
        return self._frame.frame_create(EParseId.CHINFO, _bytes)

    def frame_enable(
        self, enable: tuple[int, bool] | list[bool], chmax: int
    ) -> bytes:
        """Create a enable frame."""
        # single channel change
        if isinstance(enable, tuple) is True:
            # for tuple: first element is channel id,
            #            second element is enable value
            chan = enable[0]
            data = bytes([enable[1]])
            return self._frame_set_single(EParseId.ENABLE, data, chan)

        # all the same
        if len(enable) == chmax and len(set(enable)) <= 1:
            data = bytes([enable[0]])
            return self._frame_set_all(EParseId.ENABLE, data)

        # bulk request for all channels
        data = b""
        for _chan in range(chmax):
            if enable[_chan] is True:
                # en byte
                data += b"\x01"
            else:
                # en byte
                data += b"\x00"

        return self._frame_set_bulk(EParseId.ENABLE, data)

    def frame_div(self, div: tuple[int, int] | list[int], chmax: int) -> bytes:
        """Create a div frame."""
        # single channel change
        if isinstance(div, tuple) is True:
            # for tuple: first element is channel id,
            #            second element is div value
            chan = div[0]
            data = bytes([div[1]])
            return self._frame_set_single(EParseId.DIV, data, chan)

        # all the same
        if len(div) == chmax and len(set(div)) <= 1:
            data = bytes([int(div[0])])
            return self._frame_set_all(EParseId.DIV, data)

        # bulk request for all channels
        data = b""
        for chan in range(chmax):
            # div byte
            data += bytes([div[chan]])

        return self._frame_set_bulk(EParseId.DIV, data)

    def frame_stream_decode(
        self, frame: DParseFrame, dev: Device
    ) -> DParseStream | None:
        """Decode a stream frame."""
        # no data
        if not frame:
            return None

        # invalid frame ID
        if frame.fid != EParseId.STREAM:
            return None

        if not frame.data:
            return None

        # parse samples data
        # first byte is stream data is always flags byte - ommit it for now
        samples = []
        i = 1
        while i < len(frame.data):
            # first byte in stream data sequence - channel id
            chan = dev.channel_get(frame.data[i])
            assert chan
            i += 1

            # decode meta data
            meta = msfmt_get(chan.data.mlen)

            # decode sample type
            decode = dsfmt_get(chan.data.dtype, self._user_types)
            if decode.user:  # pragma: no cover
                # NxScope compatibility:
                #   real type size is determined with vdim, not by slen
                assert struct.calcsize("<" + decode.dsfmt) == chan.data.vdim

            # data always packed as little-endian
            sfmt = "<"
            if chan.data.vdim and not decode.user:
                sfmt += str(chan.data.vdim)
            sfmt += decode.dsfmt

            # unpack data
            offset = decode.slen * chan.data.vdim
            unpacked = struct.unpack(sfmt, frame.data[i : i + offset])
            i += offset

            # format stream data
            retdata = self._stream_data_get(decode, unpacked)

            # unpack metadata
            sfmt = "<" + meta
            offset = chan.data.mlen
            mdata = struct.unpack(sfmt, frame.data[i : i + offset])
            i += offset

            # sample
            sample = DParseStreamData(
                chan=chan.data.chan,
                dtype=decode.dtype,
                vdim=chan.data.vdim,
                mlen=chan.data.mlen,
                data=retdata,
                meta=mdata,
            )

            samples.append(sample)

        # return samples data and flags (always firtst byte in stream data)
        return DParseStream(flags=frame.data[0], samples=samples)

    def frame_cmninfo_decode(self, frame: DParseFrame) -> ParseCmninfo | None:
        """Decode a cmninfo frame."""
        # no data
        if frame is None:
            return None

        # no info frame
        if frame.fid != EParseId.CMNINFO:
            return None

        cmninfo_bytes = 3
        cmninfo_decode = "BBB"
        chmax, flags, rxpadding = struct.unpack(
            cmninfo_decode, frame.data[:cmninfo_bytes]
        )

        return ParseCmninfo(chmax, flags, rxpadding)

    def frame_chinfo_decode(
        self, frame: DParseFrame, chan: int
    ) -> DeviceChannel | None:
        """Decode a chinfo frame."""
        if frame is None:
            # no data
            return None

        if frame.fid != EParseId.CHINFO:
            # no info frame
            return None

        # decode channels info
        nlen = len(frame.data) - 5
        chinfo_decode = f"BBBBB{nlen}s"

        en, _type, vdim, div, mlen, _str = struct.unpack(
            chinfo_decode, frame.data
        )

        name = "" if not _str else _str.decode().split("\x00")[0]

        return DeviceChannel(
            chan=chan,
            _type=_type,
            vdim=vdim,
            en=en,
            div=div,
            mlen=mlen,
            name=name,
        )

    def frame_is_ack(self, frame: DParseFrame) -> bool:
        """Return true if a given frame is ACK."""
        return frame.fid == EParseId.ACK

    def frame_is_stream(self, frame: DParseFrame) -> bool:
        """Return true if a given frame is STREAM."""
        return frame.fid == EParseId.STREAM

    def frame_ack_decode(self, frame: DParseFrame) -> ParseAck | None:
        """Decode ACK frame."""
        # no data
        if frame is None:
            return None

        if frame.fid != EParseId.ACK:
            return None

        ret = struct.unpack("i", frame.data)[0]
        if not ret:
            return ParseAck(True, 0)

        return ParseAck(False, ret)
