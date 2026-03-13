import socket
from unittest.mock import Mock

import pytest  # type: ignore

from nxslib.intf.udp import UdpDevice


def test_nxslibudp_init_invalid_host():
    with pytest.raises(OSError):
        _ = UdpDevice("256.0.0.1", 50000)


def test_nxslibudp_read_write():
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    srv.settimeout(1.0)

    port = srv.getsockname()[1]
    dev = UdpDevice("127.0.0.1", port, timeout=0.1)

    try:
        dev.write(b"ping")
        data, addr = srv.recvfrom(16)
        assert data == b"ping"

        srv.sendto(b"pong", addr)
        assert dev.read() == b"pong"
    finally:
        dev.stop()
        srv.close()


def test_nxslibudp_context_manager_and_start():
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    dev = UdpDevice("127.0.0.1", port, timeout=0.1)

    try:
        dev.start()

        with dev as entered:
            assert entered is dev
    finally:
        dev.stop()
        srv.close()


def test_nxslibudp_drop_all_reads_until_empty():
    dev = UdpDevice.__new__(UdpDevice)
    dev._read = Mock(side_effect=[b"", b"", b"", b""])

    dev.drop_all()

    assert dev._read.call_count == 4


def test_nxslibudp_read_timeout_returns_empty():
    dev = UdpDevice.__new__(UdpDevice)
    dev._sock = Mock()
    dev._sock.recv.side_effect = TimeoutError

    assert dev._read() == b""


def test_nxslibudp_read_oserror_returns_empty():
    dev = UdpDevice.__new__(UdpDevice)
    dev._sock = Mock()
    dev._sock.recv.side_effect = OSError("recv failed")

    assert dev._read() == b""
