"""Epytext docstring formatter.

Implements the Epytext documentation format used by Epydoc:
http://epydoc.sourceforge.net/epytext.html

Epytext uses @ tags for markup instead of reStructuredText's colon syntax.
"""

from __future__ import annotations

from docpilot.core.models import CodeElement, ParameterInfo
from docpilot.formatters.base import BaseFormatter


class EpytextFormatter(BaseFormatter):
    """Formatter for Epytext-style docstrings.

    Epytext style uses @ tags for field markup:

    Example:
        ```python
        def function(arg1: int, arg2: str) -> bool:
            '''Summary line.

            Longer description if needed.

            @param arg1: Description of arg1
            @type arg1: int
            @param arg2: Description of arg2
            @type arg2: str
            @return: Description of return value
            @rtype: bool
            @raise ValueError: When something is wrong
            '''
        ```
    """

    def __init__(
        self,
        indent: str = "    ",
        max_line_length: int = 88,
        include_types: bool = True,
        separate_type_lines: bool = True,
    ) -> None:
        """Initialize Epytext formatter.

        Args:
            indent: Indentation string
            max_line_length: Maximum line length
            include_types: Whether to include type information
            separate_type_lines: Whether to use separate @type lines
        """
        super().__init__(indent, max_line_length, include_types)
        self.separate_type_lines = separate_type_lines

    def format(self, element: CodeElement, docstring_content: str) -> str:
        """Format a docstring in Epytext style.

        Args:
            element: Code element being documented
            docstring_content: Raw docstring content

        Returns:
            Formatted Epytext docstring
        """
        sections = self.parse_structured_content(docstring_content)

        lines: list[str] = []

        # Summary
        summary = sections.get("summary", "")
        if isinstance(summary, str):
            lines.append(self.format_summary(summary))

        # Extended description
        for section_name in ["description"]:
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
                    lines.extend(params_text.splitlines())

        # Returns
        if element.return_info or "returns" in sections:
            return_type = element.return_info.type_hint if element.return_info else None
            return_desc = sections.get("returns", "")
            if isinstance(return_desc, str) and return_desc:
                returns_text = self.format_returns(return_type, return_desc)
                if returns_text:
                    lines.append("")
                    lines.extend(returns_text.splitlines())

        # Yields
        if element.return_info and element.return_info.is_generator:
            yields_desc = sections.get("yields", "")
            if isinstance(yields_desc, str) and yields_desc:
                lines.append("")
                lines.extend(self.format_yields(yields_desc).splitlines())

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
                    lines.extend(raises_text.splitlines())

        # Examples
        examples = sections.get("examples", "")
        if isinstance(examples, str) and examples:
            lines.append("")
            lines.extend(self.format_examples(examples).splitlines())

        # Notes
        notes = sections.get("notes", "")
        if isinstance(notes, str) and notes:
            lines.append("")
            lines.extend(self.format_notes(notes).splitlines())

        # Warnings
        warnings = sections.get("warnings", "")
        if isinstance(warnings, str) and warnings:
            lines.append("")
            lines.extend(self.format_warnings(warnings).splitlines())

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

    def format_parameters(
        self, parameters: list[ParameterInfo], descriptions: dict[str, str]
    ) -> str:
        """Format the parameter field list.

        Args:
            parameters: List of parameters
            descriptions: Parameter descriptions

        Returns:
            Formatted parameter fields
        """
        lines: list[str] = []

        for param in parameters:
            if param.name in ("self", "cls"):
                continue

            desc = descriptions.get(param.name, "Description needed")

            # @param name: description
            param_line = f"@param {param.name}: {desc}"
            lines.append(param_line)

            # @type name: type (if separate type lines enabled and type available)
            if self.separate_type_lines and self.include_types and param.type_hint:
                type_line = f"@type {param.name}: {param.type_hint}"
                lines.append(type_line)

        return "\n".join(lines)

    def format_returns(self, return_type: str | None, description: str) -> str:
        """Format the return field.

        Args:
            return_type: Return type annotation
            description: Return value description

        Returns:
            Formatted return fields
        """
        lines: list[str] = []

        # @return: description (note: 'return' not 'returns' in Epytext)
        return_line = f"@return: {description}"
        lines.append(return_line)

        # @rtype: type
        if self.separate_type_lines and self.include_types and return_type:
            rtype_line = f"@rtype: {return_type}"
            lines.append(rtype_line)

        return "\n".join(lines)

    def format_yields(self, description: str) -> str:
        """Format the yields field.

        Args:
            description: Description of yielded values

        Returns:
            Formatted yields field
        """
        return f"@yield: {description}"

    def format_raises(self, exceptions: dict[str, str]) -> str:
        """Format the raises fields.

        Args:
            exceptions: Exception types and descriptions

        Returns:
            Formatted raises fields
        """
        lines: list[str] = []

        for exc_type, desc in exceptions.items():
            if not desc:
                desc = "Description needed"

            # @raise ExceptionType: description (note: 'raise' not 'raises')
            raises_line = f"@raise {exc_type}: {desc}"
            lines.append(raises_line)

        return "\n".join(lines)

    def format_examples(self, examples: str) -> str:
        """Format the examples section.

        Args:
            examples: Example code/text

        Returns:
            Formatted examples
        """
        lines = ["@example:"]

        # Indent example lines
        example_lines = examples.splitlines()
        for line in example_lines:
            lines.append(f"{self.indent}{line}")

        return "\n".join(lines)

    def format_notes(self, notes: str) -> str:
        """Format the notes section.

        Args:
            notes: Additional notes

        Returns:
            Formatted notes
        """
        # Wrap notes
        notes_wrapped = self.wrap_text(notes)
        return f"@note: {notes_wrapped}"

    def format_warnings(self, warnings: str) -> str:
        """Format the warnings section.

        Args:
            warnings: Warning text

        Returns:
            Formatted warnings
        """
        # Wrap warnings
        warnings_wrapped = self.wrap_text(warnings)
        return f"@warning: {warnings_wrapped}"

    def _parse_raises_section(self, raises_text: str) -> dict[str, str]:
        """Parse raises section to extract exceptions.

        Args:
            raises_text: Text of raises section

        Returns:
            Dictionary of exception types to descriptions
        """
        exceptions: dict[str, str] = {}
        lines = raises_text.splitlines()

        current_exc: str | None = None
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
                # Continuation
                current_desc.append(stripped)

        # Save final exception
        if current_exc and current_desc:
            exceptions[current_exc] = " ".join(current_desc).strip()

        return exceptions
