"""NumPy-style docstring formatter.

Implements the NumPy/SciPy documentation standard:
https://numpydoc.readthedocs.io/en/latest/format.html
"""

from __future__ import annotations

from typing import Optional

from docpilot.core.models import CodeElement, ParameterInfo
from docpilot.formatters.base import BaseFormatter


class NumpyFormatter(BaseFormatter):
    """Formatter for NumPy-style docstrings.

    NumPy style uses sections with underlined headers:

    Example:
        ```python
        def function(arg1: int, arg2: str) -> bool:
            '''Summary line.

            Longer description if needed.

            Parameters
            ----------
            arg1 : int
                Description of arg1
            arg2 : str
                Description of arg2

            Returns
            -------
            bool
                Description of return value

            Raises
            ------
            ValueError
                When something is wrong
            '''
        ```
    """

    def __init__(
        self,
        indent: str = "    ",
        max_line_length: int = 88,
        include_types: bool = True,
        section_underline_char: str = "-",
    ) -> None:
        """Initialize NumPy formatter.

        Args:
            indent: Indentation string
            max_line_length: Maximum line length
            include_types: Whether to include type information
            section_underline_char: Character for section underlines
        """
        super().__init__(indent, max_line_length, include_types)
        self.section_underline_char = section_underline_char

    def format(self, element: CodeElement, docstring_content: str) -> str:
        """Format a docstring in NumPy style.

        Args:
            element: Code element being documented
            docstring_content: Raw docstring content

        Returns:
            Formatted NumPy-style docstring
        """
        sections = self.parse_structured_content(docstring_content)

        lines: list[str] = []

        # Summary
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

        # Yields
        if element.return_info and element.return_info.is_generator:
            yields_desc = sections.get("yields", "")
            if isinstance(yields_desc, str) and yields_desc:
                lines.append("")
                lines.append(self.format_yields(yields_desc))

        # Raises
        if element.raises or "raises" in sections:
            exceptions: dict[str, str] = {}

            for exc in element.raises:
                exceptions[exc.exception_type] = exc.description or ""

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

        # See Also (common in NumPy docs)
        see_also = sections.get("see_also", "")
        if isinstance(see_also, str) and see_also:
            lines.append("")
            lines.append(self.format_see_also(see_also))

        # Notes
        notes = sections.get("notes", "")
        if isinstance(notes, str) and notes:
            lines.append("")
            lines.append(self.format_notes(notes))

        result = "\n".join(lines)
        return self.clean_content(result)

    def format_summary(self, summary: str) -> str:
        """Format the summary line.

        Args:
            summary: Summary text

        Returns:
            Formatted summary
        """
        summary = summary.strip()
        if summary and not summary.endswith((".", "!", "?")):
            summary += "."
        return self.wrap_text(summary, width=self.max_line_length)

    def format_section_header(self, section_name: str) -> str:
        """Format a section header with underline.

        Args:
            section_name: Name of the section

        Returns:
            Formatted section header with underline
        """
        underline = self.section_underline_char * len(section_name)
        return f"{section_name}\n{underline}"

    def format_parameters(
        self, parameters: list[ParameterInfo], descriptions: dict[str, str]
    ) -> str:
        """Format the Parameters section.

        Args:
            parameters: List of parameters
            descriptions: Parameter descriptions

        Returns:
            Formatted Parameters section
        """
        lines = [self.format_section_header("Parameters")]

        for param in parameters:
            if param.name in ("self", "cls"):
                continue

            desc = descriptions.get(param.name, "Description needed")

            # Parameter name and type on first line
            if self.include_types and param.type_hint:
                lines.append(f"{param.name} : {param.type_hint}")
            else:
                lines.append(param.name)

            # Description indented
            desc_wrapped = self.wrap_text(
                desc,
                initial_indent=self.indent,
                subsequent_indent=self.indent,
            )
            lines.append(desc_wrapped)

        return "\n".join(lines)

    def format_returns(self, return_type: Optional[str], description: str) -> str:
        """Format the Returns section.

        Args:
            return_type: Return type annotation
            description: Return value description

        Returns:
            Formatted Returns section
        """
        lines = [self.format_section_header("Returns")]

        # Return type (if available)
        if self.include_types and return_type:
            lines.append(return_type)

        # Description indented
        desc_wrapped = self.wrap_text(
            description,
            initial_indent=self.indent if return_type else "",
            subsequent_indent=self.indent if return_type else "",
        )
        lines.append(desc_wrapped)

        return "\n".join(lines)

    def format_yields(self, description: str) -> str:
        """Format the Yields section.

        Args:
            description: Description of yielded values

        Returns:
            Formatted Yields section
        """
        lines = [self.format_section_header("Yields")]

        desc_wrapped = self.wrap_text(
            description,
            initial_indent=self.indent,
            subsequent_indent=self.indent,
        )
        lines.append(desc_wrapped)

        return "\n".join(lines)

    def format_raises(self, exceptions: dict[str, str]) -> str:
        """Format the Raises section.

        Args:
            exceptions: Exception types and descriptions

        Returns:
            Formatted Raises section
        """
        lines = [self.format_section_header("Raises")]

        for exc_type, desc in exceptions.items():
            if not desc:
                desc = "Description needed"

            # Exception type
            lines.append(exc_type)

            # Description indented
            desc_wrapped = self.wrap_text(
                desc,
                initial_indent=self.indent,
                subsequent_indent=self.indent,
            )
            lines.append(desc_wrapped)

        return "\n".join(lines)

    def format_examples(self, examples: str) -> str:
        """Format the Examples section.

        Args:
            examples: Example code/text

        Returns:
            Formatted Examples section
        """
        lines = [self.format_section_header("Examples")]

        # Examples are typically code blocks, keep formatting
        example_lines = examples.splitlines()
        for line in example_lines:
            lines.append(line)

        return "\n".join(lines)

    def format_see_also(self, see_also: str) -> str:
        """Format the See Also section.

        Args:
            see_also: Related functions/classes

        Returns:
            Formatted See Also section
        """
        lines = [self.format_section_header("See Also")]
        lines.append(see_also)
        return "\n".join(lines)

    def format_notes(self, notes: str) -> str:
        """Format the Notes section.

        Args:
            notes: Additional notes

        Returns:
            Formatted Notes section
        """
        lines = [self.format_section_header("Notes")]

        notes_wrapped = self.wrap_text(notes)
        lines.append(notes_wrapped)

        return "\n".join(lines)

    def _parse_raises_section(self, raises_text: str) -> dict[str, str]:
        """Parse raises section to extract exceptions.

        Args:
            raises_text: Text of raises section

        Returns:
            Dictionary of exception types to descriptions
        """
        exceptions: dict[str, str] = {}
        lines = raises_text.splitlines()

        current_exc: Optional[str] = None
        current_desc: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                # Empty line might separate exceptions
                if current_exc and current_desc:
                    exceptions[current_exc] = " ".join(current_desc).strip()
                    current_exc = None
                    current_desc = []
                continue

            # Check if this is a new exception (not indented)
            if not line.startswith(" ") and not line.startswith("\t"):
                # Save previous exception
                if current_exc and current_desc:
                    exceptions[current_exc] = " ".join(current_desc).strip()

                # Start new exception
                current_exc = stripped
                current_desc = []

            elif current_exc:
                # Description line (indented)
                current_desc.append(stripped)

        # Save final exception
        if current_exc and current_desc:
            exceptions[current_exc] = " ".join(current_desc).strip()

        return exceptions
