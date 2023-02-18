import pytest  # type: ignore

from nxslib.dev import EDeviceChannelType
from nxslib.proto.iparse import (
    DsfmtItem,
    EParseDataType,
    ICommParse,
    dsfmt_get,
)


def test_inxslibparse_init():
    # abstract class
    with pytest.raises(TypeError):
        _ = ICommParse()


def test_dsfmt_get():
    for i in range(
        EDeviceChannelType.NONE.value, EDeviceChannelType.USER1.value
    ):
        print("i=", i)
        x = dsfmt_get(i)
        assert x is not None
        assert isinstance(x.slen, int)
        assert isinstance(x.dsfmt, str)
        assert isinstance(x.scale, (int, float, type(None)))
        assert isinstance(x.dtype, EParseDataType)
        # cdecode not supported for basic types
        assert x.cdecode is None
        assert x.user is False

    # not user defined type
    with pytest.raises(KeyError):
        x = dsfmt_get(EDeviceChannelType.USER1.value)

    # not supported channel type
    with pytest.raises(KeyError):
        x = dsfmt_get(EDeviceChannelType.USER12.value + 1)


def test_user_get():
    user = {
        EDeviceChannelType.USER1.value: DsfmtItem(
            1, "ib", None, EParseDataType.NUM, None, True
        ),
        EDeviceChannelType.USER3.value: DsfmtItem(
            1, "ii", None, EParseDataType.NUM, None, True
        ),
        EDeviceChannelType.USER5.value: DsfmtItem(
            1,
            "ccii",
            None,
            EParseDataType.COMPLEX,
            (
                EParseDataType.CHAR,
                EParseDataType.CHAR,
                EParseDataType.NUM,
                EParseDataType.NUM,
            ),
            True,
        ),
        EDeviceChannelType.USER6.value: DsfmtItem(
            4, "ii", None, EParseDataType.NUM, None, True
        ),
        EDeviceChannelType.USER7.value: DsfmtItem(
            1, "ii", None, EParseDataType.NUM, None, False
        ),
    }

    # not defined type
    with pytest.raises(KeyError):
        _ = dsfmt_get(EDeviceChannelType.USER10.value, user)

    # invalid user data - slen must be 1 for user types
    with pytest.raises(AssertionError):
        _ = dsfmt_get(EDeviceChannelType.USER6.value, user)

    # invalid user data - user flag must be set
    with pytest.raises(AssertionError):
        _ = dsfmt_get(EDeviceChannelType.USER7.value, user)

    # user defined types
    d1 = dsfmt_get(EDeviceChannelType.USER1.value, user)
    assert d1 is not None
    assert d1.slen == 1
    assert d1.dsfmt == "ib"
    assert d1.user is True
    d3 = dsfmt_get(EDeviceChannelType.USER3.value, user)
    assert d3 is not None
    assert d3.slen == 1
    assert d3.dsfmt == "ii"
    assert d3.user is True
    d5 = dsfmt_get(EDeviceChannelType.USER5.value, user)
    assert d5 is not None
    assert d5.slen == 1
    assert d5.dsfmt == "ccii"
    assert d5.cdecode == (
        EParseDataType.CHAR,
        EParseDataType.CHAR,
        EParseDataType.NUM,
        EParseDataType.NUM,
    )
    assert d5.user is True
