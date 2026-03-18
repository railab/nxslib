import queue
import threading
import time

import numpy as np
import pytest  # type: ignore

from nxslib.comm import AckMode
from nxslib.intf.dummy import DummyDev
from nxslib.nxscope import (
    DExtCallError,
    DNxscopeStream,
    DNxscopeStreamBlock,
    NxscopeHandler,
)
from nxslib.plugin import INxscopePlugin
from nxslib.proto.iframe import DParseFrame
from nxslib.proto.iparse import ParseAck
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


def test_nxscope_plugin_lifecycle_and_user_api():
    class TestPlugin(INxscopePlugin):
        name = "test_plugin"

        def __init__(self):
            self.events = []

        def on_register(self, nxscope):
            self.events.append("register")

        def on_unregister(self):
            self.events.append("unregister")

        def on_connect(self, dev):
            del dev
            self.events.append("connect")

        def on_disconnect(self):
            self.events.append("disconnect")

        def on_user_frame(self, frame):
            self.events.append(f"user:{int(frame.fid)}")
            return True

    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    plugin = TestPlugin()

    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    nxscope.register_plugin(plugin, frame_ids=[8])
    assert "register" in plugin.events

    nxscope.connect()
    assert "connect" in plugin.events
    assert (
        nxscope._comm._dispatch_user_frame(DParseFrame(fid=8, data=b"\x01"))
        is True
    )
    assert "user:8" in plugin.events

    calls = []

    def fake_send(
        fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
    ):  # pragma: no cover
        calls.append((fid, payload, ack_mode, ack_timeout))
        return None

    nxscope._comm.send_user_frame = fake_send  # type: ignore[attr-defined]
    nxscope.send_user_frame(8, b"\x11\x22", ack_mode=AckMode.DISABLED)
    assert calls == [(8, b"\x11\x22", AckMode.DISABLED, 1.0)]
    nxscope.send_user_frame(8, b"\x33\x44", ack_mode=AckMode.ENABLED)
    assert calls[-1] == (8, b"\x33\x44", AckMode.ENABLED, 1.0)

    nxscope.disconnect()
    assert "disconnect" in plugin.events

    assert nxscope.unregister_plugin("test_plugin") is True
    assert "unregister" in plugin.events
    assert nxscope.unregister_plugin("test_plugin") is False


def test_nxscope_plugin_default_interface():
    plugin = INxscopePlugin()
    assert plugin.on_register(None) is None  # type: ignore[arg-type]
    assert plugin.on_unregister() is None
    assert plugin.on_connect(None) is None  # type: ignore[arg-type]
    assert plugin.on_disconnect() is None
    assert plugin.on_user_frame(DParseFrame(fid=8, data=b"\x00")) is False


def test_nxscope_ext_channel_publish_legacy():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()

    with NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    ) as nxscope:
        nxscope.ext_channel_add(200)
        q = nxscope.stream_sub(200)

        nxscope.ext_publish_legacy(200, DNxscopeStream((1, 2), (3,)))
        data = q.get(block=True, timeout=0.1)
        assert len(data) == 1
        assert isinstance(data[0], DNxscopeStream)
        assert data[0].data == (1, 2)

        nxscope.stream_unsub(q)


def test_nxscope_ext_channel_publish_numpy():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()

    with NxscopeHandler(
        intf,
        parse,
        stream_decode_mode="numpy",
        drop_timeout=0.01,
        stream_data_timeout=0.05,
    ) as nxscope:
        nxscope.ext_channel_add(201)
        q = nxscope.stream_sub(201)

        block = DNxscopeStreamBlock(
            data=np.array([1, 2, 3], dtype=np.int32),
            meta=None,
        )
        nxscope.ext_publish_numpy(201, block)
        data = q.get(block=True, timeout=0.1)
        assert len(data) == 1
        assert isinstance(data[0], DNxscopeStreamBlock)
        assert int(data[0].data[1]) == 2

        nxscope.stream_unsub(q)


def test_nxscope_plugin_register_duplicate_and_rollback():
    class DuplicatePlugin(INxscopePlugin):
        name = "dup"

    class FailingPlugin(INxscopePlugin):
        name = "fail"

        def __init__(self):
            self.events = []

        def on_register(self, nxscope):
            del nxscope
            self.events.append("register")
            raise RuntimeError("boom")

        def on_unregister(self):
            self.events.append("unregister")

    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    nxscope.register_plugin(DuplicatePlugin())
    with pytest.raises(ValueError):
        nxscope.register_plugin(DuplicatePlugin())
    assert nxscope.unregister_plugin("dup") is True

    failing = FailingPlugin()
    with pytest.raises(RuntimeError):
        nxscope.register_plugin(failing)
    assert failing.events == ["register", "unregister"]
    assert nxscope.unregister_plugin("fail") is False


