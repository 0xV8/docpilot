"""Google-style docstring formatter.

Implements the Google Python Style Guide docstring format:
https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
"""

from __future__ import annotations

from typing import Optional

from docpilot.core.models import CodeElement, ParameterInfo
from docpilot.formatters.base import BaseFormatter


class GoogleFormatter(BaseFormatter):
    """Formatter for Google-style docstrings.

    Google style uses indented sections with capitalized headers:

    Example:
        ```python
        def function(arg1: int, arg2: str) -> bool:
            '''Summary line.

            Longer description if needed.

            Args:
                arg1: Description of arg1
                arg2: Description of arg2

            Returns:
                Description of return value

            Raises:
                ValueError: When something is wrong
            '''
        ```
    """

    def format(self, element: CodeElement, docstring_content: str) -> str:
        """Format a docstring in Google style.

        Args:
            element: Code element being documented
            docstring_content: Raw docstring content

        Returns:
            Formatted Google-style docstring
        """
        # Parse the content into sections
        sections = self.parse_structured_content(docstring_content)

        lines: list[str] = []

        # Summary (required)
        summary = sections.get("summary", "")
        if isinstance(summary, str):
            lines.append(self.format_summary(summary))

        # Extended description
        for section_name in ["description", "notes", "warnings"]:
            if section_name in sections:
                content = sections[section_name]
                if isinstance(content, str) and content:
                    lines.append("")
                    lines.append(self.wrap_text(content))

        # Parameters
        if element.parameters:
            params = [p for p in element.parameters if p.name not in ("self", "cls")]
            if params:
                # Extract descriptions from content
                args_section = sections.get("args", "")
                if isinstance(args_section, str):
                    descriptions = self.extract_parameter_descriptions(args_section)
                else:
                    descriptions = {}

                params_text = self.format_parameters(params, descriptions)
                if params_text:
                    lines.append("")
                    lines.append(params_text)

        # Returns
        if element.return_info or "returns" in sections:
            return_type = element.return_info.type_hint if element.return_info else None
            return_desc = sections.get("returns", "")
            if isinstance(return_desc, str) and return_desc:
                returns_text = self.format_returns(return_type, return_desc)
                if returns_text:
                    lines.append("")
                    lines.append(returns_text)

        # Yields (for generators)
        if element.return_info and element.return_info.is_generator:
            yields_desc = sections.get("yields", "")
            if isinstance(yields_desc, str) and yields_desc:
                lines.append("")
                lines.append(self.format_yields(yields_desc))

        # Raises
        if element.raises or "raises" in sections:
            exceptions: dict[str, str] = {}

            # Get exceptions from element
            for exc in element.raises:
                exceptions[exc.exception_type] = exc.description or ""

            # Merge with parsed exceptions
            raises_section = sections.get("raises", "")
            if isinstance(raises_section, str):
                parsed_exceptions = self._parse_raises_section(raises_section)
                exceptions.update(parsed_exceptions)

            if exceptions:
                raises_text = self.format_raises(exceptions)
                if raises_text:
                    lines.append("")
                    lines.append(raises_text)

        # Examples
        examples = sections.get("examples", "")
        if isinstance(examples, str) and examples:
            lines.append("")
            lines.append(self.format_examples(examples))

        # Clean and join
        result = "\n".join(lines)
        return self.clean_content(result)

    def format_summary(self, summary: str) -> str:
        """Format the summary line.

        Google style requires summary to be on a single line or
        wrapped at max_line_length.

        Args:
            summary: Summary text

        Returns:
            Formatted summary
        """
        # Clean and strip
        summary = summary.strip()

        # Ensure it ends with a period
        if summary and not summary.endswith((".", "!", "?")):
            summary += "."

        # Wrap if needed
        return self.wrap_text(summary, width=self.max_line_length)

    def format_parameters(
        self, parameters: list[ParameterInfo], descriptions: dict[str, str]
    ) -> str:
        """Format the Args section.

        Args:
            parameters: List of parameters
            descriptions: Parameter descriptions

        Returns:
            Formatted Args section
        """
        lines = ["Args:"]

        for param in parameters:
            # Skip self and cls
            if param.name in ("self", "cls"):
                continue

            # Get description
            desc = descriptions.get(param.name, "Description needed")

            # Build parameter line
            param_line_parts: list[str] = [f"{param.name}"]

            # Add type if available and requested
            type_annotation = self.get_type_annotation(param)
            if type_annotation:
                param_line_parts.append(f"({type_annotation})")

            # Add description
            param_line = f"{' '.join(param_line_parts)}: {desc}"

            # Wrap and indent
            wrapped = self.wrap_text(
                param_line,
                initial_indent=self.indent,
                subsequent_indent=self.indent + "    ",
            )
            lines.append(wrapped)

        return "\n".join(lines)

    def format_returns(self, return_type: Optional[str], description: str) -> str:
        """Format the Returns section.

        Args:
            return_type: Return type annotation
            description: Return value description

        Returns:
            Formatted Returns section
        """
        lines = ["Returns:"]

        # Build return line
        if self.include_types and return_type:
            return_line = f"{return_type}: {description}"
        else:
            return_line = description

        # Wrap and indent
        wrapped = self.wrap_text(
            return_line,
            initial_indent=self.indent,
            subsequent_indent=self.indent + "    ",
        )
        lines.append(wrapped)

        return "\n".join(lines)

    def format_yields(self, description: str) -> str:
        """Format the Yields section for generators.

        Args:
            description: Description of yielded values

        Returns:
            Formatted Yields section
        """
        lines = ["Yields:"]

        wrapped = self.wrap_text(
            description,
            initial_indent=self.indent,
            subsequent_indent=self.indent + "    ",
        )
        lines.append(wrapped)

        return "\n".join(lines)

    def format_raises(self, exceptions: dict[str, str]) -> str:
        """Format the Raises section.

        Args:
            exceptions: Exception types and descriptions

        Returns:
            Formatted Raises section
        """
        lines = ["Raises:"]

        for exc_type, desc in exceptions.items():
            if not desc:
                desc = "Description needed"

            exc_line = f"{exc_type}: {desc}"

            # Wrap and indent
            wrapped = self.wrap_text(
                exc_line,
                initial_indent=self.indent,
                subsequent_indent=self.indent + "    ",
            )
            lines.append(wrapped)

        return "\n".join(lines)

    def format_examples(self, examples: str) -> str:
        """Format the Examples section.

        Args:
            examples: Example code/text

        Returns:
            Formatted Examples section
        """
        lines = ["Examples:"]

        # Indent the examples
        example_lines = examples.splitlines()
        for line in example_lines:
            lines.append(f"{self.indent}{line}")

        return "\n".join(lines)

    def _parse_raises_section(self, raises_text: str) -> dict[str, str]:
        """Parse the raises section to extract exception types and descriptions.

        Args:
            raises_text: Text of raises section

        Returns:
            Dictionary mapping exception types to descriptions
        """
        exceptions: dict[str, str] = {}
        lines = raises_text.splitlines()

        current_exc: Optional[str] = None
        current_desc: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Look for "ExceptionType: description" pattern
            if ":" in stripped and not stripped.startswith(" "):
                # Save previous exception
                if current_exc and current_desc:
                    exceptions[current_exc] = " ".join(current_desc).strip()

                # Parse new exception
                parts = stripped.split(":", 1)
                current_exc = parts[0].strip()
                current_desc = [parts[1].strip()] if len(parts) > 1 else []

            elif current_exc:
                # Continuation of description
                current_desc.append(stripped)

        # Save final exception
        if current_exc and current_desc:
            exceptions[current_exc] = " ".join(current_desc).strip()

        return exceptions
