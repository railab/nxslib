import queue
import threading
import time

import pytest  # type: ignore

from nxslib.intf.dummy import DummyDev
from nxslib.nxscope import DNxscopeStream, NxscopeHandler
from nxslib.proto.parse import Parser


def test_nxscope_context_manager():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    ) as nxscope:
        assert nxscope.dev is not None


def test_nxscope_invalid_stream_mode():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with pytest.raises(ValueError):
        NxscopeHandler(
            intf,
            parse,
            stream_decode_mode="invalid",
            drop_timeout=0.01,
            stream_data_timeout=0.05,
        )


def test_nxscope_stream_item_repr_and_str():
    item = DNxscopeStream(data=(1, 2), meta=(3,))
    assert str(item) == "(1, 2), (3,)"
    assert repr(item) == "(1, 2), (3,)"


def test_dummy_context_manager():
    with DummyDev(thread_timeout=0.05) as intf:
        assert intf is not None


def test_nxscope_connect():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    # connect
    nxscope.connect()
    # connect once again
    nxscope.connect()

    assert nxscope.dev is not None
    for chan in range(nxscope.dev.data.chmax):
        assert nxscope.dev_channel_get(chan) is not None

    # disconnect
    nxscope.disconnect()
    # disconnect once again
    nxscope.disconnect()

    assert nxscope.dev is None
    with pytest.raises(AssertionError):
        _ = nxscope.dev_channel_get(0)


def test_nxscope_stream():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    ) as nxscope:
        # start stream
        nxscope.stream_start()
        # start stream once again
        nxscope.stream_start()

        # stop stream
        nxscope.stream_stop()
        # stop stream once again
        nxscope.stream_stop()

        # subscribe to streams
        q0_0 = nxscope.stream_sub(0)
        q0_1 = nxscope.stream_sub(0)

        # default configuration
        nxscope.channels_default_cfg()

        # start stream
        nxscope.stream_start()

        # channels disabled
        for ch in range(nxscope.dev.data.chmax):
            assert nxscope._comm.ch_is_enabled(ch) is False

        # wait for data but channels not enabled
        with pytest.raises(queue.Empty):
            _ = q0_0.get(block=True, timeout=0.05)
        with pytest.raises(queue.Empty):
            _ = q0_1.get(block=True, timeout=0.05)

        # stop stream
        nxscope.stream_stop()

        # unsub from streams
        nxscope.stream_unsub(q0_0)
        nxscope.stream_unsub(q0_1)


def test_nxscope_stream_numpy_mode():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf,
        parse,
        stream_decode_mode="numpy",
        drop_timeout=0.01,
        stream_data_timeout=0.05,
    ) as nxscope:
        q0 = nxscope.stream_sub(0)
        nxscope.channels_default_cfg()
        nxscope.ch_enable([0], writenow=True)
        nxscope.stream_start()
        payload = q0.get(block=True, timeout=0.5)
        assert payload
        block = payload[0]
        assert hasattr(block.data, "shape")
        nxscope.stream_stop()
        nxscope.stream_unsub(q0)

        # configure channels
        nxscope.channels_default_cfg()
        # enable/disable
        nxscope.ch_enable([0])
        nxscope.ch_disable([0])
        nxscope.ch_enable([0])
        # divider
        nxscope.ch_divider([0], 1)

        # subscribe to streams
        q0_0 = nxscope.stream_sub(0)
        q0_1 = nxscope.stream_sub(0)

        # start stream
        nxscope.stream_start()

        # wait for data
        data = q0_0.get(block=True, timeout=0.5)
        print(data)
        print(data[0])
        assert data
        data = q0_1.get(block=True, timeout=0.5)
        print(data)
        print(data[0])
        assert data

        # get more data
        for _ in range(5):
            assert q0_0.get(block=True, timeout=0.5)
            assert q0_1.get(block=True, timeout=0.5)

        # stop stream
        nxscope.stream_stop()

        nxscope.stream_unsub(q0_0)
        nxscope.stream_unsub(q0_1)


