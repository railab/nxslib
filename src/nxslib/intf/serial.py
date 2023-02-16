"""Module containing the NxScope serial interface implementation."""

import serial  # type: ignore

from nxslib.intf.iintf import ICommInterface
from nxslib.logger import logger

###############################################################################
# Class: SerialDevice
###############################################################################


class SerialDevice(ICommInterface):
    """A class used to represent a serial interface.

    To simulate UART with a NuttX sim target:
         socat PTY,link=/dev/ttySIM0 PTY,link=/dev/ttyNX0
         stty -F /dev/ttySIM0 raw
         stty -F /dev/ttyNX0 raw
         stty -F /dev/ttySIM0 115200
         stty -F /dev/ttyNX0 115200
    """

    def __init__(self, port: str, baud: int = 115200) -> None:
        """Intitialize a serial interface.

        :param port: path to the serial port device
        :param baud: baud rate
        """
        try:
            self._ser = serial.Serial(
                port, baud, timeout=1, bytesize=8, parity="N", stopbits=1
            )
        except Exception as exc:
            logger.error("Failed to open serial port: %s", str(exc))
            self._ser = None
            raise exc

        super().__init__()

    def __del__(self) -> None:
        """Make sure that serial port is closed."""
        if self._ser:
            self._ser.close()

    def start(self) -> None:
        """Start the interface."""
        logger.debug("start dummy interface")

    def stop(self) -> None:
        """Stop the interface."""
        logger.debug("Stop dummy interface")

    def drop_all(self) -> None:
        """Drop all frames."""
        for _ in range(10):
            self._read()

    def _read(self) -> bytes:
        """Interface specific read method."""
        try:
            return self._ser.read(self._ser.in_waiting)
        except serial.SerialException as e:
            logger.debug("SerialException ignored:", str(e))
            return b""

    def _write(self, data: bytes) -> None:
        """Interface specific write method.

        :param data: bytes to send
        """
        self._ser.write(data)