def test_nxscope_plugin_noncallable_hooks_and_connected_unregister():
    class BarePlugin:
        name = "bare"
        on_register = None
        on_unregister = None
        on_connect = None
        on_disconnect = None
        on_user_frame = None

    class DisconnectPlugin(INxscopePlugin):
        name = "disc"

        def __init__(self):
            self.events = []

        def on_disconnect(self):
            self.events.append("disconnect")

    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    nxscope.connect()
    nxscope.register_plugin(BarePlugin())  # type: ignore[arg-type]
    assert nxscope.unregister_plugin("bare") is True
    nxscope.disconnect()

    nxscope.connect()
    disc = DisconnectPlugin()
    nxscope.register_plugin(disc)
    assert nxscope.unregister_plugin("disc") is True
    assert disc.events == ["disconnect"]
    nxscope.disconnect()


def test_nxscope_connect_disconnect_noncallable_plugin_hooks():
    class BarePlugin:
        name = "bare_connect"
        on_register = None
        on_unregister = None
        on_connect = None
        on_disconnect = None
        on_user_frame = None

    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    nxscope.register_plugin(BarePlugin())  # type: ignore[arg-type]
    nxscope.connect()
    nxscope.disconnect()
    assert nxscope.unregister_plugin("bare_connect") is True


def test_nxscope_ext_request_response_roundtrip():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    with nxscope:
        captured = []
        orig_send = nxscope._comm.send_user_frame

        def fake_send(
            fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
        ):
            captured.append((fid, payload, ack_mode, ack_timeout))
            req = nxscope._ext_decode(fid, payload)
            assert req is not None
            assert req.flags & 0x01
            resp_payload = nxscope._ext_encode(
                ext_id=req.ext_id,
                cmd_id=req.cmd_id,
                flags=0x02,
                req_id=req.req_id,
                status=0,
                payload=b"pong",
            )
            nxscope._ext_dispatch_frame(
                DParseFrame(fid=fid, data=resp_payload)
            )
            return ParseAck(True, 0)

        nxscope._comm.send_user_frame = fake_send
        try:
            resp = nxscope.ext_request(
                ext_id=3,
                cmd_id=7,
                payload=b"ping",
                ack_mode=AckMode.DISABLED,
                timeout=0.2,
            )
        finally:
            nxscope._comm.send_user_frame = orig_send

        assert captured
        assert resp.ext_id == 3
        assert resp.cmd_id == 7
        assert resp.payload == b"pong"
        assert resp.is_error is False


def test_nxscope_ext_request_timeout():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    with nxscope:
        orig_send = nxscope._comm.send_user_frame

        def fake_send_user_frame(
            fid,
            payload,
            ack_mode=AckMode.DISABLED,
            ack_timeout=1.0,
        ):
            del fid, payload, ack_mode, ack_timeout
            return ParseAck(True, 0)

        nxscope._comm.send_user_frame = fake_send_user_frame
        try:
            with pytest.raises(TimeoutError):
                nxscope.ext_request(
                    ext_id=9,
                    cmd_id=1,
                    payload=b"\x00",
                    ack_mode=AckMode.DISABLED,
                    timeout=0.01,
                )
        finally:
            nxscope._comm.send_user_frame = orig_send


def test_nxscope_ext_call_returns_payload():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    with nxscope:
        orig_send = nxscope._comm.send_user_frame

        def fake_send(
            fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
        ):
            req = nxscope._ext_decode(fid, payload)
            assert req is not None
            assert req.flags & 0x01
            resp_payload = nxscope._ext_encode(
                ext_id=req.ext_id,
                cmd_id=req.cmd_id,
                flags=0x02,
                req_id=req.req_id,
                status=0,
                payload=b"ok-data",
            )
            nxscope._ext_dispatch_frame(
                DParseFrame(fid=fid, data=resp_payload)
            )
            return ParseAck(True, 0)

        nxscope._comm.send_user_frame = fake_send
        try:
            ret = nxscope.ext_call(
                ext_id=4,
                cmd_id=1,
                payload=b"a",
                ack_mode=AckMode.DISABLED,
                timeout=0.2,
            )
        finally:
            nxscope._comm.send_user_frame = orig_send

        assert ret == b"ok-data"


