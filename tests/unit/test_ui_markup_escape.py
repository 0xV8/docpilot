"""Tests for UI message escaping to prevent Rich markup interpretation issues.

This test ensures that error messages containing square brackets (like package
installation instructions with extras) are displayed correctly without truncation.
"""

import pytest
from io import StringIO
from rich.console import Console

from docpilot.cli.ui import DocpilotUI


class TestUIMarkupEscape:
    """Test suite for UI message escaping functionality."""

    def test_print_error_with_square_brackets(self):
        """Test that error messages with square brackets are not truncated."""
        # Create a console with string buffer to capture output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console)

        # Test message with square brackets (like pip install extras)
        error_message = "OpenAI package not installed. Install with: pip install docpilot[openai]"
        ui.print_error(error_message)

        # Get the output
        output = string_buffer.getvalue()

        # Verify the full message is present (not truncated)
        assert "docpilot[openai]" in output, f"Expected 'docpilot[openai]' in output, got: {output}"
        assert "OpenAI package not installed" in output
        assert "Install with: pip install" in output

    def test_print_error_with_multiple_square_brackets(self):
        """Test error messages with multiple square bracket groups."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console)

        error_message = "Install with: pip install docpilot[openai] or pip install docpilot[anthropic]"
        ui.print_error(error_message)

        output = string_buffer.getvalue()

        assert "docpilot[openai]" in output
        assert "docpilot[anthropic]" in output
        assert "or pip install" in output

    def test_print_warning_with_square_brackets(self):
        """Test that warning messages with square brackets are not truncated."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console)

        warning_message = "Optional dependency missing. Install with: pip install docpilot[ollama]"
        ui.print_warning(warning_message)

        output = string_buffer.getvalue()

        assert "docpilot[ollama]" in output
        assert "Optional dependency missing" in output

    def test_print_error_anthropic_provider(self):
        """Test error message for Anthropic provider."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console)

        error_message = "Anthropic package not installed. Install with: pip install docpilot[anthropic]"
        ui.print_error(error_message)

        output = string_buffer.getvalue()

        assert "docpilot[anthropic]" in output
        assert "Anthropic package not installed" in output

    def test_print_error_without_square_brackets(self):
        """Test that normal error messages still work correctly."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console)

        error_message = "Failed to initialize LLM provider: Connection timeout"
        ui.print_error(error_message)

        output = string_buffer.getvalue()

        assert "Failed to initialize LLM provider" in output
        assert "Connection timeout" in output

    def test_print_error_with_nested_brackets(self):
        """Test error messages with nested or complex bracket patterns."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console)

        # Message with brackets that might be confused with Rich markup
        error_message = "Config error: Expected format is {'provider': 'openai', 'options': ['key1', 'key2']}"
        ui.print_error(error_message)

        output = string_buffer.getvalue()

        # The brackets should be preserved
        assert "['key1', 'key2']" in output
        assert "{'provider': 'openai'" in output

    def test_quiet_mode_suppresses_error(self):
        """Test that quiet mode still shows errors (errors should always show)."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console, quiet=True)

        error_message = "Critical error with pip install docpilot[openai]"
        ui.print_error(error_message)

        output = string_buffer.getvalue()

        # Errors should still be shown in quiet mode
        assert "docpilot[openai]" in output
        assert "Critical error" in output

    def test_quiet_mode_suppresses_warning(self):
        """Test that quiet mode suppresses warnings."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console, quiet=True)

        warning_message = "Warning: pip install docpilot[openai] recommended"
        ui.print_warning(warning_message)

        output = string_buffer.getvalue()

        # Warnings should be suppressed in quiet mode
        assert output == ""

    def test_provider_initialization_error_message(self):
        """Test the complete error flow as it appears in commands.py."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console)

        # Simulate the actual error message from LLM provider initialization
        exception_message = "OpenAI package not installed. Install with: pip install docpilot[openai]"
        full_error = f"Failed to initialize LLM provider: {exception_message}"
        ui.print_error(full_error)

        output = string_buffer.getvalue()

        # Verify the complete message chain is preserved
        assert "Failed to initialize LLM provider" in output
        assert "OpenAI package not installed" in output
        assert "pip install docpilot[openai]" in output
        assert "docpilot[openai]" in output  # Most critical part

    def test_all_provider_extras(self):
        """Test all provider-specific extras are displayed correctly."""
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=200)
        ui = DocpilotUI(console=console)

        providers = ["openai", "anthropic", "ollama"]

        for provider in providers:
            string_buffer.truncate(0)
            string_buffer.seek(0)

            error_message = f"{provider.title()} package not installed. Install with: pip install docpilot[{provider}]"
            ui.print_error(error_message)

            output = string_buffer.getvalue()
            expected = f"docpilot[{provider}]"
            assert expected in output, f"Expected '{expected}' in output for {provider}, got: {output}"
