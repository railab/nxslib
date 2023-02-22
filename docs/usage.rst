Usage
=====

Quick start
-----------

1. Set up the frame parser:

   .. code-block:: python

      from nxslib.proto.parse import Parser
      parse = Parser()

2. Initialize the communication interface.

   For a quick start, you can use a simulated NxScope device built into the library:
   
   .. code-block:: python

      from nxslib.intf.dummy import DummyDev
      intf = DummyDev()


   Alternatively, connect to the real NxScope serial device:

   .. code-block:: python

      serial_path = "/dev/ttyACM0"
      serial_buad = 100000
      intf = SerialDevice(serial_path, serial_baud)


3. Create a NxScope instance and connect with the communication handler:

   .. code-block:: python

      from nxslib.comm import CommHandler
      from nxslib.nxscope import NxscopeHandler

      nxscope = NxscopeHandler()

      comm = CommHandler(intf, parse)
      nxscope.intf_connect(comm)


4. Now, we can connect to the device:

   .. code-block:: python

      nxscope.connect()
      print(nxscope.dev)


5. Subscribe to the channel data stream:

   .. code-block:: python

      q0 = nxscope.stream_sub(0)
      q1 = nxscope.stream_sub(1)


6. Configure channels individually:

   .. code-block:: python

      # default configuration
      nxscope.channels_default_cfg()

      # enable channels
      nxscope.ch_enable(0)
      nxscope.ch_enable(1)

      # configure divider if supportd
      if nxscope.dev.div_supported:
          nxscope.ch_divider(0, 10)
          nxscope.ch_divider(1, 20)

   Channels configuration is buffered, so we have to explicitly
   write it to the device:

   .. code-block:: python

      nxscope.channels_write()

   You can verify channels configuration:

   .. code-block:: python

      print(nxscope.dev_channel_get(0).en)
      print(nxscope.dev_channel_get(1).en)
      print(nxscope.dev_channel_get(0).div)
      print(nxscope.dev_channel_get(1).div)


7. Start the data stream and get data from queue:

   .. code-block:: python

      # start stream
      nxscope.stream_start()

      # get data from channel 0 queue
      data0 = q0.get(block=True, timeout=1)

      # get data from channel 1 queue
      data1 = q1.get(block=True, timeout=1)

      print(data0)
      print(data1)


9. We done now, unsubscribe from queues:

   .. code-block:: python

      nxscope.stream_unsub(q0)
      nxscope.stream_unsub(q1)


9. And disconnect from the device:

   .. code-block:: python

      nxscope.disconnect()

   IMPORTANT: this must be done manually ! Garbage collector will not help us.

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


Interfaces
^^^^^^^^^^^

If your NxScope device support DMA RX, you have to align data sending from client
interface to the smallest value that will trigger DMA trasfer.

For this purpose there is `intf.write_padding` property that configure data padding
for `write` method.


Dummy device interface
""""""""""""""""""""""

At default, dummy interface implements set of channels that generate various
types of data.

You can define your own device, including channel implementation.
Just use `DummyDev` class parameters: `chmax`, `flags` and `channels`.


Serial port interface
""""""""""""""""""""""

You can use `socat` to connect to a simulated NuttX target:

.. code-block:: bash

   SERIAL_HOST={PATH}/ttyNX0
   SERIAL_NUTTX={PATH}/ttySIM0

   # run socat in background
   socat PTY,link=$SERIAL_NUTTX PTY,link=$SERIAL_HOST &
   stty -F $SERIAL_NUTTX raw
   tty -F $SERIAL_HOST raw
   stty -F $SERIAL_NUTTX 115200
   stty -F $SERIAL_HOST 115200

