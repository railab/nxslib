"""Module containing the NxScope UDP interface implementation."""

import socket

from nxslib.intf.iintf import ICommInterface
from nxslib.logger import logger


class UdpDevice(ICommInterface):
    """A class used to represent a UDP interface."""

    def __init__(
        self,
        host: str,
        port: int,
        local_port: int = 0,
        timeout: float = 1.0,
    ) -> None:
        """Intitialize a UDP interface.

        :param host: remote host address
        :param port: remote host UDP port
        :param local_port: local UDP port (0 = ephemeral)
        :param timeout: socket timeout in seconds
        """
        self._timeout = timeout
        self._sock: socket.socket | None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(timeout)

        try:
            self._sock.bind(("0.0.0.0", local_port))
            self._sock.connect((host, port))
        except OSError as exc:
            logger.error("Failed to open UDP socket: %s", str(exc))
            self._sock.close()
            raise exc

        super().__init__()

    def __enter__(self) -> "UdpDevice":
        """Start on context manager entry."""
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        """Stop on context manager exit."""
        self.stop()

    def start(self) -> None:
        """Start the interface."""
        logger.debug("start udp interface")

    def stop(self) -> None:
        """Stop the interface."""
        logger.debug("Stop udp interface")
        if self._sock is None:
            return
        if self._sock.fileno() < 0:
            self._sock = None
            return
        self._sock.close()
        self._sock = None

    def drop_all(self) -> None:
        """Drop all frames."""
        if self._sock is None:  # pragma: no cover
            return
        if self._sock.fileno() < 0:
            self._sock = None
            return

        self._sock.setblocking(False)
        try:
            while True:
                try:
                    self._sock.recv(4096)
                except BlockingIOError:
                    break
        finally:
            self._sock.settimeout(self._timeout)

    def _read(self) -> bytes:
        """Interface specific read method."""
        if self._sock is None:
            return b""
        try:
            return self._sock.recv(4096)
        except TimeoutError:
            return b""
        except OSError as exc:
            logger.debug("UDP recv failed: %s", str(exc))
            return b""

    def _write(self, data: bytes) -> None:
        """Interface specific write method.

        :param data: bytes to send
        """
        if self._sock is None:
            return
        self._sock.send(data)
