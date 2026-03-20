import pytest  # type: ignore
import serial.serialutil  # type: ignore

from nxslib.intf.serial import SerialDevice


def test_nxslibserial_init():
    with pytest.raises(serial.serialutil.SerialException):
        _ = SerialDevice("/dev/ttyUSB00")


def test_nxslibserial_read_ignores_invalid_fd(monkeypatch):  # type: ignore
    device = SerialDevice.__new__(SerialDevice)

    class _BrokenSerial:
        is_open = True

        @property
        def in_waiting(self):
            raise TypeError(
                "argument must be an int, or have a fileno() method"
            )

    device._ser = _BrokenSerial()

    assert device._read() == b""


def test_nxslibserial_read_returns_empty_when_port_closed():
    device = SerialDevice.__new__(SerialDevice)

    class _ClosedSerial:
        is_open = False

        @property
        def in_waiting(self):  # pragma: no cover
            raise AssertionError("must not read closed port")

    device._ser = _ClosedSerial()

    assert device._read() == b""


def test_nxslibserial_write_skips_closed_port():
    device = SerialDevice.__new__(SerialDevice)

    class _ClosedSerial:
        is_open = False

        def write(self, data):  # noqa: ANN001  # pragma: no cover
            del data
            raise AssertionError("must not write closed port")

    device._ser = _ClosedSerial()

    device._write(b"test")


def test_nxslibserial_stop_closes_and_clears_port():
    device = SerialDevice.__new__(SerialDevice)

    class _Serial:
        is_open = True

        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    ser = _Serial()
    device._ser = ser

    device.stop()

    assert ser.closed is True
    assert device._ser is None