def test_nxscope_ext_call_decode():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    with nxscope:
        orig_send = nxscope._comm.send_user_frame

        def fake_send(
            fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
        ):
            req = nxscope._ext_decode(fid, payload)
            assert req is not None
            assert req.flags & 0x01
            resp_payload = nxscope._ext_encode(
                ext_id=req.ext_id,
                cmd_id=req.cmd_id,
                flags=0x02,
                req_id=req.req_id,
                status=0,
                payload=b"\x2a\x00",
            )
            nxscope._ext_dispatch_frame(
                DParseFrame(fid=fid, data=resp_payload)
            )
            return ParseAck(True, 0)

        nxscope._comm.send_user_frame = fake_send
        try:
            ret = nxscope.ext_call_decode(
                ext_id=4,
                cmd_id=2,
                payload=b"a",
                decode=lambda data: int.from_bytes(data, "little"),
                ack_mode=AckMode.DISABLED,
                timeout=0.2,
            )
        finally:
            nxscope._comm.send_user_frame = orig_send

        assert ret == 42


def test_nxscope_ext_call_raises_on_error_status():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    with nxscope:
        orig_send = nxscope._comm.send_user_frame

        def fake_send(
            fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
        ):
            req = nxscope._ext_decode(fid, payload)
            assert req is not None
            assert req.flags & 0x01
            resp_payload = nxscope._ext_encode(
                ext_id=req.ext_id,
                cmd_id=req.cmd_id,
                flags=0x04,
                req_id=req.req_id,
                status=7,
                payload=b"bad",
            )
            nxscope._ext_dispatch_frame(
                DParseFrame(fid=fid, data=resp_payload)
            )
            return ParseAck(True, 0)

        nxscope._comm.send_user_frame = fake_send
        try:
            with pytest.raises(DExtCallError) as exc:
                nxscope.ext_call(
                    ext_id=4,
                    cmd_id=3,
                    payload=b"a",
                    ack_mode=AckMode.DISABLED,
                    timeout=0.2,
                )
        finally:
            nxscope._comm.send_user_frame = orig_send

        assert exc.value.response.status == 7
        assert exc.value.response.payload == b"bad"
        assert exc.value.response.is_error is True


def test_nxscope_ext_bind_handles_request_and_notify():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    with nxscope:
        got = []
        sent = []
        orig_send = nxscope._comm.send_user_frame

        def fake_send(
            fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
        ):
            sent.append((fid, payload, ack_mode, ack_timeout))
            return ParseAck(True, 0)

        nxscope._comm.send_user_frame = fake_send  # type: ignore[attr-defined]
        try:

            def handler(req):
                got.append((req.ext_id, req.cmd_id, req.payload, req.flags))
                return (5, b"bad")

            nxscope.ext_bind(11, handler)

            req_payload = nxscope._ext_encode(
                ext_id=11,
                cmd_id=2,
                flags=0x01,
                req_id=42,
                status=0,
                payload=b"abc",
            )
            handled = nxscope._ext_dispatch_frame(
                DParseFrame(fid=8, data=req_payload)
            )
            assert handled is True
            assert got == [(11, 2, b"abc", 0x01)]
            assert len(sent) == 1
            decoded = nxscope._ext_decode(sent[0][0], sent[0][1])
            assert decoded is not None
            assert decoded.flags == 0x04
            assert decoded.req_id == 42
            assert decoded.status == 5
            assert decoded.payload == b"bad"

            got.clear()
            note_payload = nxscope._ext_encode(
                ext_id=11,
                cmd_id=3,
                flags=0x08,
                req_id=0,
                status=0,
                payload=b"note",
            )
            handled = nxscope._ext_dispatch_frame(
                DParseFrame(fid=8, data=note_payload)
            )
            assert handled is True
            assert got == [(11, 3, b"note", 0x08)]
            assert len(sent) == 1
            assert nxscope.ext_unbind(11) is True
            assert nxscope.ext_unbind(11) is False
        finally:
            nxscope._comm.send_user_frame = orig_send


