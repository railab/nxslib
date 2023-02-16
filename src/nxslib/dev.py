"""Module containint NxScope the device implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
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
    USER = 20

    # max possible
    LAST = 31


###############################################################################
# Enum: EDeviceFlags
###############################################################################


class EDeviceFlags(Enum):
    """A NxScope device flags."""

    NONE = 0
    DIVIDER_SUPPORT = 1 << 0
    ACK_SUPPORT = 1 << 1


###############################################################################
# Class: DDeviceData
###############################################################################


@dataclass
class DDeviceData:
    """A NxScope device data."""

    chmax: int
    flags: int
    rxpadding: int
    channels: list


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

    @property
    def dtype(self) -> int:
        """Reserved for future use."""
        return self._type & 0x1F

    @property
    def critical(self) -> bool:
        """Return True if the channel is critical."""
        return bool(self._type & 0x80)

    @property
    def type_res(self) -> int:
        """Reserved for future use."""
        return self._type & 0x60

    @property
    def is_valid(self) -> bool:
        """Return True if the channel is valid (dtype should be defined)."""
        return self.dtype is not EDeviceChannelType.UNDEF.value

    @property
    def is_numerical(self) -> bool:
        """Return True if the channel is numerical."""
        if not self.is_valid:
            return False
        return self.dtype not in [
            EDeviceChannelType.NONE.value,
            EDeviceChannelType.CHAR.value,
            EDeviceChannelType.WCHAR.value,
        ]


###############################################################################
# Class: DeviceChannel
###############################################################################


class DeviceChannel(DDeviceChannelData):
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
        # assert isinstance(en, bool) # TODO: fixme
        super().__init__(chan, _type, vdim, name, bool(en), div, mlen)

        if func is not None:
            assert isinstance(func, IDeviceChannelFunc)

        # force name to be string
        if not self.name:
            self.name = ""

        self._func = func

        self._cntr = 0

    def __str__(self) -> str:
        """Get channel string represenation."""
        _str = (
            "DeviceChannel "
            + "("
            + "chan:"
            + str(self.chan)
            + " _type:"
            + str(self._type)
            + " vdim:"
            + str(self.vdim)
            + " name:"
            + str(self.name)
            + ")"
        )
        return _str

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


class Device(DDeviceData):
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
        super().__init__(chmax, flags, rxpadding, channels)

        assert len(self.channels) == self.chmax
        self.channels = []
        chanids = []
        for chan in channels:
            assert isinstance(chan, DeviceChannel)
            self.channels.append(chan)
            chanids.append(chan.chan)

        # all channels should have unique ids
        assert len(set(chanids)) == len(chanids)

    def __str__(self) -> str:
        """Get device string represenation."""
        _str = (
            "Device:"
            + " (chmax:"
            + str(self.chmax)
            + " flags:"
            + str(self.flags)
            + " rxpadding:"
            + str(self.rxpadding)
            + ")"
        )
        return _str

    @property
    def div_supported(self) -> bool:
        """Return True if divider is supported."""
        return bool(self.flags & EDeviceFlags.DIVIDER_SUPPORT.value)

    @property
    def ack_supported(self) -> bool:
        """Return True if ACK frames are supported."""
        return bool(self.flags & EDeviceFlags.ACK_SUPPORT.value)

    @property
    def channels_en(self) -> list[bool]:
        """Get channels enable state."""
        ret = []
        for chan in self.channels:
            ret.append(chan.en)
        return ret

    @property
    def channels_div(self) -> list[int]:
        """Get channels divider state."""
        ret = []
        for chan in self.channels:
            ret.append(chan.div)

        return ret

    def reset(self) -> None:
        """Reset device state."""
        for chan in self.channels:
            # reset channels
            chan.reset()

    def channel_get(self, chid: int) -> DeviceChannel | None:
        """Get device channel.

        :param chid: channel ID
        """
        try:
            return self.channels[chid]
        except IndexError:
            return None
