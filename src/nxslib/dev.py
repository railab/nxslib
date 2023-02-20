"""Module containint NxScope the device implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

###############################################################################
# Enum: EDeviceChannelType
###############################################################################


class EDeviceChannelType(Enum):
    """A NxScope channel data type."""

    UNDEF = 0
    NONE = 1
    UINT8 = 2
    INT8 = 3
    UINT16 = 4
    INT16 = 5
    UINT32 = 6
    INT32 = 7
    UINT64 = 8
    INT64 = 9
    FLOAT = 10
    DOUBLE = 11
    UB8 = 12
    B8 = 13
    UB16 = 14
    B16 = 15
    UB32 = 16
    B32 = 17
    CHAR = 18
    WCHAR = 19

    # user specific types starts from here

    USER1 = 20
    USER2 = 21
    USER3 = 22
    USER4 = 23
    USER5 = 24
    USER6 = 25
    USER7 = 26
    USER8 = 27
    USER9 = 28
    USER10 = 29
    USER11 = 30
    USER12 = 31

    # max possible = 31


###############################################################################
# Enum: EDeviceFlags
###############################################################################


class EDeviceFlags(Enum):
    """A NxScope device flags."""

    NONE = 0
    DIVIDER_SUPPORT = 1 << 0
    ACK_SUPPORT = 1 << 1


###############################################################################
# Class: DDeviceChannelData
###############################################################################


@dataclass
class DDeviceChannelData:
    """A NxScope channel data."""

    chan: int
    _type: int
    vdim: int
    name: str
    en: bool = False
    div: int = 0
    mlen: int = 0
    dtype: int = field(init=False)
    type_res: int = field(init=False)
    critical: bool = field(init=False)
    is_valid: bool = field(init=False)
    is_numerical: bool = field(init=False)
    _initdone: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """Post-init processing."""
        self.dtype = self._type & 0x1F
        self.critical = bool(self._type & 0x80)
        self.type_res = self._type & 0x60
        self.is_valid = self.dtype is not EDeviceChannelType.UNDEF.value
        self.is_numerical = self.dtype not in [
            EDeviceChannelType.UNDEF.value,
            EDeviceChannelType.NONE.value,
            EDeviceChannelType.CHAR.value,
            EDeviceChannelType.WCHAR.value,
        ]
        self._initdone = True

    def __setattr__(self, name: str, value: Any) -> None:
        """Make some field read-only."""
        if self._initdone:
            if name not in ["div", "en"]:
                msg = name + " proprety is read-only"
                raise TypeError(msg)
        self.__dict__[name] = value


###############################################################################
# Class: DDeviceData
###############################################################################


@dataclass
class DDeviceData:
    """A NxScope device data."""

    chmax: int
    flags: int
    rxpadding: int
    div_supported: bool = field(init=False)
    ack_supported: bool = field(init=False)
    _initdone: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Post-init processing."""
        self.div_supported = bool(
            self.flags & EDeviceFlags.DIVIDER_SUPPORT.value
        )
        self.ack_supported = bool(self.flags & EDeviceFlags.ACK_SUPPORT.value)
        self._initdone = True

    def __setattr__(self, name: str, value: Any) -> None:
        """Make some field read-only."""
        if self._initdone:
            # all fields read-only
            msg = name + " proprety is read-only"
            raise TypeError(msg)
        self.__dict__[name] = value


###############################################################################
# Class: IDeviceChannelFuncData
###############################################################################


@dataclass
class DDeviceChannelFuncData:
    """A NxScope channel function data."""

    data: tuple[Any, ...] = ()
    meta: tuple[Any, ...] = ()


###############################################################################
# Class: IDeviceChannelFunc
###############################################################################


class IDeviceChannelFunc(ABC):
    """An abstract class used to a represent nxslib channel function."""

    @abstractmethod
    def reset(self) -> None:
        """Reset channel state."""

    @abstractmethod
    def get(self, cntr: int) -> DDeviceChannelFuncData | None:
        """Get channel stream data."""


###############################################################################
# Class: DeviceChannel
###############################################################################


class DeviceChannel:
    """A class used to represent a nxslib device channel."""

    def __init__(
        self,
        chan: int,
        _type: int,
        vdim: int,
        name: str,
        en: bool = False,
        div: int = 0,
        mlen: int = 0,
        func: IDeviceChannelFunc | None = None,
    ):
        """Initialize a NxScope device channel.

        :param type: channel id
        :param _type: channel type
        :param vdim: sample data dimension
        :param name: channel name
        :param en: enable or disable channel
        :param div: samples divider
        :param mlen: size of the channel metadata
        :param func: function used to get data from the channel
        """
        # force name to be string
        if not name:
            name = ""
        self._data = DDeviceChannelData(
            chan, _type, vdim, name, bool(en), div, mlen
        )

        self._func = func
        self._cntr = 0

    def __str__(self) -> str:
        """Get channel string represenation."""
        _str = "DeviceChannel " + "(" + str(self.data) + ")"
        return _str

    @property
    def data(self) -> DDeviceChannelData:
        """Get channel specific data."""
        return self._data

    def reset(self) -> None:
        """Reset channel state."""
        if self._func is not None:
            # reset func state if func attached
            self._func.reset()

    def data_get(self) -> DDeviceChannelFuncData | None:
        """Generate channel data."""
        if self._func is not None:
            ret = self._func.get(self._cntr)
            self._cntr += 1
        else:
            ret = None

        return ret


###############################################################################
# Class: Device
###############################################################################


class Device:
    """A class used to represent a nxslib device."""

    def __init__(
        self,
        chmax: int,
        flags: int,
        rxpadding: int,
        channels: list[DeviceChannel],
    ):
        """Initialize the NxScope device.

        :param chmax: the maximum number of supported channels
        :param flags: device flags
        :param rxpadding: RX padding
        :param channels: device channels
        """
        # all channels should have unique ids
        chanids = []
        for chan in channels:
            chanids.append(chan.data.chan)
        assert len(set(chanids)) == len(chanids)
        # channels must mach chmax
        assert len(channels) == chmax

        # initialize data
        self._data = DDeviceData(chmax, flags, rxpadding)

        self._channels = channels

        self._channels_lock = Lock()

    def __str__(self) -> str:
        """Get device string represenation."""
        return "Device:" + " (" + str(self.data) + ")"

    @property
    def data(self) -> DDeviceData:
        """Get device specific data."""
        return self._data

    @property
    def channels_en(self) -> list[bool]:
        """Get channels enable state."""
        ret = []
        with self._channels_lock:
            for chan in self._channels:
                ret.append(chan.data.en)
        return ret

    @property
    def channels_div(self) -> list[int]:
        """Get channels divider state."""
        ret = []
        with self._channels_lock:
            for chan in self._channels:
                ret.append(chan.data.div)
        return ret

    def div_channels_update(self, div: list[int]) -> None:
        """Update div state for channels."""
        with self._channels_lock:
            assert len(div) == len(self._channels)
            for i, chdiv in enumerate(div):
                self._channels[i].data.div = chdiv

    def en_channels_update(self, en: list[bool]) -> None:
        """Update enable state for channels."""
        with self._channels_lock:
            assert len(en) == len(self._channels)
            for i, chen in enumerate(en):
                self._channels[i].data.en = chen

    def reset(self) -> None:
        """Reset device state."""
        with self._channels_lock:
            for chan in self._channels:
                # reset channels
                chan.reset()

    def channel_get(self, chid: int) -> DeviceChannel | None:
        """Get device channel.

        :param chid: channel ID
        """
        try:
            with self._channels_lock:
                return self._channels[chid]
        except IndexError:
            return None
