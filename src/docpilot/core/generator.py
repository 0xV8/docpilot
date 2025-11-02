"""Docstring generation orchestrator.

This module coordinates the entire documentation generation process,
integrating parsing, analysis, LLM generation, and formatting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

import structlog

from docpilot.core.analyzer import CodeAnalyzer
from docpilot.core.models import (
    CodeElement,
    DocumentationContext,
    DocstringStyle,
    GeneratedDocstring,
    ParseResult,
)
from docpilot.core.parser import PythonParser

logger = structlog.get_logger(__name__)


class DocstringFormatter(Protocol):
    """Protocol for docstring formatters.

    All formatter implementations must follow this interface.
    """

    def format(self, element: CodeElement, docstring_content: str) -> str:
        """Format a docstring according to a specific style.

        Args:
            element: Code element being documented
            docstring_content: Raw docstring content to format

        Returns:
            Formatted docstring
        """
        ...


class LLMProvider(Protocol):
    """Protocol for LLM providers.

    All LLM provider implementations must follow this interface.
    """

    async def generate_docstring(self, context: DocumentationContext) -> str:
        """Generate docstring content using an LLM.

        Args:
            context: Documentation context with code element and settings

        Returns:
            Generated docstring content
        """
        ...


class DocstringGenerator:
    """Orchestrates the docstring generation process.

    This class coordinates parsing, analysis, LLM generation, and formatting
    to produce high-quality docstrings for Python code elements.

    Attributes:
        llm_provider: LLM provider for generating docstring content
        formatter: Docstring formatter for the desired style
        parser: Python code parser
        analyzer: Code analyzer for metadata extraction
        default_style: Default docstring style to use
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        formatter: Optional[DocstringFormatter] = None,
        default_style: DocstringStyle = DocstringStyle.GOOGLE,
        analyze_code: bool = True,
    ) -> None:
        """Initialize the docstring generator.

        Args:
            llm_provider: LLM provider instance (required for AI generation)
            formatter: Docstring formatter instance (will use default if not provided)
            default_style: Default docstring style
            analyze_code: Whether to perform code analysis
        """
        self.llm_provider = llm_provider
        self.formatter = formatter
        self.default_style = default_style
        self.parser = PythonParser()
        self.analyzer = CodeAnalyzer() if analyze_code else None
        self._log = logger.bind(component="generator")

    async def generate_for_file(
        self,
        file_path: str | Path,
        style: Optional[DocstringStyle] = None,
        include_private: bool = False,
        overwrite_existing: bool = False,
    ) -> list[GeneratedDocstring]:
        """Generate docstrings for all elements in a Python file.

        Args:
            file_path: Path to Python file
            style: Docstring style (uses default if not specified)
            include_private: Whether to generate docs for private elements
            overwrite_existing: Whether to overwrite existing docstrings

        Returns:
            List of generated docstrings for each element
        """
        file_path = Path(file_path)
        style = style or self.default_style

        self._log.info(
            "generating_for_file",
            path=str(file_path),
            style=style.value,
        )

        # Parse the file
        self.parser.extract_private = include_private
        result = self.parser.parse_file(file_path)

        # Optionally analyze
        if self.analyzer:
            for element in result.elements:
                self.analyzer.analyze_element(element)

        # Generate docstrings for each element
        generated: list[GeneratedDocstring] = []

        for element in result.elements:
            # Skip if has docstring and not overwriting
            if element.has_docstring and not overwrite_existing:
                self._log.debug(
                    "skipping_element",
                    element=element.name,
                    reason="has_docstring",
                )
                continue

            try:
                docstring = await self.generate_for_element(element, style)
                generated.append(docstring)

            except Exception as e:
                self._log.error(
                    "generation_failed",
                    element=element.name,
                    error=str(e),
                )

        self._log.info(
            "file_generation_complete",
            path=str(file_path),
            generated_count=len(generated),
        )

        return generated

    async def generate_for_element(
        self,
        element: CodeElement,
        style: Optional[DocstringStyle] = None,
        context_elements: Optional[list[CodeElement]] = None,
        custom_instructions: Optional[str] = None,
    ) -> GeneratedDocstring:
        """Generate a docstring for a single code element.

        Args:
            element: Code element to document
            style: Docstring style (uses default if not specified)
            context_elements: Related elements for context
            custom_instructions: Additional generation instructions

        Returns:
            Generated docstring

        Raises:
            ValueError: If LLM provider is not configured
        """
        if not self.llm_provider:
            raise ValueError("LLM provider is required for docstring generation")

        style = style or self.default_style

        self._log.debug(
            "generating_for_element",
            element=element.name,
            type=element.element_type.value,
            style=style.value,
        )

        # Build documentation context
        context = DocumentationContext(
            element=element,
            style=style,
            context_elements=context_elements or [],
            custom_instructions=custom_instructions,
        )

        # Generate content using LLM
        docstring_content = await self.llm_provider.generate_docstring(context)

        # Format according to style
        if self.formatter:
            formatted_docstring = self.formatter.format(element, docstring_content)
        else:
            # Use unformatted if no formatter
            formatted_docstring = docstring_content

        # Calculate confidence score based on various factors
        confidence = self._calculate_confidence(element, docstring_content)

        # Collect any warnings
        warnings = self._generate_warnings(element, docstring_content)

        return GeneratedDocstring(
            element_name=element.name,
            element_type=element.element_type,
            docstring=formatted_docstring,
            style=style,
            confidence_score=confidence,
            warnings=warnings,
            metadata={
                "has_type_hints": bool(
                    element.parameters and any(p.type_hint for p in element.parameters)
                ),
                "complexity": element.complexity_score,
                "patterns": element.metadata.get("patterns", []),
            },
        )

    async def generate_for_project(
        self,
        project_path: str | Path,
        style: Optional[DocstringStyle] = None,
        include_private: bool = False,
        overwrite_existing: bool = False,
        file_pattern: str = "**/*.py",
    ) -> dict[str, list[GeneratedDocstring]]:
        """Generate docstrings for all files in a project.

        Args:
            project_path: Path to project directory
            style: Docstring style (uses default if not specified)
            include_private: Whether to generate docs for private elements
            overwrite_existing: Whether to overwrite existing docstrings
            file_pattern: Glob pattern for finding Python files

        Returns:
            Dictionary mapping file paths to generated docstrings
        """
        project_path = Path(project_path)
        style = style or self.default_style

        self._log.info(
            "generating_for_project",
            path=str(project_path),
            style=style.value,
        )

        results: dict[str, list[GeneratedDocstring]] = {}

        # Find all Python files
        python_files = list(project_path.glob(file_pattern))

        for py_file in python_files:
            # Skip common directories
            if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
                continue

            try:
                generated = await self.generate_for_file(
                    py_file,
                    style=style,
                    include_private=include_private,
                    overwrite_existing=overwrite_existing,
                )
                results[str(py_file)] = generated

            except Exception as e:
                self._log.error(
                    "file_generation_failed",
                    path=str(py_file),
                    error=str(e),
                )

        total_generated = sum(len(docs) for docs in results.values())
        self._log.info(
            "project_generation_complete",
            files_processed=len(results),
            total_docstrings=total_generated,
        )

        return results

    def _calculate_confidence(
        self, element: CodeElement, docstring_content: str
    ) -> float:
        """Calculate confidence score for generated docstring.

        Args:
            element: Code element
            docstring_content: Generated docstring content

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 1.0

        # Reduce confidence if element has no type hints
        if element.parameters and not any(p.type_hint for p in element.parameters):
            confidence -= 0.1

        # Reduce confidence if docstring is very short
        if len(docstring_content.split()) < 10:
            confidence -= 0.15

        # Reduce confidence for complex functions without examples
        if (
            element.complexity_score
            and element.complexity_score > 10
            and "example" not in docstring_content.lower()
        ):
            confidence -= 0.1

        # Increase confidence if all parameters are documented
        if element.parameters:
            param_names = {p.name for p in element.parameters if p.name not in ("self", "cls")}
            documented_params = {
                name
                for name in param_names
                if name in docstring_content.lower()
            }
            if param_names and documented_params == param_names:
                confidence += 0.1

        return max(0.0, min(1.0, confidence))

    def _generate_warnings(
        self, element: CodeElement, docstring_content: str
    ) -> list[str]:
        """Generate warnings about potential issues.

        Args:
            element: Code element
            docstring_content: Generated docstring content

        Returns:
            List of warning messages
        """
        warnings: list[str] = []

        # Warn if complex function has short docstring
        if element.complexity_score and element.complexity_score > 10:
            if len(docstring_content.split()) < 20:
                warnings.append(
                    f"Complex function (complexity {element.complexity_score}) "
                    "has brief documentation"
                )

        # Warn if parameters are missing type hints
        untyped_params = [
            p.name
            for p in element.parameters
            if not p.type_hint and p.name not in ("self", "cls")
        ]
        if untyped_params:
            warnings.append(
                f"Parameters without type hints: {', '.join(untyped_params)}"
            )

        # Warn if function raises exceptions but they're not documented
        if element.raises:
            exception_types = {e.exception_type for e in element.raises}
            documented_exceptions = {
                exc
                for exc in exception_types
                if exc.lower() in docstring_content.lower()
            }
            missing = exception_types - documented_exceptions
            if missing:
                warnings.append(
                    f"Raised exceptions not documented: {', '.join(missing)}"
                )

        return warnings

    def set_llm_provider(self, provider: LLMProvider) -> None:
        """Set or update the LLM provider.

        Args:
            provider: LLM provider instance
        """
        self.llm_provider = provider
        self._log.info("llm_provider_updated", provider=type(provider).__name__)

    def set_formatter(self, formatter: DocstringFormatter) -> None:
        """Set or update the docstring formatter.

        Args:
            formatter: Docstring formatter instance
        """
        self.formatter = formatter
        self._log.info("formatter_updated", formatter=type(formatter).__name__)


class MockLLMProvider:
    """Mock LLM provider for testing without API calls.

    This provider generates simple placeholder docstrings based on
    code element metadata, useful for testing and development.
    """

    async def generate_docstring(self, context: DocumentationContext) -> str:
        """Generate a simple placeholder docstring.

        Args:
            context: Documentation context

        Returns:
            Mock docstring content
        """
        element = context.element
        lines: list[str] = []

        # Summary
        lines.append(f"{element.element_type.value.title()} {element.name}.")

        # Parameters
        if element.parameters:
            params = [p for p in element.parameters if p.name not in ("self", "cls")]
            if params:
                lines.append("")
                lines.append("Args:")
                for param in params:
                    param_type = param.type_hint or "Any"
                    lines.append(f"    {param.name} ({param_type}): Description needed")

        # Returns
        if element.return_info and element.return_info.type_hint:
            lines.append("")
            lines.append("Returns:")
            lines.append(f"    {element.return_info.type_hint}: Description needed")

        # Raises
        if element.raises:
            lines.append("")
            lines.append("Raises:")
            for exc in element.raises:
                lines.append(f"    {exc.exception_type}: Description needed")

        return "\n".join(lines)