def test_nxscope_stream_numpy_bitrate_updates_without_enabled_channels():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf,
        parse,
        enable_bitrate_tracking=True,
        stream_decode_mode="numpy",
        drop_timeout=0.01,
        stream_data_timeout=0.05,
    ) as nxscope:
        nxscope.channels_default_cfg(writenow=True)
        nxscope.ch_enable([0], writenow=True)

        def _channel_disabled(_chan: int) -> bool:
            return False

        nxscope._comm.ch_is_enabled = _channel_disabled  # type: ignore
        nxscope.stream_start()
        time.sleep(0.2)
        nxscope.stream_stop()
        stats = nxscope.get_stream_stats()
        assert stats.bitrate > 0.0


def test_nxscope_stream_legacy_mode_is_deprecated_and_functional():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with pytest.warns(DeprecationWarning):
        nxscope = NxscopeHandler(
            intf,
            parse,
            enable_bitrate_tracking=True,
            stream_decode_mode="legacy",
            drop_timeout=0.01,
            stream_data_timeout=0.05,
        )

    with nxscope:
        q0 = nxscope.stream_sub(0)
        nxscope.channels_default_cfg(writenow=True)
        nxscope.ch_enable([0], writenow=True)
        nxscope.stream_start()

        payload = q0.get(block=True, timeout=0.5)
        assert payload
        assert isinstance(payload[0], DNxscopeStream)
        time.sleep(0.2)

        nxscope.stream_stop()
        nxscope.stream_unsub(q0)

        stats = nxscope.get_stream_stats()
        assert stats.bitrate > 0.0


def test_nxscope_channels_runtime():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    ) as nxscope:
        # force default state
        nxscope.channels_default_cfg(writenow=True)

        # get device handlers
        dev0 = nxscope.dev_channel_get(0)
        dev1 = nxscope.dev_channel_get(1)
        dev2 = nxscope.dev_channel_get(2)

        assert dev0.data.en is False
        assert dev1.data.en is False
        assert dev2.data.en is False
        assert dev0.data.div == 0
        assert dev1.data.div == 0
        assert dev2.data.div == 0

        # subscribe to streams
        q0 = nxscope.stream_sub(0)
        q1 = nxscope.stream_sub(1)
        q2 = nxscope.stream_sub(2)

        nxscope.channels_default_cfg(writenow=True)

        # start stream without channels configured
        nxscope.stream_start()

        nxscope.channels_default_cfg(writenow=True)

        assert dev0.data.en is False
        assert dev1.data.en is False
        assert dev2.data.en is False
        assert dev0.data.div == 0
        assert dev1.data.div == 0
        assert dev2.data.div == 0

        # wait for data but channels not enabled
        with pytest.raises(queue.Empty):
            _ = q0.get(block=True, timeout=0.05)
        with pytest.raises(queue.Empty):
            _ = q1.get(block=True, timeout=0.05)
        with pytest.raises(queue.Empty):
            _ = q2.get(block=True, timeout=0.05)

        # reconfig
        nxscope.ch_enable(0, writenow=True)
        nxscope.ch_divider(0, 1, writenow=True)

        assert dev0.data.en is True
        assert dev1.data.en is False
        assert dev2.data.en is False
        assert dev0.data.div == 1
        assert dev1.data.div == 0
        assert dev2.data.div == 0

        # wait for data
        data = _wait_for_data(q0, timeout=0.5)
        assert data
        with pytest.raises(queue.Empty):
            _ = q1.get(block=True, timeout=0.05)
        with pytest.raises(queue.Empty):
            _ = q2.get(block=True, timeout=0.05)

        # reconfig
        nxscope.ch_enable(1, writenow=True)
        nxscope.ch_divider(1, 5, writenow=True)

        assert dev0.data.en is True
        assert dev1.data.en is True
        assert dev2.data.en is False
        assert dev0.data.div == 1
        assert dev1.data.div == 5
        assert dev2.data.div == 0

        # wait for data
        data = _wait_for_data(q0, timeout=0.5)
        assert data
        data = _wait_for_data(q1, timeout=0.5)
        assert data
        with pytest.raises(queue.Empty):
            _ = q2.get(block=True, timeout=0.05)

        # reconfig
        nxscope.ch_disable(0, writenow=True)
        nxscope.ch_divider(0, 0, writenow=True)
        nxscope.ch_enable(1, writenow=True)
        nxscope.ch_divider(1, 10, writenow=True)

        assert dev0.data.en is False
        assert dev1.data.en is True
        assert dev2.data.en is False
        assert dev0.data.div == 0
        assert dev1.data.div == 10
        assert dev2.data.div == 0

        nxscope.ch_enable(0, writenow=True)
        nxscope.ch_divider(0, 5, writenow=True)
        nxscope.ch_enable(1, writenow=True)
        nxscope.ch_divider(1, 5, writenow=True)
        nxscope.ch_enable(2, writenow=True)
        nxscope.ch_divider(2, 5, writenow=True)

        assert dev0.data.en is True
        assert dev1.data.en is True
        assert dev2.data.en is True
        assert dev0.data.div == 5
        assert dev1.data.div == 5
        assert dev2.data.div == 5

        # get more data
        for _ in range(5):
            _ = _wait_for_data(q0, timeout=0.5)
            _ = _wait_for_data(q1, timeout=0.5)
            _ = _wait_for_data(q2, timeout=0.5)

        # configuration not written
        nxscope.ch_disable_all()

        assert dev0.data.en is True
        assert dev1.data.en is True
        assert dev2.data.en is True

        # configuration written
        nxscope.ch_disable_all(True)

        assert dev0.data.en is False
        assert dev1.data.en is False
        assert dev2.data.en is False

        # stop stream
        nxscope.stream_stop()

        nxscope.stream_unsub(q0)
        nxscope.stream_unsub(q1)
        nxscope.stream_unsub(q2)


