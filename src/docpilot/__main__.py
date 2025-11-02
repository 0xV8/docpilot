"""Main entry point for the docpilot CLI."""

import sys

from docpilot.cli.commands import main as cli_main


def main() -> int:
    """Execute the docpilot CLI application.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    cli_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
