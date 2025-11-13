#!/usr/bin/env python3
"""Main entry point for Talon."""

import argparse

from .config.settings import TalonState
from .ui.display import print_banner_lines, print_banner_with_intro
from .ui.repl import TalonREPL
from .utils.colors import Fore, Style


def main():
    """Main entry point for the Talon application."""
    parser = argparse.ArgumentParser(
        prog="talon",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help="show this help message and exit")
    args, _ = parser.parse_known_args()

    if args.help:
        # -h output (no REPL)
        print_banner_lines()
        print(
            Fore.YELLOW
            + Style.BRIGHT
            + "[*] Starting interactive mode. Use CTRL+d to exit."
            + Style.RESET_ALL
        )
        # Bold ">" preview line
        print(Fore.WHITE + Style.BRIGHT + "> " + Style.RESET_ALL, end="")
        return

    # No CLI args: enter REPL
    print_banner_with_intro()
    state = TalonState()
    state.load_config()  # Load saved connections
    repl = TalonREPL(state)

    try:
        repl.root_loop()
    except KeyboardInterrupt:
        print()
    finally:
        state.save_config()  # Save on exit


if __name__ == "__main__":
    main()
