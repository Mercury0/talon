"""Color utilities and fallbacks."""

try:
    import colorama
    from colorama import Fore, Style
    colorama.just_fix_windows_console()
except ImportError:
    # Fallback (no colors)
    class _Fore:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ""

    class _Style:
        BRIGHT = NORMAL = RESET_ALL = DIM = ""

    Fore = _Fore()
    Style = _Style()

__all__ = ["Fore", "Style"]