def test_nxscope_plugin_register_receives_control_surface():
    class ControlPlugin(INxscopePlugin):
        name = "ctl"

        def __init__(self):
            self.control = None

        def on_register(self, control):
            self.control = control

    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )
    plugin = ControlPlugin()
    nxscope.register_plugin(plugin)
    assert plugin.control is not None
    assert plugin.control is not nxscope
    assert hasattr(plugin.control, "ext_request")
    assert hasattr(plugin.control, "ext_call")
    assert hasattr(plugin.control, "ext_call_decode")
    assert nxscope.unregister_plugin("ctl") is True


def test_nxscope_plugin_control_forwards_all_extension_methods():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )
    control = nxscope._control
    calls = []

    nxscope.send_user_frame = lambda **kw: calls.append(
        ("send_user_frame", kw)
    ) or ParseAck(True, 0)
    nxscope.add_user_frame_listener = (
        lambda cb, fids=None: calls.append(
            ("add_user_frame_listener", cb, fids)
        )
        or 11
    )
    nxscope.remove_user_frame_listener = (
        lambda lid: calls.append(("remove_user_frame_listener", lid)) or True
    )
    nxscope.ext_channel_add = lambda chan: calls.append(
        ("ext_channel_add", chan)
    )
    nxscope.ext_publish_numpy = lambda chan, data: calls.append(
        ("ext_publish_numpy", chan, data)
    )
    nxscope.ext_publish_legacy = lambda chan, data: calls.append(
        ("ext_publish_legacy", chan, data)
    )
    nxscope.ext_bind = lambda ext_id, h: calls.append(("ext_bind", ext_id, h))
    nxscope.ext_unbind = (
        lambda ext_id: calls.append(("ext_unbind", ext_id)) or True
    )
    nxscope.ext_notify = lambda **kw: calls.append(
        ("ext_notify", kw)
    ) or ParseAck(True, 0)
    nxscope.ext_request = lambda **kw: calls.append(
        ("ext_request", kw)
    ) or nxscope._ext_decode(8, nxscope._ext_encode(1, 2, 0x02, 1, 0, b""))
    nxscope.ext_call = lambda **kw: calls.append(("ext_call", kw)) or b"ok"
    nxscope.ext_call_decode = (
        lambda **kw: calls.append(("ext_call_decode", kw)) or 42
    )

    assert control.send_user_frame(8, b"x").state is True
    assert control.add_user_frame_listener(lambda _: False, [8]) == 11
    assert control.remove_user_frame_listener(11) is True
    control.ext_channel_add(101)
    control.ext_publish_numpy(101, [])
    control.ext_publish_legacy(101, [])
    control.ext_bind(2, lambda _: None)
    assert control.ext_unbind(2) is True
    assert control.ext_notify(2, 1, b"x").state is True
    assert control.ext_request(2, 1, b"x") is not None
    assert control.ext_call(2, 1, b"x") == b"ok"
    assert control.ext_call_decode(2, 1, b"x", decode=lambda data: data) == 42

    names = [entry[0] for entry in calls]
    assert "send_user_frame" in names
    assert "add_user_frame_listener" in names
    assert "remove_user_frame_listener" in names
    assert "ext_channel_add" in names
    assert "ext_publish_numpy" in names
    assert "ext_publish_legacy" in names
    assert "ext_bind" in names
    assert "ext_unbind" in names
    assert "ext_notify" in names
    assert "ext_request" in names
    assert "ext_call" in names
    assert "ext_call_decode" in names


