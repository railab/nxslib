import pytest  # type: ignore

from nxslib.dev import EDeviceChannelType
from nxslib.proto.iparse import EParseDataType, ICommParse, dsfmt_get


def test_inxslibparse_init():
    # abstract class
    with pytest.raises(TypeError):
        _ = ICommParse()


def test_dsfmt_get():
    for i in range(
        EDeviceChannelType.NONE.value, EDeviceChannelType.USER.value
    ):
        print("i=", i)
        x = dsfmt_get(i)
        assert isinstance(x, tuple)
        assert isinstance(x[0], int)
        assert isinstance(x[1], str)
        assert isinstance(x[2], (int, float, type(None)))
        assert isinstance(x[3], EParseDataType)

    # not supported channel type
    with pytest.raises(KeyError):
        x = dsfmt_get(EDeviceChannelType.LAST.value + 1)
