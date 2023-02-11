"""The Nxslib common thread logic."""

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

###############################################################################
# Class: ThreadCommon
###############################################################################


class ThreadCommon:
    """A class that handle common thread logic."""

    def __init__(
        self,
        target: "Callable[[], None]",
        init: "Callable[[], None] | None" = None,
        final: "Callable[[], None] | None" = None,
    ) -> None:
        """Initialize common thread.

        :param: callable object to be invoked
        """
        assert callable(target)
        if init:
            assert callable(init)
        if final:
            assert callable(final)
        self._target = target
        self._init = init
        self._final = final
        self._thrd: threading.Thread | None = None
        self._stop_flag = threading.Event()

    def _stop_is_set(self) -> bool:
        """Return stop flag state."""
        return self._stop_flag.is_set()

    def _stop_set(self) -> None:
        """Set stop flag."""
        self._stop_flag.set()

    def _thread_loop(self) -> None:
        # one time initialization
        if self._init:
            self._init()

        # thread loop
        while not self._stop_is_set():
            self._target()

        # final logic
        if self._final:
            self._final()

    def _stop_clear(self) -> None:
        """Clear stop flag."""
        self._stop_flag.clear()

    def thread_is_alive(self) -> bool:
        """Return true is thread is alive."""
        if self._thrd is None:
            return False

        return self._thrd.is_alive()

    def thread_stop(self) -> None:
        """Stop thread."""
        if self._thrd is None:
            return

        # stop request for thread
        self._stop_set()

        # wait for thread
        if self.thread_is_alive():
            self._thrd.join()

    def thread_start(self) -> None:
        """Start thread."""
        self._stop_clear()
        self._thrd = threading.Thread(target=self._thread_loop)
        self._thrd.start()