stream_started = threading.Event()
stream_stop = threading.Event()


def _wait_for_data(q, timeout: float = 3.0, step: float = 0.2):
    """Retry queue.get to reduce CI timing flakiness."""
    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise queue.Empty
        chunk = step if remaining > step else remaining
        try:
            return q.get(block=True, timeout=chunk)
        except queue.Empty:
            continue


def thread1(nxscope, inst):
    # wait for stream started
    stream_started.wait()

    # get device handlers
    dev0 = nxscope.dev_channel_get(0)
    dev1 = nxscope.dev_channel_get(1)
    dev2 = nxscope.dev_channel_get(2)

    # make sure that channels enabled
    nxscope.ch_enable(0)
    nxscope.ch_enable(1)
    nxscope.ch_enable(2)
    nxscope.channels_write()

    assert dev0.data.en is True
    assert dev1.data.en is True
    assert dev2.data.en is True

    # subscribe to streams
    q0 = nxscope.stream_sub(0)
    q1 = nxscope.stream_sub(1)
    q2 = nxscope.stream_sub(2)

    # wait for stop request
    while not stream_stop.is_set():
        try:
            _ = q0.get(block=True, timeout=0.5)
            _ = q1.get(block=True, timeout=0.5)
            _ = q2.get(block=True, timeout=0.5)
        except queue.Empty:
            # CI can briefly starve producers; keep polling until stop.
            continue

    nxscope.stream_unsub(q0)
    nxscope.stream_unsub(q1)
    nxscope.stream_unsub(q2)


