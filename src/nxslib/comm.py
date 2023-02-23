"""Module containing the NxScope communication logic."""

import copy
import queue
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

from nxslib.dev import Device, DeviceChannel
from nxslib.logger import logger
from nxslib.proto.iframe import DParseFrame, DParseHdr, EParseError
from nxslib.proto.iparse import (
    DParseStream,
    EParseStreamFlags,
    ICommParse,
    ParseAck,
    ParseCmninfo,
)
from nxslib.thread import ThreadCommon

if TYPE_CHECKING:
    from nxslib.intf.iintf import ICommInterface

###############################################################################
# Class: DCommChannelsData
###############################################################################


@dataclass
class DCommChannelsData:
    """Channels management data."""

    en_now: list[bool]
    en_new: list[bool]
    div_now: list[int]
    div_new: list[int]


###############################################################################
# Class: CommHandler
###############################################################################


class CommHandler:
    """A class implementing the Nxslib communication glue logic."""

    def __init__(self, intf: "ICommInterface", parse: ICommParse):
        """Initialize communication glue logic.

        :param intf: instance of a communication interface
        :param parse: instance of a parser class
        """
        # started flag
        self._started = False

        self._thrd = ThreadCommon(self._recv_thread, name="recv")

        self._intf = intf
        self._parse = parse

        self._prev_read = b""
        self._dev: Device | None = None

        # recv queue
        self._q: queue.Queue[DParseFrame] = queue.Queue()
        # stream frames queue
        self._q_stream: queue.Queue[DParseFrame] = queue.Queue()

        # channels configuration
        self._channels: DCommChannelsData
        self._channels_lock = Lock()

    def __del__(self) -> None:
        """Need to disconnect from the device."""
        self.disconnect()

    def _drop_all(self) -> None:
        """Drop all frames."""
        self._intf.drop_all()
        self._drop_all_frames()

    def _recv_thread(self) -> None:
        """Recv thread."""
        frame = self._read_frame()
        if frame:
            if self._parse.frame_is_stream(frame):
                # special queue for stream frames
                self._q_stream.put(frame)
            else:
                if self.dev is None and self._parse.frame_is_ack(frame):
                    # drop ACK frames if we dont have dev info yet
                    pass
                else:
                    self._q.put(frame)

    def _get_frame(self, timeout: float = 1.0) -> DParseFrame | None:
        """Get frame from queue."""
        try:
            frame = self._q.get(block=True, timeout=timeout)

        except queue.Empty:
            frame = None

        return frame

    def _get_stream_frame(self, timeout: float = 1.0) -> DParseFrame | None:
        """Get frame from stream queue."""
        try:
            frame = self._q_stream.get(block=True, timeout=timeout)

        except queue.Empty:
            frame = None

        return frame

    def _get_ack(self, timeout: float = 1.0) -> ParseAck:
        """Get ACK response."""
        # return ACK if ACK frames not supported or we don't know yet
        if self.dev is None or not self.dev.data.ack_supported:
            return ParseAck(True, 0)

        frame = self._get_frame(timeout)
        if frame is None:  # pragma: no cover
            return ParseAck(False, -1)

        ret = self._parse.frame_ack_decode(frame)
        if ret is None:  # pragma: no cover
            return ParseAck(False, -2)

        return ret

    def _read_hdr(self) -> tuple[DParseHdr, bytes] | tuple[None, None]:
        """Read hdr from interface."""
        # look for hdr in the recieved data
        while True:
            # start with previous data
            _bytes = self._prev_read

            while len(_bytes) < self._parse.frame.hdr_len:
                _bytes += self._intf.read()
                if not _bytes:
                    return None, None

            # find hdr candidate
            i = self._parse.frame.hdr_find(data=_bytes)
            if i < 0:  # pragma: no cover
                # not found - drop data from buffer
                self._prev_read = b""
                return None, None

            _bytes = _bytes[i:]

            hdr = self._parse.frame.hdr_decode(data=_bytes)
            if hdr.err is not EParseError.NOERR:  # pragma: no cover
                # drop 1 byte from buffer
                self._prev_read = _bytes[1:]
                continue

            # valid hdr
            return hdr, _bytes

    def _read_frame(self) -> DParseFrame | None:
        """Read frame from interface."""
        # read hdr from data
        hdr, _bytes = self._read_hdr()
        if hdr is None or _bytes is None:
            return None

        # read the rest of frame
        while len(_bytes) < hdr.flen:  # pragma: no cover
            rdata = self._intf.read()
            if not rdata:
                # buffer empty
                break

            # accumulate data
            _bytes += rdata

        # return none and store captured data
        if len(_bytes) < hdr.flen:  # pragma: no cover
            self._prev_read = _bytes
            return None

        # get possible frame
        possible_frame = _bytes[: hdr.flen]
        frame_decoded = self._parse.frame.frame_decode(possible_frame)
        if frame_decoded.err is not EParseError.NOERR:  # pragma: no cover
            # corrupted data or no valid frame - drop one byte
            self._prev_read = _bytes[1:]
            return None

        # drop frame data from buffer and return decoded frame
        self._prev_read = _bytes[hdr.flen :]
        return frame_decoded

    def _drop_all_frames(self) -> None:
        cntr = 4
        while cntr > 0:
            ret = self._get_frame(timeout=0.1)
            if not ret:  # pragma: no cover
                cntr -= 1
        cntr = 4
        while cntr > 0:
            ret = self._get_stream_frame(timeout=0.1)
            if not ret:  # pragma: no cover
                cntr -= 1

    def _devinfo_get(self) -> Device | None:
        """Get nxslib dev info."""
        logger.info("get cmn info")

        # get cmn info
        frame = self._nxslib_cmninfo()
        if frame is None:  # pragma: no cover
            return None

        # reconfigure interface if writepadding supported
        padding_change = self._intf.write_padding != frame.rxpadding
        if frame.rxpadding > 0 and padding_change:  # pragma: no cover
            logger.info("reconfigure intf: write_padding=%d", frame.rxpadding)
            self._intf.write_padding = frame.rxpadding

            # Make sure that nxslib handled all previous frames
            # that was send before adding rxpadding.
            # If nxslib uses RX DMA then RX trigger can be issued
            # only after sufficient bytes was received.
            # This can cause spurious frames in our receive buffer,
            # so we want to make sure that we have a fresh start from here

            # trigger RX with dummy data write
            self._intf.write(b"\x00" * frame.rxpadding)

        # drop all frames
        self._drop_all()

        # get channels info
        channels: list[DeviceChannel] = []
        for i in range(frame.chmax):
            chan = None
            while chan is None:
                chan = self._nxslib_chinfo(i)

            logger.info("chan %d %s", i, str(chan))
            channels.append(chan)

        # return nxslib device
        return Device(
            chmax=frame.chmax,
            flags=frame.flags,
            rxpadding=frame.rxpadding,
            channels=channels,
        )

    def _stop(self) -> None:
        """Stop nxslib."""
        if self._started is True:
            # stop recv thread
            self._thrd.thread_stop()

            # stop intf
            self._intf.stop()

            # drop all pending data
            self._drop_all()

            self._started = False
            self._dev = None

    def _start(self) -> None:
        """Start nxslib."""
        if not self._started:
            # start interface
            self._intf.start()

            # start recv thread
            self._thrd.thread_start()

            # send stop request
            self.stream_stop()

            # drop all pending data
            self._drop_all()

            # get info frame
            timeout = 5
            while self._dev is None:
                if timeout < 0:  # pragma: no cover
                    msg = (
                        "Failed to get device info, check"
                        " your interface configuration"
                    )
                    raise TimeoutError(msg)
                self._dev = self._devinfo_get()
                timeout -= 1

            # initialize channels state
            self._channels_init(self._dev)

            self._started = True

    # TODO: use decorator to handle ack responses
    def _channel_enable(
        self, enable: tuple[int, bool] | list[bool]
    ) -> ParseAck:
        """Channel enable."""
        assert self.dev

        fwrite = self._parse.frame_enable(enable, self.dev.data.chmax)
        self._intf.write(fwrite)

        ack = self._get_ack(timeout=1.0)
        return ack

    def _channel_div(self, div: tuple[int, int] | list[int]) -> ParseAck:
        """Channel divider."""
        assert self.dev

        fwrite = self._parse.frame_div(div, self.dev.data.chmax)
        self._intf.write(fwrite)

        ack = self._get_ack(timeout=1.0)
        return ack

    def _nxslib_cmninfo(self) -> ParseCmninfo | None:
        """Get nxslib cmninfo."""
        fwrite = self._parse.frame_cmninfo()
        self._intf.write(fwrite)

        fread = self._get_frame(timeout=1.0)
        if fread is None:  # pragma: no cover
            return None

        return self._parse.frame_cmninfo_decode(fread)

    def _nxslib_chinfo(self, chan: int) -> DeviceChannel | None:
        """Get nxslib chinfo.

        :param chan: channel ID
        """
        chinfo = self._parse.frame_chinfo(chan)
        self._intf.write(chinfo)

        fread = self._get_frame(timeout=1.0)
        if fread is None:  # pragma: no cover
            return None

        return self._parse.frame_chinfo_decode(fread, chan)

    def _nxslib_channels_enable(self) -> None:
        with self._channels_lock:
            assert self._channels
            j = 0
            k = 0
            for i, _ in enumerate(self._channels.en_now):
                if self._channels.en_new[i] != self._channels.en_now[i]:
                    j += 1
                    k = i

            if j == 1:
                en_req_t = (k, self._channels.en_new[k])
                ret = self._channel_enable(en_req_t)
            else:
                en_req_l = self._channels.en_new
                ret = self._channel_enable(en_req_l)
            if ret.state is False:  # pragma: no cover
                return

            # update states
            self._channels.en_now = copy.deepcopy(self._channels.en_new)
            assert self.dev
            self.dev.en_channels_update(self._channels.en_now)

    def _nxslib_channels_div(self) -> None:
        """Send nxslib div."""
        with self._channels_lock:
            assert self._channels
            j = 0
            k = 0
            for i, _ in enumerate(self._channels.div_now):
                if self._channels.div_new[i] != self._channels.div_now[i]:
                    j += 1
                    k = i

            if j == 1:
                div_req_t = (k, self._channels.div_new[k])
                ret = self._channel_div(div_req_t)
            else:
                div_req_l = self._channels.div_new
                ret = self._channel_div(div_req_l)
            if ret.state is False:  # pragma: no cover
                return

            # update states
            self._channels.div_now = copy.deepcopy(self._channels.div_new)
            assert self.dev
            self.dev.div_channels_update(self._channels.div_now)

    def _ch_divider_default(self) -> None:
        """Set all channels divider to default."""
        with self._channels_lock:
            assert self._channels
            for i, _ in enumerate(self._channels.div_new):
                self._channels.div_new[i] = 0

    def _channels_init(self, dev: Device) -> None:
        """Initialize channels.

        :param dev: Nxscope device instance
        """
        with self._channels_lock:
            self._channels = DCommChannelsData(
                copy.deepcopy(dev.channels_en),
                copy.deepcopy(dev.channels_en),
                copy.deepcopy(dev.channels_div),
                copy.deepcopy(dev.channels_div),
            )

    @property
    def dev(self) -> Device | None:
        """Get device info."""
        return self._dev

    def connect(self) -> None:
        """Connect to a nxslib device."""
        self._start()
        assert self._dev

    def disconnect(self) -> None:
        """Disconnect from a nxslib device."""
        try:
            # TODO: revisit.
            # This is a dirty fix for occasional RuntimeError in
            # thread.thread_stop(). I wasn't able to find the real cause
            # of this problem.
            self._stop()
        except RuntimeError:  # pragma: no cover
            pass

    def flags_is_overflow(self, flag: int) -> bool:
        """Return stream OVERFLOW flag state.

        :param data: flag to check
        """
        return bool(flag & EParseStreamFlags.OVERFLOW.value)

    def stream_start(self) -> ParseAck | None:
        """Start stream."""
        fwrite = self._parse.frame_start(True)
        self._intf.write(fwrite)

        ack = self._get_ack(timeout=1.0)
        return ack

    def stream_stop(self) -> ParseAck | None:
        """Stop stream."""
        fwrite = self._parse.frame_start(False)
        self._intf.write(fwrite)

        ack = self._get_ack(timeout=1.0)
        return ack

    def stream_data(self) -> DParseStream | None:
        """Get stream data."""
        assert self.dev

        # separate queue for stream frames
        frame = self._get_stream_frame()
        if not frame:
            return None

        assert self._parse.frame_is_stream(frame)
        ret = self._parse.frame_stream_decode(frame, self.dev)

        return ret

    def channels_write(self) -> None:
        """Initialize channels for stream.

        :param dev: Nxscope device instance
        """
        assert self.dev
        if self.dev.data.div_supported:
            # send div request
            self._nxslib_channels_div()

        # send enable request
        self._nxslib_channels_enable()

    def ch_enable(self, chans: list[int] | int) -> None:
        """Enable specific channel.

        :param chans: single channel ID or a list with channels IDs
        """
        with self._channels_lock:
            assert self._channels
            if isinstance(chans, list):
                for chan in chans:
                    self._channels.en_new[chan] = True
            elif isinstance(chans, int):
                self._channels.en_new[chans] = True
            else:
                raise TypeError

    def ch_disable(self, chans: list[int] | int) -> None:
        """Disable specific channel.

        :param chans: single channel ID or a list with channels IDs
        """
        with self._channels_lock:
            assert self._channels
            if isinstance(chans, list):
                for chan in chans:
                    self._channels.en_new[chan] = False
            elif isinstance(chans, int):
                self._channels.en_new[chans] = False
            else:
                raise TypeError

    def ch_divider(self, chans: list[int] | int, div: int) -> None:
        """Set channel divider.

        :param chans: single channel ID or a list with channels IDs
        :param div: divider value to be set
        """
        if div < 0 or div > 255:
            raise ValueError

        assert self.dev
        if not self.dev.data.div_supported and div > 0:
            logger.error("divider not supported by device !")

        with self._channels_lock:
            assert self._channels
            if isinstance(chans, list):
                for chan in chans:
                    self._channels.div_new[chan] = div
            elif isinstance(chans, int):
                self._channels.div_new[chans] = div
            else:
                raise TypeError

    def ch_enable_all(self) -> None:
        """Enable all channels."""
        assert self.dev
        for chan in range(self.dev.data.chmax):
            self.ch_enable(chan)

    def ch_disable_all(self) -> None:
        """Disale all channels."""
        assert self.dev
        for chan in range(self.dev.data.chmax):
            self.ch_disable(chan)

    def ch_is_enabled(self, chan: int) -> bool:
        """Return True if channel is enabled.

        :param chan: channel ID
        """
        with self._channels_lock:
            assert self._channels
            return self._channels.en_now[chan]

    def ch_div_get(self, chan: int) -> int:
        """Get channel divider.

        :param chid: the channel ID
        """
        with self._channels_lock:
            assert self._channels
            return self._channels.div_now[chan]

    def channels_default_cfg(self) -> None:
        """Set default channels configuration."""
        # disable all channels
        self.ch_disable_all()
        # default divider
        self._ch_divider_default()
