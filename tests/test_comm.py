import pytest  # type: ignore

from nxslib.comm import CommHandler
from nxslib.dev import Device, EDeviceFlags
from nxslib.intf.dummy import DummyDev
from nxslib.proto.iframe import DParseFrame
from nxslib.proto.iparse import EParseDataType, ParseAck
from nxslib.proto.parse import Parser


def test_nxslib_init():
    i = DummyDev(thread_timeout=0.05)
    p = Parser()

    comm = CommHandler(i, p, drop_timeout=0.01, stream_data_timeout=0.05)
    assert isinstance(comm, CommHandler)


@pytest.fixture
def comm():
    i = DummyDev(thread_timeout=0.05)
    p = Parser()
    c = CommHandler(i, p, drop_timeout=0.01, stream_data_timeout=0.05)
    yield c
    c.disconnect()


def test_nxslib_connect(comm):
    # not connected - no info
    assert comm.dev is None

    comm.connect()
    assert comm.dev is not None
    assert isinstance(comm.dev, Device)

    # connect again
    comm.connect()
    assert comm.dev is not None
    assert isinstance(comm.dev, Device)

    comm.disconnect()
    assert comm.dev is None

    # disconnect again
    comm.disconnect()
    assert comm.dev is None


def test_nxslib_channels(comm):
    # not connected should raise error
    with pytest.raises(AssertionError):
        comm.channels_default_cfg()

    with comm:
        # default configuration
        comm.channels_default_cfg()
        comm.channels_write()
        for chan in range(comm.dev.data.chmax):
            assert comm.ch_is_enabled(chan) is False
            assert comm.ch_div_get(chan) == 0

        # invalid interface use
        with pytest.raises(TypeError):
            comm.ch_enable("1")
        with pytest.raises(TypeError):
            comm.ch_disable("1")
        with pytest.raises(TypeError):
            comm.ch_divider("1", 0)
        with pytest.raises(ValueError):
            comm.ch_divider(1, 1000)

        # enable all channels
        comm.ch_enable_all()
        comm.channels_write()
        for chan in range(comm.dev.data.chmax):
            assert comm.ch_is_enabled(chan) is True
            assert comm.ch_div_get(chan) == 0

        # enable all once again
        comm.ch_enable_all()
        comm.channels_write()

        # disable channel
        comm.ch_disable(0)
        comm.channels_write()
        assert comm.ch_is_enabled(0) is False
        assert comm.ch_is_enabled(1) is True
        assert comm.ch_is_enabled(2) is True
        assert comm.ch_is_enabled(3) is True

        # disable channels
        comm.ch_disable([1, 3])
        comm.channels_write()

        # once again
        comm.ch_disable([1, 3])
        comm.channels_write()

        # divider
        comm.ch_divider(1, 1)
        comm.channels_write()
        assert comm.ch_div_get(0) == 0
        assert comm.ch_div_get(1) == 1
        assert comm.ch_div_get(2) == 0
        assert comm.ch_div_get(3) == 0

        # divider
        comm.ch_divider([0, 3], 3)
        comm.channels_write()
        assert comm.ch_div_get(0) == 3
        assert comm.ch_div_get(1) == 1
        assert comm.ch_div_get(2) == 0
        assert comm.ch_div_get(3) == 3


def test_nxslib_stream_ch1(comm):
    with comm:
        # default configuration
        comm.channels_default_cfg()

        # enable channel 1
        comm.ch_enable(1)
        comm.channels_write()

        # no stream - should be no data
        assert comm.stream_data() is None

        # start stream
        comm.stream_start()

        # get data
        data = comm.stream_data()
        assert data is not None
        assert data.flags == 0

        # should mach dummy dev channel 1
        i = 1.0
        for x in data.samples:
            assert x.chan == 1
            assert x.dtype == EParseDataType.NUM
            assert x.vdim == 1
            assert x.mlen == 0
            assert isinstance(x.data, tuple)
            assert x.data == (i,)
            i += 1.0
            assert x.meta == ()

        # do not stop stream but disconnect


def test_nxslib_stream_numpy(comm):
    with comm:
        comm.channels_default_cfg()
        comm.ch_enable(1)
        comm.channels_write()

        # no stream - should be no data
        assert comm.stream_data_numpy() is None

        comm.stream_start()
        data = comm.stream_data_numpy()
        assert data is not None
        assert data.flags == 0
        assert len(data.blocks) > 0
        assert data.blocks[0].data.shape[1] == 1


def test_nxslib_stream_numpy_no_decoder(comm):
    with comm:
        comm.channels_default_cfg()
        comm.ch_enable(1)
        comm.channels_write()
        comm.stream_start()
        # simulate parser without numpy decode implementation
        comm._parse.frame_stream_decode_numpy = (  # type: ignore[attr-defined]
            None
        )
        assert comm.stream_data_numpy() is None


