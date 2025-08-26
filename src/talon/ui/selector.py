"""Interactive selector widget for choosing from lists."""

import os
import sys
from typing import List, Optional


def _ansi_move_up(n: int):
    """Move cursor up n lines."""
    if n > 0:
        sys.stdout.write(f"\x1b[{n}A")


def _ansi_clear_line():
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
    # initial render
    idx = 0
    for i, opt in enumerate(options, 1):
        prefix = "->" if (i - 1) == idx else "  "
        print(f"{prefix} {i}. {opt}")

    buf = ""  # numeric buffer

    def redraw():
        # Move cursor up N option lines, then rewrite each line
        _ansi_move_up(len(options))
        for i, opt in enumerate(options, 1):
            prefix = "->" if (i - 1) == idx else "  "
            _ansi_clear_line()
            sys.stdout.write(f"{prefix} {i}. {opt}\n")
        sys.stdout.flush()

    try:
        if os.name == "nt":
            import msvcrt
            while True:
                ch = msvcrt.getwch()
                if ch == "\x03":  # CTRL+C
                    raise KeyboardInterrupt
                if ch in ("\r", "\n"):
                    if buf.isdigit():
                        n = int(buf)
                        buf = ""
                        if 1 <= n <= len(options):
                            print()
                            return n - 1
                        else:
                            continue
                    print()
                    return idx
                if ch == "\x1b":  # ESC
                    print()
                    return None
                if ch == "\xe0":  # arrow prefix
                    k = msvcrt.getwch()
                    if k == "H":   # up
                        idx = (idx - 1) % len(options)
                        redraw()
                    elif k == "P": # down
                        idx = (idx + 1) % len(options)
                        redraw()
                elif ch.isdigit():
                    buf += ch
                else:
                    buf = ""
        else:
            import tty
            import termios
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
                            else:
                                continue
                        print()
                        return idx
                    if ch == "\x1b":
                        nxt = sys.stdin.read(1)
                        if nxt == "[":
                            arrow = sys.stdin.read(1)
                            if arrow == "A":   # up
                                idx = (idx - 1) % len(options)
                                redraw()
                            elif arrow == "B": # down
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
        # Fallback to simple numeric prompt if anything goes wrong
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
