import pytest  # type: ignore

from nxslib.proto.iparserecv import ICommParseRecv


def test_inxslibparserecv_init():
    # abstract class
    with pytest.raises(TypeError):
        _ = ICommParseRecv()
