"""Module containing common parser definitions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from nxslib.dev import Device, DeviceChannel, EDeviceChannelType

if TYPE_CHECKING:
    from nxslib.proto.iframe import DParseFrame, ICommFrame

###############################################################################
# Enum: EParseIdSetFlags
###############################################################################


class EParseIdSetFlags(IntEnum):
    """Nxslib set frame flags definitions."""

    SINGLE = 0
    BULK = 1
    ALL = 2
    # must be last item
    INVALID = 3


###############################################################################
# Enum: EParseStreamFlags
###############################################################################


class EParseStreamFlags(IntEnum):
    """Nxslib stream frame flags."""

    OVERFLOW = 1 << 0


###############################################################################
# Class: ParseAck
###############################################################################


# TODO: only retcode as input, decode state from retcode value
@dataclass
class ParseAck:
    """Nxslib ACK frame."""

    state: bool
    retcode: int


###############################################################################
# Class: ParseCmninfo
###############################################################################


@dataclass
class ParseCmninfo:
    """Nxslib cmninfo frame."""

    chmax: int
    flags: int
    rxpadding: int


###############################################################################
# Class: DParseStreamData
###############################################################################


@dataclass
class DParseStreamData:
    """Nxslib stream data."""

    chan: int
    dtype: int
    vdim: int
    mlen: int
    data: tuple[Any, ...]
    meta: tuple[Any, ...]


###############################################################################
# Class: DParseStream
###############################################################################


@dataclass
class DParseStream:
    """Nxslib stream data."""

    flags: int
    samples: list


###############################################################################
# Function: msfmt_get
###############################################################################


def msfmt_get(mlen: int) -> str:
    """Get metadata format."""
    msfmt_dict = {0: "", 1: "B", 2: "H", 4: "I", 8: "Q"}

    meta = msfmt_dict.get(mlen)
    if meta is None:
        # otherwise decode as bytes
        meta = str(mlen) + "B"

    return meta


###############################################################################
# Enum: EParseDataType
###############################################################################


class EParseDataType(IntEnum):
    """Nxslib parse data type."""

    NONE = 0
    NUM = 1
    CHAR = 2


###############################################################################
# Function: dsfmt_get
###############################################################################


def dsfmt_get(dtype: int) -> tuple:
    """Get data format."""
    # tuple of (size in bytes, unpack fmt, scale factor)
    dsfmt_dict = {
        EDeviceChannelType.NONE.value: (
            0,
            "",
            None,
            EParseDataType.NONE,
        ),
        EDeviceChannelType.UINT8.value: (
            1,
            "B",
            1,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.INT8.value: (
            1,
            "b",
            1,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.UINT16.value: (
            2,
            "H",
            1,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.INT16.value: (
            2,
            "h",
            1,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.UINT32.value: (
            4,
            "I",
            1,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.INT32.value: (
            4,
            "i",
            1,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.UINT64.value: (
            8,
            "Q",
            1,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.INT64.value: (
            8,
            "q",
            1,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.FLOAT.value: (
            4,
            "f",
            1.0,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.DOUBLE.value: (
            8,
            "d",
            1.0,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.UB8.value: (
            2,
            "H",
            256.0,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.B8.value: (
            2,
            "h",
            256.0,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.UB16.value: (
            4,
            "I",
            65536.0,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.B16.value: (
            4,
            "i",
            65536.0,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.UB32.value: (
            8,
            "Q",
            4294967296.0,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.B32.value: (
            8,
            "q",
            4294967296.0,
            EParseDataType.NUM,
        ),
        EDeviceChannelType.CHAR.value: (
            1,
            "s",
            None,
            EParseDataType.CHAR,
        ),
        EDeviceChannelType.WCHAR.value: (
            1,
            "s",
            None,
            EParseDataType.CHAR,
        ),
    }

    dsfmt = dsfmt_dict.get(dtype)
    if not dsfmt:
        raise KeyError

    return dsfmt


###############################################################################
# Class: ICommParse
###############################################################################


class ICommParse(ABC):
    """The Nxslib parser interface."""

    @property
    @abstractmethod
    def frame(self) -> "ICommFrame":
        """Get the frame handler."""

    @abstractmethod
    def frame_start(self, start: bool) -> bytes:
        """Create a start frame."""

    @abstractmethod
    def frame_cmninfo(self) -> bytes:
        """Create a cmninfo frame."""

    @abstractmethod
    def frame_chinfo(self, chan: int) -> bytes:
        """Create a chinfo frame."""

    @abstractmethod
    def frame_enable(self, enable: tuple | list, chmax: int) -> bytes:
        """Create a enable frame."""

    @abstractmethod
    def frame_div(self, div: tuple | list, chmax: int) -> bytes:
        """Create a div frame."""

    @abstractmethod
    def frame_stream_decode(
        self, frame: "DParseFrame", dev: Device
    ) -> DParseStream | None:
        """Decode a stream frame."""

    @abstractmethod
    def frame_cmninfo_decode(
        self, frame: "DParseFrame"
    ) -> ParseCmninfo | None:
        """Decode a cmninfo frame."""

    @abstractmethod
    def frame_chinfo_decode(
        self, frame: "DParseFrame", chan: int
    ) -> DeviceChannel | None:
        """Decode a chinfo frame."""

    @abstractmethod
    def frame_is_ack(self, frame: "DParseFrame") -> bool:
        """Return true if a given frame is ACK."""

    @abstractmethod
    def frame_ack_decode(self, frame: "DParseFrame") -> ParseAck | None:
        """Decode ACK frame."""
