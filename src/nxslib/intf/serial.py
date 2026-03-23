"""Module containing the NxScope serial interface implementation."""

import serial  # type: ignore

from nxslib.intf.iintf import ICommInterface
from nxslib.logger import logger

###############################################################################
# Class: SerialDevice
###############################################################################


class SerialDevice(ICommInterface):
    """A class used to represent a serial port interface."""

    def __init__(
        self,
        port: str,
        baud: int = 115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
    ) -> None:
        """Intitialize a serial interface.

        :param port: path to the serial port device
        :param baud: baud rate
        :param bytesize: number of data bits
        :param parity: parity checking
        :param stopbits: number of stop bits
        """
        try:
            self._ser = serial.Serial(
                port,
                baud,
                timeout=1,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                write_timeout=1,
            )
        except Exception as exc:
            logger.error("Failed to open serial port: %s", str(exc))
            self._ser = None
            raise exc

        super().__init__()

    def __enter__(self) -> "SerialDevice":
        """Start on context manager entry."""
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        """Stop on context manager exit."""
        self.stop()

    def start(self) -> None:
        """Start the interface."""
        logger.debug("start serial interface")

    def stop(self) -> None:
        """Stop the interface."""
        logger.debug("Stop serial interface")
        if self._ser:
            self._ser.close()
            self._ser = None

    def drop_all(self) -> None:
        """Drop all frames."""
        if self._ser is None:
            return
        if self._ser.is_open is False:
            return
        try:
            self._ser.reset_input_buffer()
        except serial.SerialException as exc:
            logger.debug("SerialException ignored: %s", str(exc))

    def _read(self) -> bytes:
        """Interface specific read method."""
        if self._ser is None:
            return b""
        if self._ser.is_open is False:
            return b""
        try:
            pending = self._ser.in_waiting
            # Avoid busy loop when no data is pending: read(0) returns
            # immediately and can spin a CPU core in the recv thread.
            size = pending if pending > 0 else 1
            return self._ser.read(size)  # type: ignore
        except (serial.SerialException, TypeError) as exc:
            logger.debug("SerialException ignored: %s", str(exc))
            return b""

    def _write(self, data: bytes) -> None:
        """Interface specific write method.

        :param data: bytes to send
        """
        if self._ser is None:
            return
        if self._ser.is_open is False:
            return
        self._ser.write(data)
