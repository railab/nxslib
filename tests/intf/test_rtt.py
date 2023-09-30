import pytest  # type: ignore

from nxslib.intf.rtt import RTTDevice


def test_nxslibserial_init():
    with pytest.raises(ValueError):
        _ = RTTDevice("test", 1, 100, "x")
