import threading

import pytest  # type: ignore

from nxslib.thread import ThreadCommon

thread_flag = threading.Event()
init_flag = threading.Event()
final_flag = threading.Event()


# clear flags at the beginning of all tests
@pytest.fixture(autouse=True)
def init_flags():
    thread_flag.clear()
    init_flag.clear()
    final_flag.clear()


def thread():
    thread_flag.set()


def init():
    init_flag.set()


def final():
    final_flag.set()


def test_thread():
    # invalid thread type
    with pytest.raises(AssertionError):
        thr = ThreadCommon(None)

    with pytest.raises(AssertionError):
        thr = ThreadCommon(1)

    # valid thread type
    thr = ThreadCommon(thread)
    assert isinstance(thr, ThreadCommon)

    # not started
    assert thr.thread_is_alive() is False

    # flags not set
    assert thread_flag.is_set() is False
    assert init_flag.is_set() is False
    assert final_flag.is_set() is False

    # start thread
    thr.thread_start()
    assert thr.thread_is_alive() is True

    # flag should be set
    assert thread_flag.wait(0.5)

    # stop trehad
    thr.thread_stop()
    assert thr.thread_is_alive() is False

    # init and final not set
    assert init_flag.is_set() is False
    assert final_flag.is_set() is False

    # start and stop once again
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_stop()
    assert thr.thread_is_alive() is False

    # start/stop many times
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_stop()
    assert thr.thread_is_alive() is False
    thr.thread_stop()
    assert thr.thread_is_alive() is False
    thr.thread_stop()
    assert thr.thread_is_alive() is False


def test_thread_init_final():
    # invalid init type
    with pytest.raises(AssertionError):
        thr = ThreadCommon(thread, init="foo")

    # invalid final type
    with pytest.raises(AssertionError):
        thr = ThreadCommon(thread, final="foo")

    # valid thread init and final
    thr = ThreadCommon(thread, init=init, final=final)
    assert isinstance(thr, ThreadCommon)

    # not started
    assert thr.thread_is_alive() is False

    # flags not set
    assert thread_flag.is_set() is False
    assert init_flag.is_set() is False
    assert final_flag.is_set() is False

    # start thread
    thr.thread_start()
    assert thr.thread_is_alive() is True

    # flags should be set
    assert init_flag.wait(0.5)
    assert thread_flag.wait(0.5)
    assert final_flag.is_set() is False

    # stop trehad
    thr.thread_stop()
    assert thr.thread_is_alive() is False

    # final flag set
    assert final_flag.wait(0.5)

    # start and stop once again
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_stop()
    assert thr.thread_is_alive() is False

    # start/stop many times
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_start()
    assert thr.thread_is_alive() is True
    thr.thread_stop()
    assert thr.thread_is_alive() is False
    thr.thread_stop()
    assert thr.thread_is_alive() is False
    thr.thread_stop()
    assert thr.thread_is_alive() is False
