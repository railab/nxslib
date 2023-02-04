import pytest  # type: ignore

from nxslib.thread import ThreadCommon


def thread():
    print("thread")


def test_thread_init():
    # invalid thread type
    with pytest.raises(TypeError):
        thr = ThreadCommon(None)

    with pytest.raises(TypeError):
        thr = ThreadCommon(1)

    # valid thread type
    thr = ThreadCommon(thread)
    assert isinstance(thr, ThreadCommon)

    # start and stop thread few times
    assert thr.thread_is_alive() is False
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_stop()
    assert thr.thread_is_alive() is False
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_stop()
    assert thr.thread_is_alive() is False
