"""Module containing the NxScope handler."""

import queue
import struct
import warnings
from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import time
from typing import TYPE_CHECKING, Any, Callable, TypeVar

import numpy as np

from nxslib.comm import CommHandler
from nxslib.logger import logger
from nxslib.proto.iparse import ParseAck, dsfmt_get
from nxslib.thread import ThreadCommon

if TYPE_CHECKING:
    from nxslib.dev import Device, DeviceChannel
    from nxslib.intf.iintf import ICommInterface
    from nxslib.plugin import INxscopePlugin
    from nxslib.proto.iparse import DParseStreamNumpy, ICommParse

T = TypeVar("T")


###############################################################################
# Data: DNxscopeStream
###############################################################################


@dataclass
class DNxscopeStream:
    """Legacy per-sample stream data item (deprecated)."""

    data: tuple[Any, ...]
    meta: tuple[Any, ...]

    def __str__(self) -> str:
        """Human-readable stream item."""
        return str(self.data) + ", " + str(self.meta)

    def __repr__(self) -> str:
        """Represent stream item as string."""
        return str(self.data) + ", " + str(self.meta)


###############################################################################
# Data: DNxscopeStreamBlock
###############################################################################


@dataclass
class DNxscopeStreamBlock:
    """NumPy block stream item."""

    data: np.ndarray[Any, Any]
    meta: np.ndarray[Any, Any] | None


###############################################################################
# Data: DChannelState
###############################################################################


@dataclass(frozen=True)
class DChannelState:
    """Channels runtime state snapshot."""

    enabled_channels: tuple[int, ...]
    dividers: tuple[int, ...]


###############################################################################
# Data: DDeviceCapabilities
###############################################################################


@dataclass(frozen=True)
class DDeviceCapabilities:
    """Device capabilities snapshot."""

    chmax: int
    flags: int
    rxpadding: int
    div_supported: bool
    ack_supported: bool


###############################################################################
# Data: DStreamStats
###############################################################################


@dataclass(frozen=True)
class DStreamStats:
    """Stream runtime stats snapshot."""

    connected: bool
    stream_started: bool
    overflow_count: int
    bitrate: float


@dataclass(frozen=True)
class DExtRequest:
    """Decoded extension request/notify payload."""

    ext_id: int
    cmd_id: int
    req_id: int
    status: int
    payload: bytes
    fid: int
    flags: int


@dataclass(frozen=True)
class DExtResponse:
    """Extension response returned by ext_request()."""

    ext_id: int
    cmd_id: int
    req_id: int
    status: int
    payload: bytes
    fid: int
    is_error: bool


class DExtCallError(RuntimeError):
    """Extension call failed with status or explicit error response."""

    def __init__(self, response: DExtResponse):
        """Build exception with the full extension response attached."""
        super().__init__(
            "extension call failed: "
            f"ext_id={response.ext_id} cmd_id={response.cmd_id} "
            f"req_id={response.req_id} status={response.status} "
            f"is_error={response.is_error}"
        )
        self.response = response


_EXT_FLAG_REQ = 0x01
_EXT_FLAG_RESP = 0x02
_EXT_FLAG_ERR = 0x04
_EXT_FLAG_NOTIFY = 0x08
_EXT_HDR_FMT = "<BBBBHB"
_EXT_HDR_LEN = struct.calcsize(_EXT_HDR_FMT)


###############################################################################
# Class: _BitrateTracker
###############################################################################


class _BitrateTracker:
    """Helper for bitrate calculation with moving average."""

    def __init__(self, window_seconds: float = 5.0) -> None:
        """Initialize bitrate tracker.

        :param window_seconds: Time window for moving average
        """
        self._bytes_received: int = 0
        self._last_timestamp: float = 0.0
        self._samples: deque[tuple[float, int]] = deque()
        self._window_seconds: float = window_seconds
        self._lock = Lock()

    def update(self, bytes_count: int) -> None:
        """Update tracker with new byte count.

        :param bytes_count: Number of bytes received
        """
        with self._lock:
            now = time()
            self._bytes_received += bytes_count
            self._samples.append((now, bytes_count))

            # Remove samples older than window
            cutoff = now - self._window_seconds
            while self._samples and self._samples[0][0] < cutoff:
                self._samples.popleft()

            self._last_timestamp = now

    def get_bitrate(self) -> float:
        """Calculate current bitrate.

        :return: Bytes per second over the window period
        """
        with self._lock:
            if not self._samples:
                return 0.0

            now = time()
            oldest_time = self._samples[0][0]
            time_span = now - oldest_time

            if time_span < 0.1:  # Less than 100ms of data
                return 0.0

            total_bytes = sum(count for _, count in self._samples)
            return total_bytes / time_span


