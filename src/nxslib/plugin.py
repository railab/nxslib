"""Module containing nxslib plugin interfaces."""

from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar

from nxslib.comm import AckMode

if TYPE_CHECKING:
    from nxslib.dev import Device
    from nxslib.nxscope import (
        DExtResponse,
        DNxscopeStream,
        DNxscopeStreamBlock,
    )
    from nxslib.proto.iframe import DParseFrame
    from nxslib.proto.iparse import ParseAck

T = TypeVar("T")


class INxscopeControl(Protocol):
    """Stable control surface exposed to plugins."""

    def send_user_frame(
        self,
        fid: int,
        payload: bytes,
        ack_mode: AckMode = AckMode.DISABLED,
        ack_timeout: float = 1.0,
    ) -> "ParseAck":
        """Send a user-defined frame."""

    def add_user_frame_listener(
        self,
        callback: Any,
        frame_ids: list[int] | tuple[int, ...] | set[int] | None = None,
    ) -> int:
        """Register callback for user-defined frames."""

    def remove_user_frame_listener(self, listener_id: int) -> bool:
        """Unregister callback for user-defined frames."""

    def ext_channel_add(self, chan: int) -> None:
        """Register extension channel ID for plugin-produced data."""

    def ext_publish_numpy(
        self,
        chan: int,
        data: "DNxscopeStreamBlock | list[DNxscopeStreamBlock]",
    ) -> None:
        """Publish NumPy stream blocks on an extension channel."""

    def ext_publish_legacy(
        self,
        chan: int,
        data: "DNxscopeStream | list[DNxscopeStream]",
    ) -> None:
        """Publish legacy stream samples on an extension channel."""

    def ext_bind(self, ext_id: int, handler: Any) -> None:
        """Bind request/notify handler for an extension ID."""

    def ext_unbind(self, ext_id: int) -> bool:
        """Unbind extension handler."""

    def ext_notify(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        ack_mode: AckMode = AckMode.DISABLED,
        ack_timeout: float = 1.0,
    ) -> "ParseAck":
        """Send extension notification."""

    def ext_request(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: AckMode = AckMode.DISABLED,
        ack_timeout: float = 1.0,
    ) -> "DExtResponse":
        """Send extension request and wait for response."""

    def ext_call(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: AckMode = AckMode.DISABLED,
        ack_timeout: float = 1.0,
    ) -> bytes:
        """Send request and return payload or raise on extension errors."""

    def ext_call_decode(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        decode: Callable[[bytes], T],
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: AckMode = AckMode.DISABLED,
        ack_timeout: float = 1.0,
    ) -> T:
        """Send request, then decode the successful response payload."""


class INxscopePlugin:
    """Base interface for nxslib plugins."""

    name: str = "plugin"

    def on_register(self, control: INxscopeControl) -> None:
        """Handle plugin registration."""
        del control

    def on_unregister(self) -> None:
        """Handle plugin unregistration."""

    def on_connect(self, dev: "Device") -> None:
        """Handle established nxscope connection."""
        del dev

    def on_disconnect(self) -> None:
        """Handle nxscope disconnection."""

    def on_user_frame(self, frame: "DParseFrame") -> bool | None:
        """Handle a user-defined frame."""
        del frame
        return False
