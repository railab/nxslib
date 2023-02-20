"""Nxslib interface abstract class."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from nxslib.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

###############################################################################
# Class: CommInterfaceCommon
###############################################################################


class CommInterfaceCommon:
    """A class with a common Nxslib interface logic."""

    def __init__(
        self, read: "Callable[[], bytes]", write: "Callable[[bytes], None]"
    ) -> None:
        """Initialize a common communication interface.

        :param read: interface specific read
        :param write: interface specific method
        """
        self._write_padding = 0
        self._fread = read
        self._fwrite = write

    @property
    def write_padding(self) -> int:
        """Get the write padding."""
        return self._write_padding

    @write_padding.setter
    def write_padding(self, val: int) -> None:
        """Set the write padding.

        :param data: write padding to set
        """
        self._write_padding = val

    def data_align(self, data: bytes) -> bytes:
        """Align data according to the configured write padding.

        :param data: bytes to be aligned
        """
        if self._write_padding:
            modlen = len(data) % self._write_padding
            if modlen:
                padding = self._write_padding - modlen
                # add padding
                data += b"\x00" * padding
        return data

    def read(self) -> bytes:
        """Read data from the interface."""
        data = self._fread()
        if len(data) > 0:
            logger.debug("read=%s", data)

        return data

    def write(self, data: bytes) -> None:
        """Write data to the interface.

        :param data: bytes to send
        """
        # align data
        data = self.data_align(data)
        logger.debug("write=%s", data)
        self._fwrite(data)


###############################################################################
# Class: ICommInterface
###############################################################################


class ICommInterface(ABC, CommInterfaceCommon):
    """An abstract class used to a represent the Nxslib interface."""

    def __init__(self) -> None:
        """Initialize an abstract communication interface."""
        CommInterfaceCommon.__init__(self, self._read, self._write)

    @abstractmethod
    def start(self) -> None:
        """Start the interface."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the interface."""

    @abstractmethod
    def drop_all(self) -> None:
        """Drop all frames."""

    @abstractmethod
    def _read(self) -> bytes:
        """Interface specific read method."""

    @abstractmethod
    def _write(self, data: bytes) -> None:
        """Interface specific write method.

        :param data: bytes to send
        """
