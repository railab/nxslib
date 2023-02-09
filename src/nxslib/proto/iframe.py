"""Module containing common Nxslib frame definitions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum

###############################################################################
# Enum: EParseId
###############################################################################


class EParseId(IntEnum):
    """Nxslib frame ID definitions."""

    UNDEF = 0
    # stream frames
    STREAM = 1
    # get frames
    CMNINFO = 2
    CHINFO = 3
    # special
    ACK = 4
    # set frames
    START = 5
    ENABLE = 6
    DIV = 7

    # must be last item
    INVALID = 8


###############################################################################
# Enum: EParseError
###############################################################################


class EParseError(IntEnum):
    """Nxslib frame ID errors."""

    NOERR = 0
    ERR = 1
    HDR = 2
    FOOT = 3


###############################################################################
# Class: DParseHdr
###############################################################################


@dataclass
class DParseHdr:
    """Nxslib frame header data."""

    fid: EParseId = EParseId.UNDEF
    flen: int = 0
    err: EParseError = EParseError.NOERR


###############################################################################
# Class: DParseFrame
###############################################################################


@dataclass
class DParseFrame:
    """Nxslib frame data."""

    fid: EParseId = EParseId.UNDEF
    data: bytes = b""
    err: EParseError = EParseError.NOERR


###############################################################################
# Class: ICommFrame
###############################################################################


class ICommFrame(ABC):
    """The Nxslib frame interface."""

    @property
    @abstractmethod
    def hdr_len(self) -> int:
        """Get the size of a header."""

    @property
    @abstractmethod
    def foot_len(self) -> int:
        """Get the size of a footer."""

    @abstractmethod
    def hdr_find(self, data: bytes) -> int:
        """Find a header in bytes.

        :param data: bytes to search
        """

    @abstractmethod
    def hdr_decode(self, data: bytes) -> DParseHdr:
        """Decode a header from bytes.

        :param data: bytes to decode
        """

    @abstractmethod
    def foot_validate(self, data: bytes) -> bool:
        """Validate a frame footer.

        :param data: bytes to validate
        """

    @abstractmethod
    def frame_decode(self, data: bytes) -> DParseFrame:
        """Decode a frame from bytes.

        :param data: bytes to decode
        """

    @abstractmethod
    def frame_create(self, fid: EParseId, data: bytes | None) -> bytes:
        """Create a frame from data.

        :param fid: frame ID
        :param data: frame data
        """