def test_nxslib_stream_ch1ch2(comm):
    with comm:
        # default configuration
        comm.channels_default_cfg()

        # enable channel 1 and 2
        comm.ch_enable([1, 2])
        comm.channels_write()

        # no stream - should be no data
        assert comm.stream_data() is None

        # start stream
        comm.stream_start()

        # get data
        data = comm.stream_data()
        assert data is not None
        assert data.flags == 0

        # we expect data from ch1 and ch2
        ch1_cntr = 0
        ch2_cntr = 0
        for x in data.samples:
            if x.chan == 1:
                ch1_cntr += 1
            if x.chan == 2:
                ch2_cntr += 1

        assert ch1_cntr > 0
        assert ch2_cntr > 0

        # do not stop stream but disconnect


def test_nxslib_stream_ch6(comm):
    with comm:
        # default configuration
        comm.channels_default_cfg()

        # enable channel 6
        comm.ch_enable(6)
        comm.channels_write()

        # no stream - should be no data
        assert comm.stream_data() is None

        # start stream
        comm.stream_start()

        # get data
        data = comm.stream_data()
        assert data is not None
        assert data.flags == 0

        # should mach dummy dev channel 6 - we should capture at
        # least one message
        for x in data.samples:
            assert x.chan == 6
            assert x.dtype == EParseDataType.CHAR
            assert x.vdim == 64
            assert x.mlen == 0
            assert isinstance(x.data[0], str)
            assert x.data == ("hello" + "\0" * 59,)
            assert x.meta == ()

        # stop stream
        comm.stream_stop()


def test_nxslib_stream_ch7(comm):
    with comm:
        # default configuration
        comm.channels_default_cfg()

        # enable channel 7
        comm.ch_enable(7)
        comm.channels_write()

        # no stream - should be no data
        assert comm.stream_data() is None

        # start stream
        comm.stream_start()

        # get data
        data = comm.stream_data()
        assert data is not None
        assert data.flags == 0

        # should mach dummy dev channel 7
        i = 1
        for x in data.samples:
            assert x.chan == 7
            assert x.dtype == EParseDataType.NUM
            assert x.vdim == 3
            assert x.mlen == 1
            assert isinstance(x.data, tuple)
            assert x.data == (1, 0, -1)
            assert x.meta == (i,)
            i += 1

        # stop stream
        comm.stream_stop()


def test_nxslib_stream_ch8(comm):
    with comm:
        # default configuration
        comm.channels_default_cfg()

        # enable channel 8
        comm.ch_enable(8)
        comm.channels_write()

        # no stream - should be no data
        assert comm.stream_data() is None

        # start stream
        comm.stream_start()

        # get data
        data = comm.stream_data()
        assert data is not None
        assert data.flags == 0

        # should mach dummy dev channel 8
        for x in data.samples:
            assert x.chan == 8
            assert x.dtype == EParseDataType.NONE
            assert x.vdim == 0
            assert x.mlen == 16
            assert x.data == ()
            assert x.meta == (
                104,
                101,
                108,
                108,
                111,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )  # hello

        # stop stream
        comm.stream_stop()


