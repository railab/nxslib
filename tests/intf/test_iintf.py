import pytest  # type: ignore

from nxslib.intf.iintf import CommInterfaceCommon, ICommInterface


def test_nxslibiintf_init():
    # abstract class
    with pytest.raises(TypeError):
        _ = ICommInterface()


def test_nxslibintfcommon():
    intf = CommInterfaceCommon(None, None)

    with pytest.raises(AssertionError):
        _ = intf.read()
    with pytest.raises(AssertionError):
        intf.write(b"xx")

    intf.write_padding = 16

    with pytest.raises(AssertionError):
        data = intf.data_align("x")

    data = intf.data_align(b"x")
    assert len(data) == 16
    assert data[0] == b"x"[0]
    for i in range(1, intf.write_padding):
        assert data[i] == b"\x00"[0]

    intf.write_padding = 0
    data = intf.data_align(b"x")
    assert len(data) == 1
    assert data[0] == b"x"[0]
