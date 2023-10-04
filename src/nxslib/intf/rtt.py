"""Module containing the NxScope RTT interface implementation."""

import time

import pylink  # type: ignore

from nxslib.intf.iintf import ICommInterface
from nxslib.logger import logger

###############################################################################
# Class: RTTDevice
###############################################################################


class RTTDevice(ICommInterface):  # pragma: no cover
    """A class used to represent a serial port interface."""

    def __init__(
        self,
        target_device: str,
        buffer_index: int,
        upsize: int,
        interface: str,
        blockaddr: str = "auto",
    ) -> None:
        """Intitialize a serial interface.

        :param : target_device: target chip name
        :param : buffer_index: nxscope RTT buffer index
        :param : upsize: nxscope RTT buffer size
        :param : interface: JLink interface: swd or jtag
        :param : blockaddr: RTT block address as hex or `auto`
        """
        # ger RTT block address
        if blockaddr != "auto":
            block_address = int(blockaddr, 16)
            print("RTT block address = ", hex(block_address))
        else:
            block_address = None
            print("Auto-search for RTT block address")

        # get JLink interface
        if interface in ["swd", "SWD"]:
            jlinkinterface = pylink.enums.JLinkInterfaces.SWD
            print("JLink interface is SWD")
        elif interface in ["jtag", "JTAG"]:
            jlinkinterface = pylink.enums.JLinkInterfaces.JTAG
            print("JLink interface is JTAG")
        else:
            raise ValueError

        self.buffer_index = buffer_index
        self.upsize = upsize

        # connect to JLink
        while True:
            try:
                print("connecting to", target_device, "...")
                self._jlink = pylink.JLink()
                self._jlink.open()
                self._jlink.set_tif(jlinkinterface)
                self._jlink.connect(target_device)
                print("connected, starting RTT...")
                self._jlink.rtt_start(block_address)
                break
            except pylink.errors.JLinkException:
                time.sleep(0.1)

        # wait for RTT (revisit: do we need that ?)
        while True:
            try:
                num_up = self._jlink.rtt_get_num_up_buffers()
                num_down = self._jlink.rtt_get_num_down_buffers()
                print(
                    "RTT started, %d up bufs, %d down bufs."
                    % (num_up, num_down)
                )
                break
            except pylink.errors.JLinkRTTException:
                time.sleep(0.1)

        super().__init__()

    def __del__(self) -> None:
        """Make sure that serial port is closed."""

    def start(self) -> None:
        """Start the interface."""
        logger.debug("start RTT interface")

    def stop(self) -> None:
        """Stop the interface."""
        logger.debug("Stop RTT interface")

    def drop_all(self) -> None:
        """Drop all frames."""
        cntr = 4
        while cntr > 0:
            ret = self._read()
            if not ret:  # pragma: no cover
                cntr -= 1

    def _read(self) -> bytes:
        """Interface specific read method."""
        assert self._jlink
        try:
            _bytes = self._jlink.rtt_read(self.buffer_index, self.upsize)
            return bytes(_bytes)
        except Exception as exc:
            logger.debug("pylink exception ignored: %s", str(exc))
            return b""

    def _write(self, data: bytes) -> None:
        """Interface specific write method.

        :param data: bytes to send
        """
        assert self._jlink
        self._jlink.rtt_write(self.buffer_index, data)
