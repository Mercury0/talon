"""Display utilities for banners and UI elements."""

import random
from ..utils.colors import Fore, Style

VERSION = "0.1.0"

ASCII_LOGO = """

████████╗ █████╗ ██╗      ██████╗ ███╗   ██╗
╚══██╔══╝██╔══██╗██║     ██╔═══██╗████╗  ██║
   ██║   ███████║██║     ██║   ██║██╔██╗ ██║
   ██║   ██╔══██║██║     ██║   ██║██║╚██╗██║
   ██║   ██║  ██║███████╗╚██████╔╝██║ ╚████║
   ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝"""


def print_banner_lines():
    """Print the ASCII logo and version."""
    # Keep a blank line before and after the ASCII logo
    print()  # leading blank
    lines = ASCII_LOGO.splitlines()
    if lines and lines[0] == "":
        lines = lines[1:]  # drop leading empty from triple-quoted literal

    if not lines:
        print(Fore.WHITE + Style.BRIGHT + VERSION + Style.RESET_ALL)
    else:
        for line in lines[:-1]:
            print(Fore.WHITE + line + Style.RESET_ALL)
        # last line + bold version
        print(
            Fore.WHITE
            + lines[-1]
            + " "
            + Style.BRIGHT
            + VERSION
            + Style.RESET_ALL
        )
    print()  # trailing blank
    print(Fore.CYAN + Style.BRIGHT + " 2025 @markfox" + Style.RESET_ALL)


def print_banner_with_intro():
    """Print banner with interactive mode intro."""
    print_banner_lines()
    # Yellow + bold
    print(Fore.YELLOW + Style.BRIGHT + "[*] Starting interactive mode. Use CTRL+d to exit." + Style.RESET_ALL)


def generate_conn_id() -> str:
    """Generate a connection UUID-ish (10 chars)."""
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choice(alphabet) for _ in range(10))


def mask_secret(val: str) -> str:
    """Mask a secret value for display."""
    if not val:
        return ""
    if len(val) <= 6:
        return "*" * len(val)
    return val[:2] + "*" * (len(val)-4) + val[-2:]


def _returned_to_root():
    """Print 'returned to root menu' message."""
    print(Fore.CYAN + Style.BRIGHT + "Returned to root menu" + Style.RESET_ALL)
