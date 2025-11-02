"""Base formatter interface and common utilities for docstring formatting.

This module defines the abstract base class that all docstring formatters
must implement, along with shared utilities for formatting operations.
"""

from __future__ import annotations

import textwrap
from abc import ABC, abstractmethod

from docpilot.core.models import CodeElement, ParameterInfo


class BaseFormatter(ABC):
    """Abstract base class for docstring formatters.

    All docstring formatters (Google, NumPy, Sphinx, etc.) must inherit
    from this class and implement the required formatting methods.

    Attributes:
        indent: Indentation string (default 4 spaces)
        max_line_length: Maximum line length for wrapping
        include_types: Whether to include type information
    """

    def __init__(
        self,
        indent: str = "    ",
        max_line_length: int = 88,
        include_types: bool = True,
    ) -> None:
        """Initialize the formatter.

        Args:
            indent: String to use for indentation (e.g., "    " or "\\t")
            max_line_length: Maximum line length before wrapping
            include_types: Whether to include type annotations in docstrings
        """
        self.indent = indent
        self.max_line_length = max_line_length
        self.include_types = include_types

    @abstractmethod
    def format(self, element: CodeElement, docstring_content: str) -> str:
        """Format a docstring for a code element.

        Args:
            element: Code element being documented
            docstring_content: Raw docstring content to format

        Returns:
            Formatted docstring with proper style and structure
        """
        pass

    @abstractmethod
    def format_summary(self, summary: str) -> str:
        """Format the summary line of a docstring.

        Args:
            summary: Summary text

        Returns:
            Formatted summary line
        """
        pass

    @abstractmethod
    def format_parameters(
        self, parameters: list[ParameterInfo], descriptions: dict[str, str]
    ) -> str:
        """Format the parameters section.

        Args:
            parameters: List of parameter information
            descriptions: Mapping of parameter names to descriptions

        Returns:
            Formatted parameters section
        """
        pass

    @abstractmethod
    def format_returns(self, return_type: str | None, description: str) -> str:
        """Format the returns section.

        Args:
            return_type: Return type annotation (if any)
            description: Description of return value

        Returns:
            Formatted returns section
        """
        pass

    @abstractmethod
    def format_raises(self, exceptions: dict[str, str]) -> str:
        """Format the raises/exceptions section.

        Args:
            exceptions: Mapping of exception types to descriptions

        Returns:
            Formatted raises section
        """
        pass

    def wrap_text(
        self,
        text: str,
        width: int | None = None,
        initial_indent: str = "",
        subsequent_indent: str = "",
    ) -> str:
        """Wrap text to specified width while preserving structure.

        Args:
            text: Text to wrap
            width: Maximum line width (uses max_line_length if not specified)
            initial_indent: Indentation for first line
            subsequent_indent: Indentation for subsequent lines

        Returns:
            Wrapped text
        """
        if width is None:
            width = self.max_line_length

        # Handle empty text
        if not text or not text.strip():
            return ""

        # Preserve paragraph breaks
        paragraphs = text.split("\n\n")
        wrapped_paragraphs: list[str] = []

        for para in paragraphs:
            # Remove extra whitespace but preserve single newlines
            para = " ".join(para.split())

            if para:
                wrapped = textwrap.fill(
                    para,
                    width=width,
                    initial_indent=initial_indent,
                    subsequent_indent=subsequent_indent,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                wrapped_paragraphs.append(wrapped)

        return "\n\n".join(wrapped_paragraphs)

    def indent_block(self, text: str, levels: int = 1) -> str:
        """Indent a block of text.

        Args:
            text: Text to indent
            levels: Number of indentation levels

        Returns:
            Indented text
        """
        if not text:
            return ""

        indent_str = self.indent * levels
        lines = text.splitlines()
        return "\n".join(
            f"{indent_str}{line}" if line.strip() else "" for line in lines
        )

    def clean_content(self, content: str) -> str:
        """Clean and normalize docstring content.

        Args:
            content: Raw content to clean

        Returns:
            Cleaned content
        """
        # Remove excessive whitespace
        lines = [line.rstrip() for line in content.splitlines()]

        # Remove leading/trailing blank lines
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        return "\n".join(lines)

    def parse_structured_content(self, content: str) -> dict[str, str | dict[str, str]]:
        """Parse structured docstring content into sections.

        Attempts to extract sections like Args, Returns, Raises from
        unformatted content.

        Args:
            content: Raw docstring content

        Returns:
            Dictionary with sections (summary, args, returns, raises, etc.)
        """
        sections: dict[str, str | dict[str, str]] = {}
        current_section = "summary"
        current_content: list[str] = []

        lines = content.splitlines()

        section_keywords = {
            "args": ["args:", "arguments:", "parameters:", "params:"],
            "returns": ["returns:", "return:"],
            "raises": ["raises:", "exceptions:", "throws:"],
            "yields": ["yields:", "yield:"],
            "examples": ["examples:", "example:"],
            "notes": ["notes:", "note:"],
            "warnings": ["warnings:", "warning:"],
        }

        for line in lines:
            line_lower = line.strip().lower()

            # Check if line starts a new section
            section_found = False
            for section_name, keywords in section_keywords.items():
                if any(line_lower.startswith(kw) for kw in keywords):
                    # Save current section
                    if current_content:
                        sections[current_section] = "\n".join(current_content).strip()

                    current_section = section_name
                    current_content = []
                    section_found = True
                    break

            if not section_found:
                current_content.append(line)

        # Save final section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def extract_parameter_descriptions(self, args_section: str) -> dict[str, str]:
        """Extract parameter descriptions from args section text.

        Args:
            args_section: Text of the args/parameters section

        Returns:
            Mapping of parameter names to descriptions
        """
        descriptions: dict[str, str] = {}

        if not args_section:
            return descriptions

        lines = args_section.splitlines()
        current_param: str | None = None
        current_desc: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check if line starts a new parameter (typically indented or with special char)
            # Look for patterns like "param_name: description" or "param_name (type): description"
            if ":" in stripped and not stripped.startswith(" "):
                # Save previous parameter
                if current_param and current_desc:
                    descriptions[current_param] = " ".join(current_desc).strip()

                # Parse new parameter
                parts = stripped.split(":", 1)
                param_part = parts[0].strip()

                # Remove type annotations like "name (str)"
                if "(" in param_part and ")" in param_part:
                    param_part = param_part.split("(")[0].strip()

                current_param = param_part
                current_desc = [parts[1].strip()] if len(parts) > 1 else []

            elif current_param:
                # Continuation of current parameter description
                current_desc.append(stripped)

        # Save final parameter
        if current_param and current_desc:
            descriptions[current_param] = " ".join(current_desc).strip()

        return descriptions

    def get_type_annotation(
        self, param: ParameterInfo, include_default: bool = False
    ) -> str:
        """Get formatted type annotation for a parameter.

        Args:
            param: Parameter information
            include_default: Whether to include default value

        Returns:
            Formatted type annotation
        """
        parts: list[str] = []

        if self.include_types and param.type_hint:
            parts.append(param.type_hint)

        if include_default and param.default_value:
            if parts:
                parts.append(f"default: {param.default_value}")
            else:
                parts.append(f"default: {param.default_value}")

        return ", ".join(parts) if parts else ""
