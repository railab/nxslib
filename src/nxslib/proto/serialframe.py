"""Module containing the NxScope serial protocol specific logic."""

import struct
from enum import Enum

import crcmod  # type: ignore

from nxslib.logger import logger
from nxslib.proto.iframe import DParseHdr, EParseError, EParseId, ICommFrame
from nxslib.proto.iparse import DParseFrame

###############################################################################
# Enum: ESerialFrameHdr
###############################################################################


class ESerialFrameHdr(Enum):
    """NxScope serial frame header definitions."""

    SOF = 0x55
    END = 4
    FOOT = 2


###############################################################################
# Class: SerialFrame
###############################################################################


class SerialFrame(ICommFrame):
    """A class used to parse nxslib protocol data."""

    def __init__(self) -> None:
        """Initialize the NxScope serial protocol parser.

        Parameters
        ----------
        func : dict, optional
          nxslib request callbacks
        """
        super().__init__()

        self._crc16_func = crcmod.predefined.mkCrcFun("xmodem")

    @property
    def hdr_len(self) -> int:
        """Get the size of a header."""
        return ESerialFrameHdr.END.value

    @property
    def foot_len(self) -> int:
        """Get the size of a footer."""
        return ESerialFrameHdr.FOOT.value

    def hdr_find(self, data: bytes) -> int:
        """Find a header in bytes."""
        return data.find(bytes([ESerialFrameHdr.SOF.value]))

    def hdr_decode(self, data: bytes) -> DParseHdr:
        """Decode a header from bytes."""
        # no data
        if data is None:
            return DParseHdr(err=EParseError.HDR)

        # not sufficient data for hdr
        if len(data) < self.hdr_len:
            return DParseHdr(err=EParseError.HDR)

        # crop data
        data = data[: self.hdr_len]

        # hdr always encoded in little-endian
        fmt = "<BHB"

        sof, flen, _id = struct.unpack(fmt, data[: ESerialFrameHdr.END.value])

        if sof != ESerialFrameHdr.SOF.value:
            logger.error("invalid sof = %s", hex(sof))
            return DParseHdr(err=EParseError.HDR)

        try:
            fid = EParseId(_id)
        except ValueError:
            logger.error("unknown id = %s", hex(_id))
            return DParseHdr(err=EParseError.HDR)

        return DParseHdr(fid=fid, flen=flen)

    def foot_validate(self, data: bytes) -> bool:
        """Validate a frame footer."""
        crc = self._crc16_func(data)
        if crc != 0:
            logger.error("invalid crc16 = %s", hex(crc))
            return False
        return True

    def frame_decode(self, data: bytes) -> DParseFrame:
        """Decode a frame from bytes."""
        hdr = self.hdr_decode(data)
        if hdr.err is not EParseError.NOERR:
            return DParseFrame(err=hdr.err)

        if self.foot_validate(data[: hdr.flen]) is False:
            return DParseFrame(err=EParseError.FOOT)

        data = data[ESerialFrameHdr.END.value : hdr.flen - 2]

        return DParseFrame(fid=hdr.fid, data=data)

    def frame_create(self, _id: EParseId, data: bytes | None) -> bytes:
        """Create a frame from data."""
        frame_len = 6
        if data is not None:
            frame_len += len(data)

        if _id > 255:
            raise ValueError

        # encode header - always encoded in little-endian
        fmt = "<BHB"
        _bytes = struct.pack(fmt, ESerialFrameHdr.SOF.value, frame_len, _id)

        # optional data
        if data is not None:
            _bytes += data

        # crc16 - always big endian
        crc = self._crc16_func(_bytes)
        _bytes += struct.pack(">H", crc)

        return _bytes
