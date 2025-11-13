"""Color utilities and fallbacks."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


# -------------------------------
# Protocols define the structure
# of Fore / Style objects whether
# colorama is installed or not.
# -------------------------------
@runtime_checkable
class ForeLike(Protocol):
    BLACK: str
    RED: str
    GREEN: str
    YELLOW: str
    BLUE: str
    MAGENTA: str
    CYAN: str
    WHITE: str
    RESET: str


@runtime_checkable
class StyleLike(Protocol):
    BRIGHT: str
    NORMAL: str
    RESET_ALL: str
    DIM: str


# -------------------------------
# Try real colorama, otherwise fallback
# -------------------------------
try:
    import colorama
    from colorama import Fore as _RealFore
    from colorama import Style as _RealStyle

    colorama.just_fix_windows_console()

    Fore: ForeLike = _RealFore  # type: ignore[assignment]
    Style: StyleLike = _RealStyle  # type: ignore[assignment]

except Exception:
    # Pure fallback (no colors)
    class _FallbackFore:
        BLACK = ""
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        MAGENTA = ""
        CYAN = ""
        WHITE = ""
        RESET = ""

    class _FallbackStyle:
        BRIGHT = ""
        NORMAL = ""
        RESET_ALL = ""
        DIM = ""

    Fore = _FallbackFore()
    Style = _FallbackStyle()


__all__ = ["Fore", "Style"]