class _PluginControl:
    """Restricted control surface passed to plugin on_register."""

    def __init__(self, handler: "NxscopeHandler") -> None:
        self._handler = handler

    def send_user_frame(
        self,
        fid: int,
        payload: bytes,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> ParseAck:
        return self._handler.send_user_frame(
            fid=fid,
            payload=payload,
            ack_mode=ack_mode,
            ack_timeout=ack_timeout,
        )

    def add_user_frame_listener(
        self,
        callback: Any,
        frame_ids: list[int] | tuple[int, ...] | set[int] | None = None,
    ) -> int:
        return self._handler.add_user_frame_listener(callback, frame_ids)

    def remove_user_frame_listener(self, listener_id: int) -> bool:
        return self._handler.remove_user_frame_listener(listener_id)

    def ext_channel_add(self, chan: int) -> None:
        self._handler.ext_channel_add(chan)

    def ext_publish_numpy(
        self,
        chan: int,
        data: DNxscopeStreamBlock | list[DNxscopeStreamBlock],
    ) -> None:
        self._handler.ext_publish_numpy(chan, data)

    def ext_publish_legacy(
        self,
        chan: int,
        data: DNxscopeStream | list[DNxscopeStream],
    ) -> None:
        self._handler.ext_publish_legacy(chan, data)

    def ext_bind(self, ext_id: int, handler: Any) -> None:
        self._handler.ext_bind(ext_id, handler)

    def ext_unbind(self, ext_id: int) -> bool:
        return self._handler.ext_unbind(ext_id)

    def ext_notify(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> ParseAck:
        return self._handler.ext_notify(
            ext_id=ext_id,
            cmd_id=cmd_id,
            payload=payload,
            fid=fid,
            ack_mode=ack_mode,
            ack_timeout=ack_timeout,
        )

    def ext_request(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> DExtResponse:
        return self._handler.ext_request(
            ext_id=ext_id,
            cmd_id=cmd_id,
            payload=payload,
            fid=fid,
            timeout=timeout,
            ack_mode=ack_mode,
            ack_timeout=ack_timeout,
        )

    def ext_call(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> bytes:
        return self._handler.ext_call(
            ext_id=ext_id,
            cmd_id=cmd_id,
            payload=payload,
            fid=fid,
            timeout=timeout,
            ack_mode=ack_mode,
            ack_timeout=ack_timeout,
        )

    def ext_call_decode(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        decode: Callable[[bytes], T],
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> T:
        return self._handler.ext_call_decode(
            ext_id=ext_id,
            cmd_id=cmd_id,
            payload=payload,
            decode=decode,
            fid=fid,
            timeout=timeout,
            ack_mode=ack_mode,
            ack_timeout=ack_timeout,
        )


###############################################################################
# Class: NxscopeHandler
###############################################################################


class NxscopeHandler:
    """A class used to manage NxScope device."""

    def __init__(
        self,
        intf: "ICommInterface",
        parse: "ICommParse",
        enable_bitrate_tracking: bool = False,
        stream_decode_mode: str | None = None,
        drop_timeout: float = 0.1,
        stream_data_timeout: float = 1.0,
    ) -> None:
        """Initialize the Nxslib handler.

        :param intf: Communication interface
        :param parse: Protocol parser
        :param enable_bitrate_tracking: Enable bitrate tracking
            (default: False)
        :param stream_decode_mode: stream decode mode: `numpy` (default)
            or `legacy` (deprecated).
        :param drop_timeout: timeout used in _drop_all_frames queue drains
        :param stream_data_timeout: timeout used in stream_data() frame wait
        """
        self._connected: bool = False
        self._comm = CommHandler(
            intf,
            parse,
            drop_timeout=drop_timeout,
            stream_data_timeout=stream_data_timeout,
        )

        self._thrd = ThreadCommon(self._stream_thread, name="stream")

        mode = stream_decode_mode or "numpy"
        if mode not in ("legacy", "numpy"):
            raise ValueError("stream_decode_mode must be `legacy` or `numpy`")
        self._stream_decode_mode = mode
        if self._stream_decode_mode == "legacy":
            warnings.warn(
                "legacy stream decode mode is deprecated, should not be used "
                "for new code, and will be removed in a future release; "
                "use stream_decode_mode='numpy'",
                DeprecationWarning,
                stacklevel=2,
            )

        self._sub_q: dict[int, list[queue.Queue[Any]]] = {}
        self._queue_lock: Lock = Lock()

        self._stream_started: bool = False

        self._plugins: dict[str, tuple["INxscopePlugin", int | None]] = {}
        self._plugins_lock: Lock = Lock()
        self._control = _PluginControl(self)

        self._ext_handlers: dict[int, Any] = {}
        self._ext_pending: dict[int, queue.Queue[DExtResponse]] = {}
        self._ext_lock: Lock = Lock()
        self._ext_req_id: int = 1
        self._ext_listener_id = self._comm.add_user_frame_listener(
            self._ext_dispatch_frame
        )

        self._ovf_cntr: int = 0
        self._stats_lock: Lock = Lock()
        self._bitrate_tracker: _BitrateTracker | None = (
            _BitrateTracker() if enable_bitrate_tracking else None
        )

    def __enter__(self) -> "NxscopeHandler":
        """Connect on context manager entry."""
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        """Disconnect on context manager exit."""
        self.disconnect()

    def _stream_start(self) -> bool:
        """Start stream request."""
        self._reset_stats()

        ret = self._comm.stream_start()
        if ret is None:  # pragma: no cover
            return False

        return ret.state

    def _stream_stop(self) -> bool:
        """Stop stream request."""
        ret = self._comm.stream_stop()
        if ret is None:  # pragma: no cover
            return False

        return ret.state

    def _stream_thread(self) -> None:  # noqa: C901
        """Stream thread."""
        assert self.dev
        chmax = self.dev.data.chmax

        if self._stream_decode_mode == "numpy":
            samples_block: list[list[DNxscopeStreamBlock]] = [
                [] for _ in range(chmax)
            ]
            sdata_np: "DParseStreamNumpy | None" = (
                self._comm.stream_data_numpy()
            )
            if not sdata_np:
                return

            if (
                self._comm.flags_is_overflow(sdata_np.flags) is True
            ):  # pragma: no cover
                logger.info("stream flags: OVERFLOW!")
                with self._stats_lock:
                    self._ovf_cntr += 1

            for block in sdata_np.blocks:
                if self._bitrate_tracker is not None:
                    data_bytes = int(block.data.size * block.data.itemsize)
                    meta_bytes = (
                        0
                        if block.meta is None
                        else int(block.meta.size * block.meta.itemsize)
                    )
                    self._bitrate_tracker.update(data_bytes + meta_bytes)

                if self._comm.ch_is_enabled(block.chan) is True:
                    samples_block[block.chan].append(
                        DNxscopeStreamBlock(block.data, block.meta)
                    )

            with self._queue_lock:
                for chan_id in range(chmax):
                    if len(samples_block[chan_id]) > 0:
                        for que in self._sub_q.get(chan_id, []):
                            que.put(samples_block[chan_id])
            return

        samples: list[list[DNxscopeStream]] = [[] for _ in range(chmax)]

        sdata = self._comm.stream_data()
        if not sdata:  # pragma: no cover
            return
        if (
            self._comm.flags_is_overflow(sdata.flags) is True
        ):  # pragma: no cover
            logger.info("stream flags: OVERFLOW!")
            with self._stats_lock:
                self._ovf_cntr += 1

        for data in sdata.samples:
            ch = self.dev_channel_get(data.chan)
            if ch:
                dsfmt = dsfmt_get(ch.data.dtype)
                data_bytes = dsfmt.slen * ch.data.vdim
                meta_bytes = ch.data.mlen
                total_bytes = data_bytes + meta_bytes
                if self._bitrate_tracker is not None:
                    self._bitrate_tracker.update(total_bytes)

            if self._comm.ch_is_enabled(data.chan) is True:  # pragma: no cover
                samples[data.chan].append(DNxscopeStream(data.data, data.meta))

        with self._queue_lock:
            for chan_id in range(chmax):
                if len(samples[chan_id]) > 0:
                    for que in self._sub_q.get(chan_id, []):
                        que.put(samples[chan_id])

    def _reset_stats(self) -> None:
        with self._stats_lock:
            self._ovf_cntr = 0
        if self._bitrate_tracker is not None:
            self._bitrate_tracker = _BitrateTracker()

    @property
    def dev(self) -> "Device | None":
        """Get device info."""
        return self._comm.dev

    @property
    def connected(self) -> bool:
        """Check if device is connected."""
        return self._connected

    @property
    def stream_started(self) -> bool:
        """Check if stream is started."""
        return self._stream_started

    @property
    def overflow_count(self) -> int:
        """Get overflow counter."""
        with self._stats_lock:
            return self._ovf_cntr

    def get_bitrate(self) -> float:
        """Calculate current bitrate with moving average.

        :return: Bytes per second over the window period, or 0.0 if
        tracking disabled
        """
        if self._bitrate_tracker is None:
            return 0.0
        return self._bitrate_tracker.get_bitrate()

    def get_enabled_channels(self, applied: bool = True) -> tuple[int, ...]:
        """Get enabled channels state.

        :param applied: get currently-applied values when True, otherwise get
            buffered values that will be applied on next channels_write
        """
        return self._comm.get_enabled_channels(applied=applied)

    def get_channel_divider(self, chid: int, applied: bool = True) -> int:
        """Get divider for a channel.

        :param chid: channel ID
        :param applied: get currently-applied value when True, otherwise get
            buffered value that will be applied on next channels_write
        """
        return self._comm.ch_div_get(chid, applied=applied)

    def get_channel_dividers(self, applied: bool = True) -> tuple[int, ...]:
        """Get divider values for all channels.

        :param applied: get currently-applied values when True, otherwise get
            buffered values that will be applied on next channels_write
        """
        return self._comm.get_channel_dividers(applied=applied)

    def get_channels_state(self, applied: bool = True) -> DChannelState:
        """Get channels state snapshot."""
        return DChannelState(
            enabled_channels=self.get_enabled_channels(applied=applied),
            dividers=self.get_channel_dividers(applied=applied),
        )

    def get_device_capabilities(self) -> DDeviceCapabilities:
        """Get device capabilities snapshot."""
        assert self.dev
        data = self.dev.data
        return DDeviceCapabilities(
            chmax=data.chmax,
            flags=data.flags,
            rxpadding=data.rxpadding,
            div_supported=data.div_supported,
            ack_supported=data.ack_supported,
        )

    def get_stream_stats(self) -> DStreamStats:
        """Get stream stats snapshot."""
        return DStreamStats(
            connected=self.connected,
            stream_started=self.stream_started,
            overflow_count=self.overflow_count,
            bitrate=self.get_bitrate(),
        )

    def connect(self) -> "Device | None":
        """Connect with a NxScope device."""
        if self._connected is True:
            logger.info("WARNING: ALREADY CONNECTED!")
            return self._comm.dev

        logger.info("Connecting to NxScope device")
        self._comm.connect()

        # create queues map for physical channels
        assert self.dev
        self._sub_q = {chan: [] for chan in range(self.dev.data.chmax)}
        self._connected = True

        with self._plugins_lock:
            plugins = [p for p, _ in self._plugins.values()]
        for plugin in plugins:
            cb = getattr(plugin, "on_connect", None)
            if callable(cb):
                cb(self.dev)

        return self._comm.dev

    def disconnect(self) -> None:
        """Disconnect from a NxScope device."""
        if self._connected is True:
            with self._plugins_lock:
                plugins = [p for p, _ in self._plugins.values()]
            for plugin in plugins:
                cb = getattr(plugin, "on_disconnect", None)
                if callable(cb):
                    cb()

            # stop stream
            self.stream_stop()
            # disable all channels now
            self.ch_disable_all(True)
            # disconnect
            self._comm.disconnect()
            self._connected = False

    def send_user_frame(
        self,
        fid: int,
        payload: bytes,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> ParseAck:
        """Send user-defined frame through nxscope transport."""
        return self._comm.send_user_frame(
            fid, payload, ack_mode=ack_mode, ack_timeout=ack_timeout
        )

    def add_user_frame_listener(
        self,
        callback: Any,
        frame_ids: list[int] | tuple[int, ...] | set[int] | None = None,
    ) -> int:
        """Register callback for user-defined frames."""
        return self._comm.add_user_frame_listener(callback, frame_ids)

    def remove_user_frame_listener(self, listener_id: int) -> bool:
        """Unregister callback for user-defined frames."""
        return self._comm.remove_user_frame_listener(listener_id)

    def _ext_encode(
        self,
        ext_id: int,
        cmd_id: int,
        flags: int,
        req_id: int,
        status: int,
        payload: bytes,
    ) -> bytes:
        """Encode extension envelope."""
        if ext_id < 0 or ext_id > 0xFF:
            raise ValueError("ext_id must be in range [0, 255]")
        if cmd_id < 0 or cmd_id > 0xFF:
            raise ValueError("cmd_id must be in range [0, 255]")
        if req_id < 0 or req_id > 0xFFFF:
            raise ValueError("req_id must be in range [0, 65535]")
        if status < 0 or status > 0xFF:
            raise ValueError("status must be in range [0, 255]")
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")

        return (
            struct.pack(
                _EXT_HDR_FMT,
                0xE1,
                ext_id,
                cmd_id,
                flags,
                req_id,
                status,
            )
            + payload
        )

    def _ext_decode(self, fid: int, data: bytes) -> DExtRequest | None:
        """Decode extension envelope from user frame payload."""
        if len(data) < _EXT_HDR_LEN:
            return None

        magic, ext_id, cmd_id, flags, req_id, status = struct.unpack(
            _EXT_HDR_FMT, data[:_EXT_HDR_LEN]
        )
        if magic != 0xE1:
            return None

        return DExtRequest(
            ext_id=ext_id,
            cmd_id=cmd_id,
            req_id=req_id,
            status=status,
            payload=data[_EXT_HDR_LEN:],
            fid=fid,
            flags=flags,
        )

    def _ext_alloc_req_id(self) -> int:
        """Allocate request ID for extension request/response."""
        with self._ext_lock:
            for _ in range(0xFFFF):
                req_id = self._ext_req_id if self._ext_req_id != 0 else 1
                self._ext_req_id = (req_id % 0xFFFF) + 1
                if req_id not in self._ext_pending:
                    return req_id

        raise RuntimeError("no free extension request IDs")

    def ext_bind(self, ext_id: int, handler: Any) -> None:
        """Bind handler for extension namespace.

        Handler receives DExtRequest and may return:
        - None: no response
        - bytes: response payload with status 0
        - tuple[int, bytes]: response status and payload
        """
        if ext_id < 0 or ext_id > 0xFF:
            raise ValueError("ext_id must be in range [0, 255]")
        if not callable(handler):
            raise TypeError("handler must be callable")

        with self._ext_lock:
            self._ext_handlers[ext_id] = handler

    def ext_unbind(self, ext_id: int) -> bool:
        """Unbind extension namespace handler."""
        with self._ext_lock:
            if ext_id in self._ext_handlers:
                self._ext_handlers.pop(ext_id)
                return True
        return False

    def ext_notify(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> ParseAck:
        """Send extension notification."""
        data = self._ext_encode(
            ext_id=ext_id,
            cmd_id=cmd_id,
            flags=_EXT_FLAG_NOTIFY,
            req_id=0,
            status=0,
            payload=payload,
        )
        return self.send_user_frame(
            fid=fid,
            payload=data,
            ack_mode=ack_mode,
            ack_timeout=ack_timeout,
        )

    def ext_request(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> DExtResponse:
        """Send extension request and wait for response."""
        req_id = self._ext_alloc_req_id()
        q: queue.Queue[DExtResponse] = queue.Queue(maxsize=1)

        with self._ext_lock:
            self._ext_pending[req_id] = q

        try:
            data = self._ext_encode(
                ext_id=ext_id,
                cmd_id=cmd_id,
                flags=_EXT_FLAG_REQ,
                req_id=req_id,
                status=0,
                payload=payload,
            )
            ack = self.send_user_frame(
                fid=fid,
                payload=data,
                ack_mode=ack_mode,
                ack_timeout=ack_timeout,
            )
            if ack_mode == "required" and not ack.state:
                raise RuntimeError(
                    f"extension request ACK failed: {ack.retcode}"
                )

            try:
                return q.get(block=True, timeout=timeout)
            except queue.Empty as exc:
                raise TimeoutError("extension response timeout") from exc
        finally:
            with self._ext_lock:
                self._ext_pending.pop(req_id, None)

    def ext_call(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> bytes:
        """Send extension request and return payload on success.

        This helper raises DExtCallError when extension response indicates
        an error (explicit ERR flag or non-zero status).
        """
        resp = self.ext_request(
            ext_id=ext_id,
            cmd_id=cmd_id,
            payload=payload,
            fid=fid,
            timeout=timeout,
            ack_mode=ack_mode,
            ack_timeout=ack_timeout,
        )
        if resp.is_error or resp.status != 0:
            raise DExtCallError(resp)
        return resp.payload

    def ext_call_decode(
        self,
        ext_id: int,
        cmd_id: int,
        payload: bytes,
        decode: Callable[[bytes], T],
        fid: int = 8,
        timeout: float = 1.0,
        ack_mode: str = "auto",
        ack_timeout: float = 1.0,
    ) -> T:
        """Send extension request and decode successful response payload."""
        data = self.ext_call(
            ext_id=ext_id,
            cmd_id=cmd_id,
            payload=payload,
            fid=fid,
            timeout=timeout,
            ack_mode=ack_mode,
            ack_timeout=ack_timeout,
        )
        return decode(data)

    def _ext_dispatch_frame(self, frame: Any) -> bool:
        """Handle extension frame from comm user-frame listener path."""
        req = self._ext_decode(int(frame.fid), frame.data)
        if req is None:
            return False

        if (req.flags & (_EXT_FLAG_RESP | _EXT_FLAG_ERR)) != 0:
            with self._ext_lock:
                pending = self._ext_pending.get(req.req_id)
            if pending is None:
                return False
            pending.put(
                DExtResponse(
                    ext_id=req.ext_id,
                    cmd_id=req.cmd_id,
                    req_id=req.req_id,
                    status=req.status,
                    payload=req.payload,
                    fid=req.fid,
                    is_error=bool(req.flags & _EXT_FLAG_ERR),
                )
            )
            return True

        with self._ext_lock:
            handler = self._ext_handlers.get(req.ext_id)

        if handler is None:
            return False

        ret = handler(req)

        if (req.flags & _EXT_FLAG_REQ) == 0:
            return True

        if ret is None:
            return True

        status = 0
        resp_payload: bytes
        if isinstance(ret, tuple):
            status, resp_payload = ret
        else:
            resp_payload = ret

        if not isinstance(resp_payload, bytes):
            raise TypeError("extension response payload must be bytes")

        flags = _EXT_FLAG_RESP if status == 0 else _EXT_FLAG_ERR
        resp_data = self._ext_encode(
            ext_id=req.ext_id,
            cmd_id=req.cmd_id,
            flags=flags,
            req_id=req.req_id,
            status=status & 0xFF,
            payload=resp_payload,
        )
        self.send_user_frame(
            fid=req.fid,
            payload=resp_data,
            ack_mode="disabled",
            ack_timeout=0.0,
        )
        return True

    def register_plugin(
        self,
        plugin: "INxscopePlugin",
        frame_ids: list[int] | tuple[int, ...] | set[int] | None = None,
    ) -> str:
        """Register plugin and optional user-frame handler."""
        name = getattr(plugin, "name", plugin.__class__.__name__)
        listener_id: int | None = None

        with self._plugins_lock:
            if name in self._plugins:
                raise ValueError(f"plugin already registered: {name}")

            cb = getattr(plugin, "on_user_frame", None)
            if callable(cb):
                listener_id = self.add_user_frame_listener(cb, frame_ids)
            self._plugins[name] = (plugin, listener_id)

        try:
            cb_register = getattr(plugin, "on_register", None)
            if callable(cb_register):
                cb_register(self._control)

            if self.connected and self.dev is not None:
                cb_connect = getattr(plugin, "on_connect", None)
                if callable(cb_connect):
                    cb_connect(self.dev)
        except Exception:
            self.unregister_plugin(name)
            raise

        return name

    def unregister_plugin(self, name: str) -> bool:
        """Unregister plugin by name."""
        with self._plugins_lock:
            if name not in self._plugins:
                return False
            plugin, listener_id = self._plugins.pop(name)

        if listener_id is not None:
            self.remove_user_frame_listener(listener_id)

        if self.connected:
            cb_disconnect = getattr(plugin, "on_disconnect", None)
            if callable(cb_disconnect):
                cb_disconnect()

        cb_unregister = getattr(plugin, "on_unregister", None)
        if callable(cb_unregister):
            cb_unregister()

        return True

    def dev_channel_get(self, chid: int) -> "DeviceChannel | None":
        """Get a channel info.

        :param chid: the channel ID
        """
        assert self.dev
        return self.dev.channel_get(chid)

    def stream_start(self) -> None:
        """Start a data stream.

        Before starting the stream, the buffered channel configuration
        is applied to the device.
        """
        if not self._stream_started:
            # initialize stream
            self.channels_write()

            # start request for nxslib
            self._stream_start()

            # start stream thread
            self._thrd.thread_start()

            self._stream_started = True

    def stream_stop(self) -> None:
        """Stop a data stream."""
        if self._stream_started is True:
            # stop request for nxslib
            self._stream_stop()

            # stop stream thread
            self._thrd.thread_stop()

            self._stream_started = False

    def stream_sub(self, chan: int) -> queue.Queue[Any]:
        """Subscribe to a given channel.

        :param chid: the channel ID
        """
        subq: queue.Queue[Any] = queue.Queue()

        with self._queue_lock:
            if chan not in self._sub_q:
                self._sub_q[chan] = []
            self._sub_q[chan].append(subq)

        return subq

    def stream_unsub(self, subq: queue.Queue[Any]) -> None:
        """Unsubscribe from a given channel.

        :param subq: the queue instance that was used with the channel
        """
        with self._queue_lock:
            for sub in self._sub_q.values():
                if subq in sub:
                    sub.remove(subq)
                    break

    def ext_channel_add(self, chan: int) -> None:
        """Register extension channel ID for plugin-produced stream data."""
        if chan < 0:
            raise ValueError("chan must be >= 0")

        with self._queue_lock:
            if chan not in self._sub_q:
                self._sub_q[chan] = []

    def ext_publish_numpy(
        self,
        chan: int,
        data: DNxscopeStreamBlock | list[DNxscopeStreamBlock],
    ) -> None:
        """Publish NumPy stream blocks to extension channel subscribers."""
        payload: list[DNxscopeStreamBlock]

        if isinstance(data, list):
            payload = data
        else:
            payload = [data]

        with self._queue_lock:
            if chan not in self._sub_q:
                self._sub_q[chan] = []
            for que in self._sub_q[chan]:
                que.put(payload)

    def ext_publish_legacy(
        self,
        chan: int,
        data: DNxscopeStream | list[DNxscopeStream],
    ) -> None:
        """Publish legacy stream samples to extension channel subscribers."""
        payload: list[DNxscopeStream]

        if isinstance(data, list):
            payload = data
        else:
            payload = [data]

        with self._queue_lock:
            if chan not in self._sub_q:
                self._sub_q[chan] = []
            for que in self._sub_q[chan]:
                que.put(payload)

    def channels_default_cfg(self, writenow: bool = False) -> None:
        """Set default channels configuration.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.
        :param writenow: write channels configuration now
        """
        self._comm.channels_default_cfg()

        if writenow:
            # write channels configuration
            self.channels_write()

    def ch_enable(
        self, chans: list[int] | int, writenow: bool = False
    ) -> None:
        """Enable a given channels.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.

        :param chans: single channel ID or list with channels IDs
        :param writenow: write channels configuration now
        """
        self._comm.ch_enable(chans)

        if writenow:
            # write channels configuration
            self.channels_write()

    def ch_disable(
        self, chans: list[int] | int, writenow: bool = False
    ) -> None:
        """Disable a given channels.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.

        :param chans: single channel ID or list with channels IDs
        :param writenow: write channels configuration now
        """
        self._comm.ch_disable(chans)

        if writenow:
            # write channels configuration
            self.channels_write()

    def ch_disable_all(self, writenow: bool = False) -> None:
        """Disable all channels.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.

        :param writenow: write channels configuration now
        """
        self._comm.ch_disable_all()

        if writenow:
            # write channels configuration
            self.channels_write()

    def ch_divider(
        self, chans: list[int] | int, div: int, writenow: bool = False
    ) -> None:
        """Configure divider for a given channels.

        The effects of this method are buffered and will
        be applied to the device just before the stream starts
        or can be forced to write with writenow flag.

        :param chans: single channel ID or list with channels IDs
        :param div: divider value to be set
        :param writenow: write channels configuration now
        """
        self._comm.ch_divider(chans, div)

        if writenow:
            # write channels configuration
            self.channels_write()

    def channels_write(self) -> None:
        """Write channels configuration."""
        self._comm.channels_write()
