import pytest  # type: ignore

from nxslib.proto.iframe import ICommFrame


def test_nxslibiframe_init():
    # abstract class
    with pytest.raises(TypeError):
        _ = ICommFrame()
