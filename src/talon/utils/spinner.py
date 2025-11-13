"""Spinner utility for showing progress."""

import itertools
import sys
import threading
import time
from typing import Optional

try:
    from tqdm import tqdm
except ImportError as err:
    raise ImportError("This tool requires 'tqdm' for the spinner. Try: pip install tqdm") from err

from .colors import Fore, Style


class TqdmSpinner:
    """
    Bright white pipx-like spinner. Shows only: "⠼ Authenticating…"
    (no elapsed time). Automatically clears itself when stopped.
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Authenticating…", interval: float = 0.1):
        self.message = message
        self.interval = interval
        self._stop = threading.Event()
        self._thr: Optional[threading.Thread] = None

    def _run(self):
        frames = itertools.cycle(self.FRAMES)
        # Only description; leave=False to remove on close. Disable if not a TTY.
        with tqdm(total=0, bar_format="{desc}", leave=False, disable=not sys.stdout.isatty()) as t:
            while not self._stop.is_set():
                frame = next(frames)
                # bright white desc; no elapsed
                t.set_description_str(
                    Fore.WHITE + Style.BRIGHT + f"{frame} {self.message}" + Style.RESET_ALL
                )
                t.update(0)
                time.sleep(self.interval)

    def start(self, message: Optional[str] = None):
        if message is not None:
            self.message = message
        self._stop.clear()
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._thr.start()

    def stop(self):
        self._stop.set()
        if self._thr:
            self._thr.join(timeout=2.0)
        # ensure line cleared in case tqdm was disabled
        sys.stdout.write("\r\x1b[2K")
        sys.stdout.flush()