def test_nxscope_extension_validation_and_edge_paths():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    with pytest.raises(ValueError):
        nxscope._ext_encode(-1, 1, 0, 1, 0, b"x")
    with pytest.raises(ValueError):
        nxscope._ext_encode(1, 256, 0, 1, 0, b"x")
    with pytest.raises(ValueError):
        nxscope._ext_encode(1, 1, 0, -1, 0, b"x")
    with pytest.raises(ValueError):
        nxscope._ext_encode(1, 1, 0, 1, 256, b"x")
    with pytest.raises(TypeError):
        nxscope._ext_encode(1, 1, 0, 1, 0, "x")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        nxscope.ext_bind(-1, lambda _: None)
    with pytest.raises(TypeError):
        nxscope.ext_bind(1, 123)  # type: ignore[arg-type]

    bad_magic = b"\x00" + nxscope._ext_encode(1, 1, 0, 1, 0, b"x")[1:]
    assert nxscope._ext_decode(8, bad_magic) is None

    nxscope._ext_req_id = 0xFFFF
    req = nxscope._ext_alloc_req_id()
    assert req == 0xFFFF

    nxscope._ext_req_id = 1
    nxscope._ext_pending = {
        i: queue.Queue(maxsize=1) for i in range(1, 0x10000)
    }
    with pytest.raises(RuntimeError):
        nxscope._ext_alloc_req_id()

    nxscope.ext_channel_add(300)
    nxscope.ext_channel_add(300)
    q300 = nxscope.stream_sub(300)
    nxscope.ext_publish_numpy(300, [DNxscopeStreamBlock(np.array([1]), None)])
    assert q300.get(timeout=0.1)[0].data[0] == 1

    nxscope.ext_channel_add(301)
    q301 = nxscope.stream_sub(301)
    nxscope.ext_publish_legacy(301, [DNxscopeStream((1,), (0,))])
    assert q301.get(timeout=0.1)[0].data == (1,)

    q999 = nxscope.stream_sub(999)
    nxscope.ext_publish_numpy(1000, [DNxscopeStreamBlock(np.array([2]), None)])
    nxscope.ext_publish_legacy(1001, [DNxscopeStream((2,), (0,))])
    nxscope.stream_unsub(q999)
    nxscope.stream_unsub(queue.Queue())

    with pytest.raises(ValueError):
        nxscope.ext_channel_add(-1)


def test_nxscope_extension_dispatch_misc_branches():
    intf = DummyDev(thread_timeout=0.05)
    parse = Parser()
    nxscope = NxscopeHandler(
        intf, parse, drop_timeout=0.01, stream_data_timeout=0.05
    )

    with nxscope:
        sent = []
        orig_send = nxscope._comm.send_user_frame

        def fake_send(
            fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
        ):
            sent.append((fid, payload, ack_mode, ack_timeout))
            return ParseAck(True, 0)

        nxscope._comm.send_user_frame = fake_send
        try:
            assert nxscope.ext_notify(
                5, 1, b"x", ack_mode=AckMode.DISABLED
            ).state
            req = nxscope._ext_decode(sent[-1][0], sent[-1][1])
            assert req is not None
            assert req.flags == 0x08

            def fail_ack(
                fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
            ):
                del fid, payload, ack_mode, ack_timeout
                return ParseAck(False, -5)

            nxscope._comm.send_user_frame = fail_ack
            with pytest.raises(RuntimeError):
                nxscope.ext_request(
                    ext_id=5,
                    cmd_id=1,
                    payload=b"x",
                    ack_mode=AckMode.ENABLED,
                )
        finally:
            nxscope._comm.send_user_frame = orig_send

        resp_no_pending = nxscope._ext_encode(5, 1, 0x02, 1234, 0, b"ok")
        assert (
            nxscope._ext_dispatch_frame(
                DParseFrame(fid=8, data=resp_no_pending)
            )
            is False
        )

        req_no_handler = nxscope._ext_encode(6, 1, 0x01, 11, 0, b"x")
        assert (
            nxscope._ext_dispatch_frame(
                DParseFrame(fid=8, data=req_no_handler)
            )
            is False
        )

        nxscope.ext_bind(7, lambda _: None)
        req_none = nxscope._ext_encode(7, 1, 0x01, 12, 0, b"x")
        assert nxscope._ext_dispatch_frame(DParseFrame(fid=8, data=req_none))
        nxscope.ext_unbind(7)

        sent2 = []

        def collect_send(
            fid, payload, ack_mode=AckMode.DISABLED, ack_timeout=1.0
        ):
            sent2.append((fid, payload, ack_mode, ack_timeout))
            return ParseAck(True, 0)

        nxscope._comm.send_user_frame = collect_send
        try:
            nxscope.ext_bind(8, lambda _: b"done")
            req_bytes = nxscope._ext_encode(8, 1, 0x01, 13, 0, b"x")
            assert nxscope._ext_dispatch_frame(
                DParseFrame(fid=8, data=req_bytes)
            )
            out = nxscope._ext_decode(sent2[-1][0], sent2[-1][1])
            assert out is not None
            assert out.payload == b"done"
            assert out.status == 0

            nxscope.ext_unbind(8)
            nxscope.ext_bind(9, lambda _: 123)
            req_bad = nxscope._ext_encode(9, 1, 0x01, 14, 0, b"x")
            with pytest.raises(TypeError):
                nxscope._ext_dispatch_frame(DParseFrame(fid=8, data=req_bad))
        finally:
            nxscope._comm.send_user_frame = orig_send
