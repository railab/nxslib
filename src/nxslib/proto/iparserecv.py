"""Module containing common definitions for the receiver parser."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from nxslib.dev import Device, DeviceChannel
from nxslib.proto.iframe import ICommFrame
from nxslib.proto.serialframe import SerialFrame

###############################################################################
# Class: ParseRecvCb
###############################################################################


@dataclass
class ParseRecvCb:
    """Receiver parser callbacks."""

    cmninfo: Callable[[bytes], None]
    chinfo: Callable[[bytes], None]
    enable: Callable[[bytes], None]
    div: Callable[[bytes], None]
    start: Callable[[bytes], None]


###############################################################################
# Class: ICommParseRecv
###############################################################################


class ICommParseRecv(ABC):
    """The receiver parser interface."""

    @abstractmethod
    def __init__(
        self,
        cb: ParseRecvCb,
        frame: type[ICommFrame] = SerialFrame,
    ):
        """Initialize the receiver parser."""

    @abstractmethod
    def frame_start_decode(self, data: bytes) -> bool:
        """Decode start frame."""

    @abstractmethod
    def frame_set_decode(self, data: bytes) -> tuple:
        """Decode set type frame."""

    @abstractmethod
    def frame_enable_decode(self, data: bytes, info: Device) -> list:
        """Decode enable frame."""

    @abstractmethod
    def frame_div_decode(self, data: bytes, info: Device) -> list:
        """Decode divider frame."""

    @abstractmethod
    def frame_cmninfo_encode(self, dev: Device) -> bytes:
        """Encode common info frame."""

    @abstractmethod
    def frame_chinfo_encode(self, chan: DeviceChannel) -> bytes:
        """Encode channel info frame."""

    @abstractmethod
    def frame_stream_encode(self, data: list) -> bytes | None:
        """Encode stream data frame."""

    @abstractmethod
    def frame_ack_encode(self, data: int) -> bytes:
        """Encode ACK frame."""

    @abstractmethod
    def recv_handle(self, data: bytes) -> None:
        """Handle received frame."""
