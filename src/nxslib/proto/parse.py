"""Module containing the NxScope data parser."""

import struct

from nxslib.dev import Device, DeviceChannel
from nxslib.proto.iframe import EParseId, ICommFrame
from nxslib.proto.iparse import (
    DParseFrame,
    DParseStream,
    DParseStreamData,
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

    def __init__(self, frame: type[ICommFrame] = SerialFrame):
        """Initialize the Nxslib parser."""
        self._frame = frame()

    def _frame_set_data(self, flags, chan=0) -> bytes:
        return struct.pack("BB", flags, chan)

    def _frame_set_single(self, _id: EParseId, data: bytes, chan) -> bytes:
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

    def frame_enable(self, enable: tuple | list, chmax: int) -> bytes:
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
            data = bytes([bool(enable[0])])
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

    def frame_div(self, div: tuple | list, chmax: int) -> bytes:
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
        self, frame: DParseFrame, info: Device
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
            chan = info.channel_get(frame.data[i])
            assert chan
            i += 1

            # decode meta data
            meta = msfmt_get(chan.mlen)

            # decode sample type
            slen, dsfmt, scale, dtype = dsfmt_get(chan.dtype)

            # data always packed as little-endian
            if chan.vdim:
                sfmt = "<" + str(chan.vdim) + dsfmt + meta
            else:
                sfmt = "<" + meta

            # unpack data
            offset = slen * chan.vdim + chan.mlen

            unpacked = struct.unpack(sfmt, frame.data[i : i + offset])
            i += offset

            # TODO: refactor
            assert dtype in EParseDataType
            if dtype == EParseDataType.NUM:
                # scale data
                retdata = tuple(x / scale for x in unpacked[: chan.vdim])
                mdata = unpacked[chan.vdim :]
            elif dtype is EParseDataType.NONE:
                retdata = ()
                mdata = unpacked
            else:
                assert dtype == EParseDataType.CHAR
                retbytes = unpacked[0]
                # decode bytes to char
                retdata = (retbytes.decode(),)
                if chan.mlen > 0:
                    mdata = (unpacked[1],)
                else:
                    mdata = ()

            # sample
            sample = DParseStreamData(
                chan=chan.chan,
                dtype=dtype,
                vdim=chan.vdim,
                mlen=chan.mlen,
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

        name = "" if _str else _str.decode().split("\x00")[0]

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
        if frame.fid == EParseId.ACK:
            return True

        return False

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
