=====
Usage
=====

Quick start
===========

The recommended way to manage resources is with the context manager protocol.
``NxscopeHandler.__enter__`` calls ``connect()`` and
``NxscopeHandler.__exit__`` calls
``disconnect()``, so cleanup is guaranteed even if an exception occurs.

.. code-block:: python

   from nxslib.proto.parse import Parser
   from nxslib.intf.dummy import DummyDev
   from nxslib.nxscope import NxscopeHandler

   parse = Parser()
   intf = DummyDev()

   with NxscopeHandler(intf, parse) as nxscope:
       print(nxscope.dev)

       # subscribe to channel data streams before starting
       q0 = nxscope.stream_sub(0)
       q1 = nxscope.stream_sub(1)

       # configure channels
       nxscope.channels_default_cfg()
       nxscope.ch_enable(0)
       nxscope.ch_enable(1)

       # configure divider if supported
       if nxscope.dev and nxscope.dev.data.div_supported:
           nxscope.ch_divider(0, 10)
           nxscope.ch_divider(1, 20)

       # configuration is buffered — write it to the device
       nxscope.channels_write()

       # start stream and read data
       nxscope.stream_start()
       data0 = q0.get(block=True, timeout=1)
       data1 = q1.get(block=True, timeout=1)
       print(data0)
       print(data1)

       # stop stream and unsubscribe
       nxscope.stream_stop()
       nxscope.stream_unsub(q0)
       nxscope.stream_unsub(q1)
   # nxscope.disconnect() is called automatically on context manager exit

Stream decode mode
==================

``NxscopeHandler`` now decodes stream frames in NumPy block mode by default.
This is the recommended mode for performance-sensitive pipelines.

If you need compatibility with older per-sample consumers, you can still opt
in to legacy decode mode explicitly:

.. code-block:: python

   with NxscopeHandler(intf, parse, stream_decode_mode="legacy") as nxscope:
       ...

Legacy mode is deprecated, should not be used for new code, and will be
removed in a future release.

If you need to manage the connection lifetime manually:

.. code-block:: python

   nxscope = NxscopeHandler(intf, parse)
   nxscope.connect()
   try:
       # ... work here
   finally:
       nxscope.disconnect()

Communication Interfaces
========================

All interface classes support the context manager protocol:

.. code-block:: python

   from nxslib.intf.serial import SerialDevice
   with SerialDevice("/dev/ttyACM0") as intf:
       ...  # intf.stop() called automatically on exit

Dummy device interface
~~~~~~~~~~~~~~~~~~~~~~

For a quick start, use the simulated NxScope device built into the library:

.. code-block:: python

   from nxslib.intf.dummy import DummyDev
   with DummyDev() as intf:
       ...

By default, the dummy interface implements a set of channels that generate
various types of data.

You can define your own device, including channel implementation.
Just use ``DummyDev`` class parameters: ``chmax``, ``flags``, and
``channels``.

Serial port interface
~~~~~~~~~~~~~~~~~~~~~

Connect to a real NxScope device over a serial port:

.. code-block:: python

   from nxslib.intf.serial import SerialDevice
   with SerialDevice("/dev/ttyACM0", baud=100000) as intf:
       ...

If your NxScope device supports DMA RX, you have to align data sending from
the client interface to the smallest value that will trigger a DMA transfer.
For this purpose there is an ``intf.write_padding`` property that configures
data padding for the ``write`` method.

You can use ``socat`` to connect to a simulated NuttX target:

.. code-block:: bash

   SERIAL_HOST={PATH}/ttyNX0
   SERIAL_NUTTX={PATH}/ttySIM0

   # run socat in background
   socat PTY,link=$SERIAL_NUTTX PTY,link=$SERIAL_HOST &
   stty -F $SERIAL_NUTTX raw
   stty -F $SERIAL_HOST raw
   stty -F $SERIAL_NUTTX 115200
   stty -F $SERIAL_HOST 115200

Segger RTT interface
~~~~~~~~~~~~~~~~~~~~

Connect to a device that supports NxScope over the Segger RTT interface:

.. code-block:: python

   from nxslib.intf.rtt import RTTDevice
   with RTTDevice("STM32G431CB", buffer_index=1, upsize=2048, interface="swd") as intf:
       ...

UDP interface
~~~~~~~~~~~~~

Connect to a device that supports NxScope over UDP:

.. code-block:: python

   from nxslib.intf.udp import UdpDevice
   with UdpDevice("192.168.0.10", 50000, local_port=0, timeout=1.0) as intf:
       ...

Use ``UdpDevice`` when the target exposes NxScope over UDP.
By default it binds to an ephemeral local port (``local_port=0``) and
reads with a 1 second timeout.

.. code-block:: python

   from nxslib.intf.udp import UdpDevice

   with UdpDevice("127.0.0.1", 50000, timeout=0.2) as intf:
       # pass ``intf`` to NxscopeHandler
       ...

Communication handler
=====================

User extensions and plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Nxslib supports user-defined NxScope frame IDs (IDs ``>= 8``) for protocol
extensions.

Sending a user frame:

.. code-block:: python

   ack = nxscope.send_user_frame(
       8,                       # user frame ID
       b"\x01\x02\x03",         # payload
       ack_mode="auto",         # auto | required | disabled
       ack_timeout=1.0,
   )

Receiving user frames with a callback:

.. code-block:: python

   def on_user_frame(frame):
       print(frame.fid, frame.data)
       return True  # handled

   listener_id = nxscope.add_user_frame_listener(on_user_frame, frame_ids=[8])
   # ...
   nxscope.remove_user_frame_listener(listener_id)

Plugin registration API:

.. code-block:: python

   from nxslib.plugin import INxscopePlugin

   class MyPlugin(INxscopePlugin):
       name = "my_plugin"

       def on_register(self, control):
           self.control = control

       def on_user_frame(self, frame):
           return False

   plugin = MyPlugin()
   nxscope.register_plugin(plugin, frame_ids=[8, 9])
   # ...
   nxscope.unregister_plugin("my_plugin")

Plugins can also create and publish extension channels
(protocol agnostic):

.. code-block:: python

   from nxslib.nxscope import DNxscopeStream

   nxscope.ext_channel_add(200)
   q = nxscope.stream_sub(200)
   nxscope.ext_publish_legacy(200, DNxscopeStream((1,), (0,)))

Extension request broker (transport agnostic):

.. code-block:: python

   # namespace handler on receiving side
   def on_ext(req):
       if req.cmd_id == 1:       # set value
           return b"ok"          # status=0, payload=b"ok"
       return (1, b"unknown")    # non-zero status => error response

   nxscope.ext_bind(0x21, on_ext)

   # one-way notify
   nxscope.ext_notify(0x21, 2, b"fire", ack_mode="auto")

   # raw request/response (independent from ACK support)
   resp = nxscope.ext_request(
       0x21,
       1,
       b"\x10\x20",
       timeout=0.5,
       ack_mode="auto",          # can be disabled/required/auto
   )
   print(resp.status, resp.payload)

   # helper API: returns payload or raises DExtCallError
   data = nxscope.ext_call(
       0x21,
       1,
       b"\x10\x20",
       timeout=0.5,
       ack_mode="auto",
   )

   # typed helper
   value = nxscope.ext_call_decode(
       0x21,
       3,
       b"",
       decode=lambda raw: int.from_bytes(raw, "little"),
   )

The extension broker lives in ``nxslib`` and works with any NxScope transport
(``serial``, ``udp``, ``rtt``, and future interfaces) because transport access
is owned by one ``NxscopeHandler`` instance.

Parser
~~~~~~

For now only standard NxScope frames are supported.

It should be easy to implement a custom protocol parser by providing
a class derived from ``ICommFrame``:

.. code-block:: python

   from nxslib.proto.iframe import ICommFrame
   from nxslib.proto.parse import Parser

   class OurCustomFrame(ICommFrame):
       pass # custom implementation

   parse = Parser(frame=OurCustomFrame)