def test_nxscope_channels_thread():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    ) as nxscope:
        thr1 = threading.Thread(target=thread1, args=[nxscope, 1])
        thr1.start()
        thr2 = threading.Thread(target=thread1, args=[nxscope, 2])
        thr2.start()
        thr3 = threading.Thread(target=thread1, args=[nxscope, 3])
        thr3.start()

        # force default state
        nxscope.channels_default_cfg(writenow=True)

        # get device handlers
        dev0 = nxscope.dev_channel_get(0)
        dev1 = nxscope.dev_channel_get(1)
        dev2 = nxscope.dev_channel_get(2)

        assert dev0.data.en is False
        assert dev1.data.en is False
        assert dev2.data.en is False
        assert dev0.data.div == 0
        assert dev1.data.div == 0
        assert dev2.data.div == 0

        # subscribe to streams
        q0 = nxscope.stream_sub(0)
        q1 = nxscope.stream_sub(1)
        q2 = nxscope.stream_sub(2)

        nxscope.channels_default_cfg(writenow=True)

        # configure channels
        nxscope.ch_enable(0)
        nxscope.ch_enable(1)
        nxscope.ch_enable(2)
        nxscope.ch_divider(1, 1)
        nxscope.ch_divider(2, 2)
        nxscope.ch_divider(3, 3)
        nxscope.channels_write()

        assert dev0.data.en is True
        assert dev1.data.en is True
        assert dev2.data.en is True

        # start stream
        nxscope.stream_start()
        stream_started.set()

        # get more data
        for _ in range(5):
            _ = _wait_for_data(q0, timeout=0.5)
            _ = _wait_for_data(q1, timeout=0.5)
            _ = _wait_for_data(q2, timeout=0.5)

        # stop threads
        stream_stop.set()

        # stop stream
        nxscope.stream_stop()

        nxscope.stream_unsub(q0)
        nxscope.stream_unsub(q1)
        nxscope.stream_unsub(q2)

        # wait for threads
        thr1.join()
        thr2.join()
        thr3.join()

        stream_started.clear()
        stream_stop.clear()


def test_nxscope_properties():
    """Test new properties added to NxscopeHandler."""
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    # Test connected property before connect
    assert nxscope.connected is False

    with nxscope:
        assert nxscope.connected is True

        # Test stream_started property
        assert nxscope.stream_started is False
        nxscope.stream_start()
        assert nxscope.stream_started is True
        nxscope.stream_stop()
        assert nxscope.stream_started is False

        # Test overflow_count property
        overflow_count = nxscope.overflow_count
        assert isinstance(overflow_count, int)
        assert overflow_count >= 0

    assert nxscope.connected is False


def test_nxscope_channels_state_interfaces():
    """Test channels state access interfaces."""
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    ) as nxscope:
        nxscope.channels_default_cfg(writenow=True)

        # applied and buffered states are equal after writenow
        assert nxscope.get_enabled_channels() == ()
        assert nxscope.get_channel_divider(0) == 0
        assert nxscope.get_channel_dividers()[0] == 0

        applied = nxscope.get_channels_state(applied=True)
        buffered = nxscope.get_channels_state(applied=False)
        assert applied == buffered

        # configure buffered state without writing
        nxscope.ch_enable(0)
        nxscope.ch_divider(0, 7)

        applied2 = nxscope.get_channels_state(applied=True)
        buffered2 = nxscope.get_channels_state(applied=False)
        assert 0 not in applied2.enabled_channels
        assert 0 in buffered2.enabled_channels
        assert applied2.dividers[0] == 0
        assert buffered2.dividers[0] == 7

        nxscope.channels_write()

        # now applied should match buffered configuration
        applied3 = nxscope.get_channels_state(applied=True)
        assert 0 in applied3.enabled_channels
        assert applied3.dividers[0] == 7


def test_nxscope_capabilities_and_stats_interfaces():
    """Test capabilities and stream stats interfaces."""
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf,
        parse,
        enable_bitrate_tracking=True,
        drop_timeout=0.01,
        stream_data_timeout=0.05,
    ) as nxscope:
        caps = nxscope.get_device_capabilities()
        assert caps.chmax > 0
        assert isinstance(caps.div_supported, bool)
        assert isinstance(caps.ack_supported, bool)

        stats = nxscope.get_stream_stats()
        assert stats.connected is True
        assert stats.stream_started is False
        assert stats.overflow_count == 0
        assert stats.bitrate == 0.0


def test_nxscope_bitrate():
    """Test get_bitrate method."""
    import time

    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf,
        parse,
        enable_bitrate_tracking=True,
        drop_timeout=0.01,
        stream_data_timeout=0.05,
    ) as nxscope:
        # Before stream starts, bitrate should be 0
        bitrate = nxscope.get_bitrate()
        assert bitrate == 0.0

        # Enable a channel and start stream
        nxscope.ch_enable([0])
        q = nxscope.stream_sub(0)
        nxscope.stream_start()

        # Wait for some data
        for _ in range(10):
            q.get(block=True, timeout=1)

        # Small delay to ensure bitrate tracker has data
        time.sleep(0.2)

        # Now bitrate should be > 0
        bitrate = nxscope.get_bitrate()
        assert bitrate > 0

        # stop stream
        nxscope.stream_stop()
        nxscope.stream_unsub(q)


