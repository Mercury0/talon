"""Interactive selector widget for choosing from lists."""

from __future__ import annotations

import os
import sys
from typing import List, Optional


def _ansi_move_up(n: int) -> None:
    """Move cursor up n lines."""
    if n > 0:
        sys.stdout.write(f"\x1b[{n}A")


def _ansi_clear_line() -> None:
    """Clear current line."""
    sys.stdout.write("\x1b[2K\r")


def select_index(options: List[str], title: str = "Connection IDs") -> Optional[int]:
    """
    Minimal selector that:
      - Prints a numbered list
      - Supports arrow keys (↑/↓) or typing a number and Enter
      - Esc / empty Enter to cancel
    Uses inline ANSI to redraw only the list lines (no full-screen clear).
    Propagates CTRL+C to caller so we can bounce to root.
    """
    if not options:
        return None

    # Non-interactive fallback
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        for i, opt in enumerate(options, 1):
            print(f"{i}. {opt}")
        try:
            sel = input("Select by number (Enter to cancel): ").strip()
        except EOFError:
            print()
            return None
        except KeyboardInterrupt:
            print()
            raise
        if not sel:
            return None
        if not sel.isdigit():
            print("Invalid selection.")
            return None
        n = int(sel)
        return n - 1 if 1 <= n <= len(options) else None

    print(title + ":")
    print("Use ↑/↓ or type a number; Enter to select; Esc to cancel.")

    idx: int = 0
    buf: str = ""  # numeric buffer

    # Initial draw
    for i, opt in enumerate(options, 1):
        prefix = "->" if (i - 1) == idx else "  "
        print(f"{prefix} {i}. {opt}")

    def redraw() -> None:
        _ansi_move_up(len(options))
        for i, opt in enumerate(options, 1):
            prefix = "->" if (i - 1) == idx else "  "
            _ansi_clear_line()
            sys.stdout.write(f"{prefix} {i}. {opt}\n")
        sys.stdout.flush()

    try:
        # -------------------------------------------
        # WINDOWS (msvcrt.getwch) with safe guard
        # -------------------------------------------
        if os.name == "nt":
            try:
                import msvcrt  # type: ignore
            except ImportError:
                msvcrt = None  # type: ignore

            if msvcrt is None or not hasattr(msvcrt, "getwch"):
                # Fallback to numeric selection
                raise RuntimeError("msvcrt.getwch unavailable")

            while True:
                ch = msvcrt.getwch()  # type: ignore[attr-defined]

                if ch == "\x03":  # CTRL+C
                    raise KeyboardInterrupt

                if ch in ("\r", "\n"):
                    if buf.isdigit():
                        n = int(buf)
                        buf = ""
                        if 1 <= n <= len(options):
                            print()
                            return n - 1
                        continue
                    print()
                    return idx

                if ch == "\x1b":  # ESC
                    print()
                    return None

                if ch == "\xe0":  # arrow prefix
                    k = msvcrt.getwch()  # type: ignore[attr-defined]
                    if k == "H":  # up
                        idx = (idx - 1) % len(options)
                        redraw()
                    elif k == "P":  # down
                        idx = (idx + 1) % len(options)
                        redraw()
                elif ch.isdigit():
                    buf += ch
                else:
                    buf = ""

        # -------------------------------------------
        # POSIX (termios + tty)
        # -------------------------------------------
        else:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)

            try:
                tty.setraw(fd)
                while True:
                    ch = sys.stdin.read(1)

                    if ch == "\x03":  # CTRL+C
                        raise KeyboardInterrupt

                    if ch in ("\r", "\n"):
                        if buf.isdigit():
                            n = int(buf)
                            buf = ""
                            if 1 <= n <= len(options):
                                print()
                                return n - 1
                            continue
                        print()
                        return idx

                    if ch == "\x1b":
                        nxt = sys.stdin.read(1)
                        if nxt == "[":
                            arrow = sys.stdin.read(1)
                            if arrow == "A":  # up
                                idx = (idx - 1) % len(options)
                                redraw()
                            elif arrow == "B":  # down
                                idx = (idx + 1) % len(options)
                                redraw()
                        else:
                            print()
                            return None

                    elif ch.isdigit():
                        buf += ch
                    else:
                        buf = ""

            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    except KeyboardInterrupt:
        print()
        raise
    except Exception:
        # Fallback to simple numeric selection
        print()
        for i, opt in enumerate(options, 1):
            print(f"{i}. {opt}")
        try:
            sel = input("Select by number (Enter to cancel): ").strip()
        except EOFError:
            print()
            return None
        except KeyboardInterrupt:
            print()
            raise
        if not sel or not sel.isdigit():
            return None
        n = int(sel)
        return n - 1 if 1 <= n <= len(options) else None

    return None