def test_nxslib_nodiv():
    i = DummyDev(flags=EDeviceFlags.ACK_SUPPORT.value, thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        # default configuration
        comm.channels_default_cfg()
        comm.channels_write()

        comm.ch_enable(0)
        comm.ch_divider(1, 1)
        comm.channels_write()
        assert comm.ch_is_enabled(0) is True
        assert comm.ch_div_get(0) == 0


def test_nxslib_noack():
    i = DummyDev(flags=EDeviceFlags.DIVIDER_SUPPORT.value, thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        # default configuration
        comm.channels_default_cfg()
        comm.channels_write()

        comm.ch_enable(0)
        comm.ch_divider(1, 1)
        comm.channels_write()
        assert comm.ch_is_enabled(0) is True
        assert comm.ch_div_get(0) == 0


def test_comm_get_enabled_channels():
    """Test get_enabled_channels method."""
    i = DummyDev(thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        # default configuration - no channels enabled
        comm.channels_default_cfg()
        comm.channels_write()

        enabled = comm.get_enabled_channels()
        assert enabled == ()

        # configure buffered-only state (not written yet)
        comm.ch_enable(1)
        comm.ch_divider(1, 7)
        assert comm.get_enabled_channels(applied=True) == ()
        assert 1 in comm.get_enabled_channels(applied=False)
        assert comm.ch_div_get(1, applied=True) == 0
        assert comm.ch_div_get(1, applied=False) == 7

        # enable some channels
        comm.ch_enable(0)
        comm.ch_enable(2)
        comm.ch_enable(4)
        comm.channels_write()

        enabled = comm.get_enabled_channels()
        assert 0 in enabled
        assert 1 in enabled
        assert 2 in enabled
        assert 4 in enabled
        assert 3 not in enabled
        dividers = comm.get_channel_dividers()
        assert dividers[1] == 7


def test_comm_context_manager():
    i = DummyDev(thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        assert comm.dev is not None


def test_user_listener_dispatch_and_filter():
    i = DummyDev(thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        seen = []

        def on_user(frame):
            seen.append((int(frame.fid), frame.data))
            return True

        lid = comm.add_user_frame_listener(on_user, frame_ids=[8, 9])
        assert isinstance(lid, int)

        frame_ok = DParseFrame(fid=8, data=b"\x01\x02")
        frame_ng = DParseFrame(fid=10, data=b"\x03")

        assert comm._dispatch_user_frame(frame_ok) is True
        assert comm._dispatch_user_frame(frame_ng) is False
        assert seen == [(8, b"\x01\x02")]
        assert comm.remove_user_frame_listener(lid) is True
        assert comm.remove_user_frame_listener(lid) is False


def test_send_user_frame_ack_modes():
    i = DummyDev(thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        # Avoid sending unknown user frames into dummy parser thread.
        comm._intf.write = lambda _data: None

        calls = []
        calls_required = []

        def fake_ack(timeout=1.0):
            calls.append(timeout)
            return ParseAck(True, 77)

        def fake_ack_req(timeout=1.0):
            calls_required.append(timeout)
            return ParseAck(True, 88)

        comm._get_ack = fake_ack
        comm._get_ack_required = fake_ack_req

        ack = comm.send_user_frame(8, b"\xaa", ack_mode="disabled")
        assert ack.state is True
        assert ack.retcode == 0
        assert calls == []
        assert calls_required == []

        ack = comm.send_user_frame(
            9, b"\xbb", ack_mode="auto", ack_timeout=0.2
        )
        assert ack.retcode == 77
        assert calls == [0.2]

        ack = comm.send_user_frame(
            10, b"\xcc", ack_mode="required", ack_timeout=0.3
        )
        assert ack.retcode == 88
        assert calls_required == [0.3]

        with pytest.raises(ValueError):
            comm.send_user_frame(7, b"\x00")
        with pytest.raises(ValueError):
            comm.send_user_frame(256, b"\x00")
        with pytest.raises(ValueError):
            comm.send_user_frame(8, b"\x00", ack_mode="bad")


def test_recv_thread_dispatches_user_frames():
    i = DummyDev(thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        seen = []

        def on_user(frame):
            seen.append(int(frame.fid))
            return True

        comm.add_user_frame_listener(on_user)
        comm._read_frame = lambda: DParseFrame(fid=8, data=b"\x00")

        comm._recv_thread()
        assert seen == [8]
        assert comm._get_frame(timeout=0.01) is None


def test_user_listener_invalid_range():
    i = DummyDev(thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        with pytest.raises(ValueError):
            comm.add_user_frame_listener(lambda _f: True, frame_ids=[7])
        with pytest.raises(ValueError):
            comm.add_user_frame_listener(lambda _f: True, frame_ids=[256])


def test_dispatch_user_frame_unhandled_goes_to_queue():
    i = DummyDev(thread_timeout=0.05)
    p = Parser()
    with CommHandler(
        i, p, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm:
        seen = []

        def listener_false(frame):
            seen.append(("false", int(frame.fid)))
            return False

        def listener_true(frame):
            seen.append(("true", int(frame.fid)))
            return True

        comm.add_user_frame_listener(listener_false, frame_ids=[8])
        comm.add_user_frame_listener(listener_true, frame_ids=[8])

        frame = DParseFrame(fid=8, data=b"\x00")
        assert comm._dispatch_user_frame(frame) is True
        assert seen == [("false", 8), ("true", 8)]

        comm.remove_user_frame_listener(1)
        assert comm._dispatch_user_frame(frame) is False

        comm._read_frame = lambda: frame
        comm._recv_thread()
        queued = comm._get_frame(timeout=0.05)
        assert queued is not None
        assert int(queued.fid) == 8


def test_get_ack_required_paths():
    i_noack = DummyDev(
        flags=EDeviceFlags.DIVIDER_SUPPORT.value, thread_timeout=0.05
    )
    p_noack = Parser()
    with CommHandler(
        i_noack, p_noack, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm_noack:
        ret = comm_noack._get_ack_required(timeout=0.01)
        assert ret.state is False
        assert ret.retcode == -3

    i_ack = DummyDev(
        flags=(
            EDeviceFlags.DIVIDER_SUPPORT.value | EDeviceFlags.ACK_SUPPORT.value
        ),
        thread_timeout=0.05,
    )
    p_ack = Parser()
    with CommHandler(
        i_ack, p_ack, drop_timeout=0.01, stream_data_timeout=0.05
    ) as comm_ack:
        orig_get_frame = comm_ack._get_frame
        orig_ack_decode = comm_ack._parse.frame_ack_decode
        try:
            comm_ack._get_frame = lambda timeout=1.0: None
            ret = comm_ack._get_ack_required(timeout=0.01)
            assert ret.state is False
            assert ret.retcode == -1

            comm_ack._get_frame = lambda timeout=1.0: DParseFrame(
                fid=4, data=b"\x00"
            )
            comm_ack._parse.frame_ack_decode = lambda _frame: None
            ret = comm_ack._get_ack_required(timeout=0.01)
            assert ret.state is False
            assert ret.retcode == -2

            comm_ack._parse.frame_ack_decode = lambda _frame: ParseAck(
                True, 123
            )
            ret = comm_ack._get_ack_required(timeout=0.01)
            assert ret.state is True
            assert ret.retcode == 123
        finally:
            comm_ack._get_frame = orig_get_frame
            comm_ack._parse.frame_ack_decode = orig_ack_decode