def test_bitrate_tracker():
    from unittest.mock import patch

    from nxslib.nxscope import _BitrateTracker

    t = [0.0]

    def fake_time():
        return t[0]

    with patch("nxslib.nxscope.time", side_effect=fake_time):
        tracker = _BitrateTracker(window_seconds=1.0)
        assert tracker.get_bitrate() == 0.0

        tracker.update(1000)
        t[0] = 0.15
        tracker.update(1000)
        t[0] = 0.20
        bitrate = tracker.get_bitrate()
        assert bitrate > 0

        # Test with very short time span (< 100ms)
        tracker2 = _BitrateTracker(window_seconds=1.0)
        tracker2.update(1000)
        tracker2.update(1000)  # same t[0] = 0.20
        bitrate = tracker2.get_bitrate()
        assert bitrate == 0.0  # Too short time span

        # Test window cleanup
        tracker3 = _BitrateTracker(window_seconds=0.5)
        t[0] = 0.0
        tracker3.update(1000)
        t[0] = 0.2
        tracker3.update(1000)

        # Should have bitrate from two samples
        bitrate = tracker3.get_bitrate()
        assert bitrate > 0

        # After window expires, old sample is cleaned on next update
        t[0] = 0.6  # Total 0.6s from first sample (window=0.5s)
        tracker3.update(1000)  # This triggers cleanup

        # Bitrate calculation still works after cleanup
        bitrate = tracker3.get_bitrate()
        assert isinstance(bitrate, float)


def test_nxscope_bitrate_disabled():
    """Test that bitrate tracking is disabled by default."""
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    with NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    ) as nxscope:
        # Bitrate should always be 0 when tracking is disabled
        bitrate = nxscope.get_bitrate()
        assert bitrate == 0.0

        # Even with streaming
        nxscope.ch_enable([0])
        q = nxscope.stream_sub(0)
        nxscope.stream_start()

        # Wait for some data
        for _ in range(10):
            q.get(block=True, timeout=1)

        # Bitrate should still be 0 (tracking disabled)
        bitrate = nxscope.get_bitrate()
        assert bitrate == 0.0

        # stop stream
        nxscope.stream_stop()
        nxscope.stream_unsub(q)


def test_wait_for_data_retries_once():
    class OneEmptyThenData:
        def __init__(self):
            self.calls = 0

        def get(self, block=True, timeout=0.0):
            del block
            del timeout
            self.calls += 1
            if self.calls == 1:
                raise queue.Empty
            return [1]

    q = OneEmptyThenData()
    ret = _wait_for_data(q, timeout=0.2, step=0.05)
    assert ret == [1]
    assert q.calls == 2


def test_wait_for_data_timeout():
    class AlwaysEmpty:
        def get(self, block=True, timeout=0.0):
            del block
            del timeout
            raise queue.Empty

    with pytest.raises(queue.Empty):
        _wait_for_data(AlwaysEmpty(), timeout=0.05, step=0.01)


def test_thread1_handles_transient_empty():
    class DevData:
        def __init__(self):
            self.en = True

    class Dev:
        def __init__(self):
            self.data = DevData()

    class EmptyThenStopQueue:
        def get(self, block=True, timeout=0.0):
            del block
            del timeout
            stream_stop.set()
            raise queue.Empty

    class FakeNxscope:
        def __init__(self):
            self.dev = {0: Dev(), 1: Dev(), 2: Dev()}
            self.unsub = 0

        def dev_channel_get(self, chid):
            return self.dev[chid]

        def ch_enable(self, ch):
            del ch

        def channels_write(self):
            return None

        def stream_sub(self, ch):
            del ch
            return EmptyThenStopQueue()

        def stream_unsub(self, q):
            del q
            self.unsub += 1

    stream_started.clear()
    stream_stop.clear()
    stream_started.set()

    nxscope = FakeNxscope()
    thread1(nxscope, 1)
    assert nxscope.unsub == 3
    stream_started.clear()
    stream_stop.clear()
