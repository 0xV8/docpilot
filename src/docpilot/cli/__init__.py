"""Command-line interface for docpilot."""

from docpilot.cli.commands import cli, main
from docpilot.cli.ui import DocpilotUI, get_ui

__all__ = [
    "cli",
    "main",
    "DocpilotUI",
    "get_ui",
]
