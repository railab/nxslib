"""Module containing the NxScope data parser."""

import struct
from dataclasses import dataclass
from typing import Any

import numpy as np

from nxslib.dev import Device, DeviceChannel
from nxslib.proto.iframe import DParseFrame, EParseId, ICommFrame
from nxslib.proto.iparse import (
    DParseStream,
    DParseStreamBlock,
    DParseStreamData,
    DParseStreamNumpy,
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


@dataclass(frozen=True)
class _NumpyChanDecode:
    """Cached NumPy decode descriptor for a single channel."""

    fingerprint: tuple[int, int, int]
    chan: int
    decode: DsfmtItem
    vdim: int
    mlen: int
    data_bytes: int
    packet_bytes: int
    fallback_fmt: str
    numeric_fast: bool
    np_dtype: np.dtype[Any] | None
    needs_scale: bool
    scale: float
    out_dtype: np.dtype[Any]
    meta_scalar_fmt: str | None


###############################################################################
# Class: Parser
###############################################################################


class Parser(ICommParse):
    """A class used to a represent NxScope parser."""

    _NUMPY_DTYPE_MAP: dict[str, np.dtype[Any]] = {
        "B": np.dtype(np.uint8),
        "b": np.dtype(np.int8),
        "H": np.dtype("<u2"),
        "h": np.dtype("<i2"),
        "I": np.dtype("<u4"),
        "i": np.dtype("<i4"),
        "Q": np.dtype("<u8"),
        "q": np.dtype("<i8"),
        "f": np.dtype("<f4"),
        "d": np.dtype("<f8"),
    }
    _META_SCALAR_NUMPY_DTYPE: dict[int, np.dtype[Any]] = {
        1: np.dtype(np.uint8),
        2: np.dtype(np.uint16),
        4: np.dtype(np.uint32),
        8: np.dtype(np.uint64),
    }
    _META_SCALAR_STRUCT_FMT: dict[int, str] = {
        1: "<B",
        2: "<H",
        4: "<I",
        8: "<Q",
    }

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
        self._numpy_chan_decode_cache: list[_NumpyChanDecode | None] = [
            None
        ] * 256

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
        if frame is None:
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

        # return samples data and flags (always first byte in stream data)
        return DParseStream(flags=frame.data[0], samples=samples)

    def frame_stream_decode_numpy(  # noqa: C901
        self, frame: DParseFrame, dev: Device
    ) -> DParseStreamNumpy | None:
        """Decode a stream frame into NumPy per-channel blocks."""
        if frame is None:
            return None
        if frame.fid != EParseId.STREAM:
            return None
        if not frame.data:
            return None

        frame_data = frame.data
        frame_len = len(frame_data)
        chan_counts = [0] * 256
        chan_info: list[_NumpyChanDecode | None] = [None] * 256
        active_chanids: list[int] = []

        # Pass 1: count samples per channel.
        i = 1
        while i < frame_len:
            chanid = frame_data[i]
            i += 1

            info = chan_info[chanid]
            if info is None:
                chan = dev.channel_get(chanid)
                assert chan
                info = self._numpy_chan_decode_get(chan)
                chan_info[chanid] = info
                active_chanids.append(chanid)

            i += info.packet_bytes
            chan_counts[chanid] += 1

        # Allocate output blocks per channel.
        data_out: list[np.ndarray[Any, Any] | None] = [None] * 256
        meta_out: list[np.ndarray[Any, Any] | None] = [None] * 256
        write_idx = [0] * 256
        for chanid in active_chanids:
            nsamples = chan_counts[chanid]
            info = chan_info[chanid]
            assert info is not None
            data_out[chanid] = np.empty(
                (nsamples, info.vdim), dtype=info.out_dtype
            )

            if info.mlen == 0:
                meta_out[chanid] = None
            elif info.meta_scalar_fmt is not None:
                meta_out[chanid] = np.empty(
                    (nsamples, 1),
                    dtype=self._META_SCALAR_NUMPY_DTYPE[info.mlen],
                )
            else:
                meta_out[chanid] = np.empty(
                    (nsamples, info.mlen), dtype=np.uint8
                )

        # Pass 2: decode and fill.
        i = 1
        while i < frame_len:
            chanid = frame_data[i]
            i += 1
            info = chan_info[chanid]
            assert info is not None
            row = write_idx[chanid]
            darray = data_out[chanid]
            assert darray is not None
            data_bytes = info.data_bytes
            mlen = info.mlen
            meta_scalar_fmt = info.meta_scalar_fmt

            data_start = i
            i += data_bytes

            if info.numeric_fast:
                assert info.np_dtype is not None
                sample = np.frombuffer(
                    frame_data,
                    dtype=info.np_dtype,
                    count=info.vdim,
                    offset=data_start,
                )
                if info.needs_scale:
                    darray[row, :] = sample / info.scale
                else:
                    darray[row, :] = sample
            else:
                unpacked = struct.unpack_from(
                    info.fallback_fmt, frame_data, data_start
                )
                formatted = self._stream_data_get(info.decode, unpacked)
                darray[row, :] = formatted

            marray = meta_out[chanid]
            if marray is not None:
                if meta_scalar_fmt is not None:
                    marray[row, 0] = struct.unpack_from(
                        meta_scalar_fmt, frame_data, i
                    )[0]
                else:
                    marray[row, :] = np.frombuffer(
                        frame_data,
                        dtype=np.uint8,
                        count=mlen,
                        offset=i,
                    )
            i += mlen
            write_idx[chanid] = row + 1

        blocks: list[DParseStreamBlock] = []
        for chanid in active_chanids:
            info = chan_info[chanid]
            assert info is not None
            darray = data_out[chanid]
            assert darray is not None
            blocks.append(
                DParseStreamBlock(
                    chan=info.chan,
                    dtype=int(info.decode.dtype),
                    vdim=info.vdim,
                    mlen=info.mlen,
                    data=darray,
                    meta=meta_out[chanid],
                )
            )

        return DParseStreamNumpy(flags=frame.data[0], blocks=blocks)

    def _numpy_chan_decode_get(self, chan: DeviceChannel) -> _NumpyChanDecode:
        """Get or refresh cached decode descriptor for a channel."""
        chan_data = chan.data
        chanid = chan_data.chan
        fingerprint = (chan_data.dtype, chan_data.vdim, chan_data.mlen)

        cached = self._numpy_chan_decode_cache[chanid]
        if cached is not None and cached.fingerprint == fingerprint:
            return cached

        decode = dsfmt_get(chan_data.dtype, self._user_types)
        vdim = chan_data.vdim
        mlen = chan_data.mlen

        fallback_fmt = "<"
        if vdim and not decode.user:
            fallback_fmt += str(vdim)
        fallback_fmt += decode.dsfmt

        numeric_fast = (
            decode.dtype == EParseDataType.NUM
            and not decode.user
            and decode.dsfmt in self._NUMPY_DTYPE_MAP
        )
        np_dtype: np.dtype[Any] | None = None
        needs_scale = False
        scale = 1.0
        out_dtype: np.dtype[Any] = np.dtype(np.object_)
        if numeric_fast:
            np_dtype = self._NUMPY_DTYPE_MAP[decode.dsfmt]
            scale = float(decode.scale) if decode.scale else 1.0
            needs_scale = scale != 1.0
            if needs_scale:
                out_dtype = np.dtype(np.float64)
            else:
                out_dtype = np_dtype

        desc = _NumpyChanDecode(
            fingerprint=fingerprint,
            chan=chanid,
            decode=decode,
            vdim=vdim,
            mlen=mlen,
            data_bytes=decode.slen * vdim,
            packet_bytes=(decode.slen * vdim) + mlen,
            fallback_fmt=fallback_fmt,
            numeric_fast=numeric_fast,
            np_dtype=np_dtype,
            needs_scale=needs_scale,
            scale=scale,
            out_dtype=out_dtype,
            meta_scalar_fmt=self._META_SCALAR_STRUCT_FMT.get(mlen),
        )
        self._numpy_chan_decode_cache[chanid] = desc
        return desc

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
