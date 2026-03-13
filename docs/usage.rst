Usage
=====

Quick start
-----------

The recommended way to manage resources is with the context manager protocol.
``NxscopeHandler.__enter__`` calls ``connect()`` and ``__exit__`` calls
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
       if nxscope.dev.div_supported:
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

If you need to manage the connection lifetime manually:

.. code-block:: python

   nxscope = NxscopeHandler(intf, parse)
   nxscope.connect()
   try:
       # ... work here
   finally:
       nxscope.disconnect()

Interfaces
----------

For a quick start, use the simulated NxScope device built into the library:

.. code-block:: python

   from nxslib.intf.dummy import DummyDev
   with DummyDev() as intf:
       ...

Connect to a real NxScope device over a serial port:

.. code-block:: python

   from nxslib.intf.serial import SerialDevice
   with SerialDevice("/dev/ttyACM0", baud=100000) as intf:
       ...

Connect to a device that supports NxScope over the Segger RTT interface:

.. code-block:: python

   from nxslib.intf.rtt import RTTDevice
   with RTTDevice("STM32G431CB", buffer_index=1, upsize=2048, interface="swd") as intf:
       ...

Connect to a device that supports NxScope over UDP:

.. code-block:: python

   from nxslib.intf.udp import UdpDevice
   with UdpDevice("192.168.0.10", 50000, local_port=0, timeout=1.0) as intf:
       ...

All interface classes support the context manager protocol:

.. code-block:: python

   with SerialDevice("/dev/ttyACM0") as intf:
       ...  # intf.stop() called automatically on exit

Communication handler
---------------------

Parser
^^^^^^

For now only standard NxScope frames are supported.

It should be easy to implemented a custom protocol parser by providing
a class derived from `ICommFrame`:

.. code-block:: python

   class OurCustomFrame(ICommFrame):
       pass # custom implementation

   frame = OurCustomFrame()
   parse = Parser(frame=frame)


Dummy device interface
""""""""""""""""""""""

At default, dummy interface implements set of channels that generate various
types of data.

You can define your own device, including channel implementation.
Just use `DummyDev` class parameters: `chmax`, `flags` and `channels`.


Serial port interface
"""""""""""""""""""""

If your NxScope device supports DMA RX, you have to align data sending from
the client interface to the smallest value that will trigger a DMA transfer.

For this purpose there is `intf.write_padding` property that configures data
padding for the `write` method.

You can use `socat` to connect to a simulated NuttX target:

.. code-block:: bash

   SERIAL_HOST={PATH}/ttyNX0
   SERIAL_NUTTX={PATH}/ttySIM0

   # run socat in background
   socat PTY,link=$SERIAL_NUTTX PTY,link=$SERIAL_HOST &
   stty -F $SERIAL_NUTTX raw
   stty -F $SERIAL_HOST raw
   stty -F $SERIAL_NUTTX 115200
   stty -F $SERIAL_HOST 115200

UDP interface
"""""""""""""

Use `UdpDevice` when the target exposes NxScope over UDP.
By default it binds to an ephemeral local port (`local_port=0`) and
reads with a 1 second timeout.

.. code-block:: python

   from nxslib.intf.udp import UdpDevice

   with UdpDevice("127.0.0.1", 50000, timeout=0.2) as intf:
       # pass `intf` to NxscopeHandler
       ...
