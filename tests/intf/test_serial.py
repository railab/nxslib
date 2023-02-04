import pytest  # type: ignore
import serial.serialutil  # type: ignore

from nxslib.intf.serial import SerialDevice


def test_nxslibserial_init():
    with pytest.raises(serial.serialutil.SerialException):
        _ = SerialDevice("/dev/ttyUSB00")
