"""Docstring generation orchestrator.

This module coordinates the entire documentation generation process,
integrating parsing, analysis, LLM generation, and formatting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import structlog

from docpilot.core.analyzer import CodeAnalyzer
from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    DocstringStyle,
    DocumentationContext,
    GeneratedDocstring,
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

    async def test_connection(self) -> bool:
        """Test connection to the LLM provider.

        Returns:
            True if connection is successful, False otherwise
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
        llm_provider: LLMProvider | None = None,
        formatter: DocstringFormatter | None = None,
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
        style: DocstringStyle | None = None,
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
                element_full_name = f"{element.parent_class}.{element.name}" if element.parent_class else element.name
                self._log.info(
                    f"Skipped {element_full_name} (has docstring)"
                )
                # Still process methods of classes even if class has docstring
                if element.element_type == CodeElementType.CLASS:
                    for method in element.methods:
                        # Skip private methods if not including them
                        if not include_private and not method.is_public:
                            continue

                        method_full_name = f"{element.name}.{method.name}"
                        if method.has_docstring and not overwrite_existing:
                            self._log.info(
                                f"Skipped {method_full_name} (has docstring)"
                            )
                        else:
                            try:
                                self._log.info(
                                    f"Generated docstring for {method_full_name}"
                                )
                                docstring = await self.generate_for_element(method, style)
                                generated.append(docstring)
                            except Exception as e:
                                self._log.error(
                                    "method_generation_failed",
                                    method=method_full_name,
                                    error=str(e),
                                )
                continue

            try:
                element_full_name = f"{element.parent_class}.{element.name}" if element.parent_class else element.name
                self._log.info(
                    f"Generated docstring for {element_full_name}"
                )
                docstring = await self.generate_for_element(element, style)
                generated.append(docstring)

                # Process methods of classes that don't have docstrings
                if element.element_type == CodeElementType.CLASS:
                    for method in element.methods:
                        # Skip private methods if not including them
                        if not include_private and not method.is_public:
                            continue

                        method_full_name = f"{element.name}.{method.name}"
                        if method.has_docstring and not overwrite_existing:
                            self._log.info(
                                f"Skipped {method_full_name} (has docstring)"
                            )
                        else:
                            try:
                                self._log.info(
                                    f"Generated docstring for {method_full_name}"
                                )
                                method_docstring = await self.generate_for_element(method, style)
                                generated.append(method_docstring)
                            except Exception as e:
                                self._log.error(
                                    "method_generation_failed",
                                    method=method_full_name,
                                    error=str(e),
                                )

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
        style: DocstringStyle | None = None,
        context_elements: list[CodeElement] | None = None,
        custom_instructions: str | None = None,
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
        style: DocstringStyle | None = None,
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
            if any(
                part.startswith(".") or part == "__pycache__" for part in py_file.parts
            ):
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
            param_names = {
                p.name for p in element.parameters if p.name not in ("self", "cls")
            }
            documented_params = {
                name for name in param_names if name in docstring_content.lower()
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
        if (
            element.complexity_score
            and element.complexity_score > 10
            and len(docstring_content.split()) < 20
        ):
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

    This provider generates meaningful template-based docstrings based on
    code element metadata, useful for testing and development.
    """

    def _generate_description_from_name(self, name: str, element_type: str, parent_class: str | None = None, patterns: list[str] | None = None) -> str:
        """Generate a meaningful description based on element name and detected patterns.

        Args:
            name: Name of the code element
            element_type: Type of element (class, function, etc.)
            parent_class: Parent class name if this is a method
            patterns: Detected design patterns

        Returns:
            Generated description string
        """
        # Convert snake_case or camelCase to words
        import re

        patterns = patterns or []

        # Handle special methods first
        if name.startswith("__") and name.endswith("__"):
            parent_ref = f"the {parent_class}" if parent_class else "the instance"
            special_methods = {
                "__init__": f"Initialize {parent_ref} with required parameters",
                "__str__": f"Return string representation of {parent_ref}",
                "__repr__": f"Return detailed representation of {parent_ref}",
                "__len__": f"Return the length/count of {parent_ref}",
                "__getitem__": f"Get item from {parent_ref} by key or index",
                "__setitem__": f"Set item in {parent_ref} by key or index",
                "__delitem__": f"Delete item from {parent_ref} by key or index",
                "__contains__": f"Check if item is contained in {parent_ref}",
                "__iter__": f"Return iterator over {parent_ref}",
                "__next__": f"Return next item from {parent_ref}",
                "__enter__": f"Enter the runtime context for {parent_ref}",
                "__exit__": f"Exit the runtime context for {parent_ref}",
                "__call__": f"Make {parent_ref} callable",
                "__eq__": f"Check equality with another object",
                "__ne__": f"Check inequality with another object",
                "__lt__": f"Check if less than another object",
                "__le__": f"Check if less than or equal to another object",
                "__gt__": f"Check if greater than another object",
                "__ge__": f"Check if greater than or equal to another object",
                "__hash__": f"Return hash value of {parent_ref}",
                "__bool__": f"Return boolean value of {parent_ref}",
            }
            if name in special_methods:
                return special_methods[name]

        # Handle camelCase and PascalCase
        words = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        # Handle snake_case
        words = words.replace('_', ' ')
        # Clean up and lowercase
        words = words.strip().lower()

        # Pattern-based descriptions for classes
        if element_type == "class":
            if "singleton" in patterns:
                return f"Singleton class for managing {words}"
            elif "factory" in patterns:
                return f"Factory class for creating {words.replace('factory', '').strip()} instances"
            elif "adapter" in patterns:
                return f"Adapter class for interfacing with {words.replace('adapter', '').strip()}"
            elif "strategy" in patterns:
                return f"Strategy class implementing {words.replace('strategy', '').strip()} algorithm"
            elif "observer" in patterns:
                return f"Observer class for monitoring {words.replace('observer', '').strip()} events"
            elif "command" in patterns:
                return f"Command class for executing {words.replace('command', '').strip()} operations"
            elif "manager" in words:
                return f"Manages {words.replace('manager', '').strip()} operations and state"
            elif "handler" in words:
                return f"Handles {words.replace('handler', '').strip()} events and processing"
            elif "processor" in words:
                return f"Processes {words.replace('processor', '').strip()} data and operations"
            elif "service" in words:
                return f"Provides {words.replace('service', '').strip()} services and functionality"
            elif "client" in words:
                return f"Client for interacting with {words.replace('client', '').strip()} services"
            elif "provider" in words:
                return f"Provides {words.replace('provider', '').strip()} functionality"
            elif "builder" in words:
                return f"Builder for constructing {words.replace('builder', '').strip()} objects"
            elif "validator" in words:
                return f"Validates {words.replace('validator', '').strip()} data and constraints"
            elif "controller" in words:
                return f"Controls {words.replace('controller', '').strip()} flow and logic"
            else:
                return f"Represents a {words}"

        # Pattern-based descriptions for functions/methods
        elif element_type in ("function", "method"):
            if "factory_method" in patterns or "factory" in patterns:
                return f"Factory method for creating {words.replace('create', '').replace('make', '').replace('build', '').strip()} instances"
            elif "singleton" in patterns:
                return f"Get singleton instance of {words}"
            elif "crud_create" in patterns:
                return f"Create a new {words.replace('create', '').strip()}"
            elif "crud_read" in patterns:
                return f"Retrieve {words.replace('get', '').replace('fetch', '').replace('retrieve', '').strip()} by ID or criteria"
            elif "crud_update" in patterns:
                return f"Update existing {words.replace('update', '').replace('set', '').strip()}"
            elif "crud_delete" in patterns:
                return f"Delete {words.replace('delete', '').replace('remove', '').strip()} from storage"
            elif words.startswith("get "):
                return f"Retrieves {words[4:]}"
            elif words.startswith("set "):
                return f"Sets {words[4:]}"
            elif words.startswith("create "):
                return f"Creates a new {words[7:]}"
            elif words.startswith("delete ") or words.startswith("remove "):
                return f"Deletes {words.split(' ', 1)[1] if ' ' in words else 'the specified item'}"
            elif words.startswith("update "):
                return f"Updates {words[7:]}"
            elif words.startswith("calculate "):
                return f"Calculates {words[10:]}"
            elif words.startswith("validate "):
                return f"Validates {words[9:]}"
            elif words.startswith("parse "):
                return f"Parses {words[6:]}"
            elif words.startswith("format "):
                return f"Formats {words[7:]}"
            elif words.startswith("build "):
                return f"Builds {words[6:]}"
            elif words.startswith("process "):
                return f"Processes {words[8:]}"
            elif words.startswith("handle "):
                return f"Handles {words[7:]}"
            elif words.startswith("fetch "):
                return f"Fetches {words[6:]}"
            elif words.startswith("load "):
                return f"Loads {words[5:]}"
            elif words.startswith("save "):
                return f"Saves {words[5:]}"
            elif words.startswith("check ") or words.startswith("is ") or words.startswith("has "):
                return f"Checks if {words.split(' ', 1)[1] if ' ' in words else 'condition is met'}"
            elif words.startswith("find "):
                return f"Finds {words[5:]}"
            elif words.startswith("search "):
                return f"Searches for {words[7:]}"
            elif words.startswith("list "):
                return f"Lists all {words[5:]}"
            elif words.startswith("count "):
                return f"Counts {words[6:]}"
            elif words.startswith("sum ") or words.startswith("total "):
                return f"Calculates the total {words.split(' ', 1)[1] if ' ' in words else 'value'}"
            elif words.startswith("send "):
                return f"Sends {words[5:]}"
            elif words.startswith("receive "):
                return f"Receives {words[8:]}"
            elif words.startswith("connect "):
                return f"Establishes connection to {words[8:]}"
            elif words.startswith("disconnect "):
                return f"Closes connection to {words[11:]}"
            elif words.startswith("init") or words.startswith("initialize"):
                return "Initializes the instance with required parameters"
            else:
                return f"Performs {words} operation"

        return f"{element_type.title()} for {words}"

    def _generate_param_description(self, param_name: str, param_type: str | None) -> str:
        """Generate a description for a parameter based on its name and type.

        Args:
            param_name: Parameter name
            param_type: Parameter type hint if available

        Returns:
            Generated parameter description
        """
        import re

        # Convert to words
        words = re.sub(r'([a-z])([A-Z])', r'\1 \2', param_name)
        words = words.replace('_', ' ').strip().lower()

        # Generate type-aware descriptions
        type_lower = (param_type or "").lower()

        if "list" in type_lower or "sequence" in type_lower:
            return f"List of {words} to process"
        elif "dict" in type_lower or "mapping" in type_lower:
            return f"Dictionary containing {words} data"
        elif "str" in type_lower:
            return f"String representing {words}"
        elif "int" in type_lower:
            return f"Integer value for {words}"
        elif "float" in type_lower:
            return f"Float value for {words}"
        elif "bool" in type_lower:
            return f"Whether to {words}" if not words.startswith("is ") and not words.startswith("has ") else f"Flag indicating if {words}"
        elif "path" in type_lower or param_name.endswith("_path") or param_name.endswith("_file"):
            return f"Path to {words.replace('path', '').replace('file', '').strip() or 'file'}"
        elif param_name.endswith("_id"):
            return f"Unique identifier for {words.replace('id', '').strip()}"
        elif param_name.endswith("_name"):
            return f"Name of the {words.replace('name', '').strip()}"
        elif param_name.startswith("num_") or param_name.startswith("count_"):
            return f"Number of {words.replace('num', '').replace('count', '').strip()}"
        elif param_name.startswith("max_") or param_name.startswith("min_"):
            prefix = "Maximum" if param_name.startswith("max_") else "Minimum"
            return f"{prefix} {words.replace('max', '').replace('min', '').strip()}"
        elif param_name.endswith("_url") or param_name.endswith("_uri"):
            return f"URL for {words.replace('url', '').replace('uri', '').strip()}"
        elif param_name.endswith("_config") or param_name.endswith("_settings"):
            return f"Configuration for {words.replace('config', '').replace('settings', '').strip()}"
        else:
            return f"The {words} to use"

    def _should_include_example(self, element: CodeElement) -> bool:
        """Determine if an example should be included in the docstring.

        Args:
            element: Code element being documented

        Returns:
            True if example should be included, False otherwise
        """
        # Include examples for complex functions (complexity_score > 5)
        if element.complexity_score and element.complexity_score > 5:
            return True

        # Include examples for functions/methods with parameters (excluding self/cls)
        has_params = any(p.name not in ("self", "cls") for p in element.parameters)

        # Skip examples for special methods (except __init__)
        is_special = element.name.startswith("__") and element.name.endswith("__")
        if is_special and element.name != "__init__":
            return False

        # Skip examples for very simple property getters
        if element.is_property and not has_params:
            return False

        # Include if has parameters with type hints
        has_type_hints = any(
            p.type_hint for p in element.parameters if p.name not in ("self", "cls")
        )

        return has_params and has_type_hints

    def _generate_example(self, element: CodeElement) -> list[str]:
        """Generate example usage for a code element.

        Args:
            element: Code element to generate example for

        Returns:
            List of example lines
        """
        import re

        lines: list[str] = []

        # Get parameters excluding self/cls
        params = [p for p in element.parameters if p.name not in ("self", "cls")]

        # Build example call
        example_args = []

        for param in params:
            # Generate example values based on type
            type_lower = (param.type_hint or "").lower()

            if "str" in type_lower:
                if "url" in param.name or "uri" in param.name:
                    example_args.append(f'{param.name}="https://example.com"')
                elif "email" in param.name:
                    example_args.append(f'{param.name}="user@example.com"')
                elif "path" in param.name or "file" in param.name:
                    example_args.append(f'{param.name}="/path/to/file"')
                elif "name" in param.name:
                    example_args.append(f'{param.name}="example_{param.name}"')
                else:
                    example_args.append(f'{param.name}="value"')
            elif "int" in type_lower:
                if "id" in param.name:
                    example_args.append(f"{param.name}=123")
                elif "count" in param.name or "num" in param.name:
                    example_args.append(f"{param.name}=10")
                elif "age" in param.name:
                    example_args.append(f"{param.name}=25")
                else:
                    example_args.append(f"{param.name}=1")
            elif "float" in type_lower:
                example_args.append(f"{param.name}=1.5")
            elif "bool" in type_lower:
                example_args.append(f"{param.name}=True")
            elif "list" in type_lower:
                # Extract type from List[X]
                match = re.search(r'List\[(\w+)\]', param.type_hint or "")
                if match:
                    inner_type = match.group(1)
                    if "str" in inner_type.lower():
                        example_args.append(f'{param.name}=["item1", "item2"]')
                    elif "int" in inner_type.lower():
                        example_args.append(f"{param.name}=[1, 2, 3]")
                    elif "user" in inner_type.lower() or "item" in inner_type.lower():
                        example_args.append(f"{param.name}=[{inner_type.lower()}1, {inner_type.lower()}2]")
                    else:
                        example_args.append(f"{param.name}=[{inner_type.lower()}1, {inner_type.lower()}2]")
                else:
                    example_args.append(f"{param.name}=[]")
            elif "dict" in type_lower:
                example_args.append(f'{param.name}={{"key": "value"}}')
            else:
                # Use parameter name as placeholder
                example_args.append(f"{param.name}={param.name}")

        # Build the call
        call_args = ", ".join(example_args)

        # Determine call style (method vs function)
        if element.parent_class:
            # Method call
            instance_name = element.parent_class.lower()
            function_call = f"{instance_name}.{element.name}({call_args})"
        else:
            # Function call
            function_call = f"{element.name}({call_args})"

        # Generate appropriate example based on return type
        return_type = element.return_info.type_hint if element.return_info else None

        if return_type and return_type.lower() not in ("none", "nonetype"):
            # Show result
            result_var = "result"
            if "dict" in return_type.lower() and ("stats" in element.name or "calculate" in element.name):
                lines.append(f">>> {result_var} = {function_call}")
                lines.append(f">>> print({result_var})")
                # Extract likely dict key from function name
                words = re.sub(r'([a-z])([A-Z])', r'\1 \2', element.name)
                words = words.replace('_', ' ').strip().lower()
                if "stats" in words:
                    lines.append("{'total': 10, 'active': 8}")
                else:
                    lines.append("{'key': 'value'}")
            elif "list" in return_type.lower():
                lines.append(f">>> {result_var} = {function_call}")
                lines.append(f">>> len({result_var})")
                lines.append("2")
            elif "bool" in return_type.lower():
                lines.append(f">>> {function_call}")
                lines.append("True")
            else:
                lines.append(f">>> {result_var} = {function_call}")
                lines.append(f">>> print({result_var})")

                # Add contextual output
                if "str" in return_type.lower():
                    lines.append('"example output"')
                elif "int" in return_type.lower() or "float" in return_type.lower():
                    lines.append("42")
                else:
                    lines.append("...")
        else:
            # No return or None return
            lines.append(f">>> {function_call}")

        return lines

    def _generate_return_description(self, return_type: str, element_name: str) -> str:
        """Generate a description for return value based on type and function name.

        Args:
            return_type: Return type hint
            element_name: Name of the function/method

        Returns:
            Generated return value description
        """
        import re

        type_lower = return_type.lower()

        # Extract function action
        words = re.sub(r'([a-z])([A-Z])', r'\1 \2', element_name)
        words = words.replace('_', ' ').strip().lower()

        # Extract subject from function name
        subject = words.replace('get', '').replace('fetch', '').replace('list', '').replace('calculate', '').replace('compute', '').strip() or 'result'

        if "bool" in type_lower:
            # More context-aware bool descriptions
            if words.startswith('is ') or words.startswith('has ') or words.startswith('can '):
                return f"True if {words}, False otherwise"
            elif words.startswith('check'):
                return f"True if validation passes, False otherwise"
            elif words.startswith('validate'):
                return f"True if valid, False otherwise"
            else:
                return "True if successful, False otherwise"
        elif "list" in type_lower:
            return f"List of {subject}s" if subject and not subject.endswith('s') else f"List of {subject}"
        elif "dict" in type_lower:
            if "stats" in words or "statistics" in words:
                return f"Dictionary with {subject} statistics"
            elif "config" in words or "settings" in words:
                return f"Configuration dictionary for {subject}"
            else:
                return f"Dictionary containing {subject} data"
        elif "str" in type_lower:
            return f"String representation of {subject}"
        elif "int" in type_lower:
            if "count" in words or "number" in words or "num" in words:
                return f"Number of {subject}s"
            else:
                return f"Calculated {subject} value"
        elif "float" in type_lower:
            return f"Calculated {subject} value"
        elif "none" in type_lower:
            return "None"
        elif type_lower == "self":
            return "Self instance for method chaining"
        elif "optional" in type_lower:
            return f"The {subject} if found, None otherwise"
        else:
            return f"The {subject}"

    async def generate_docstring(self, context: DocumentationContext) -> str:
        """Generate a meaningful template-based docstring.

        Args:
            context: Documentation context

        Returns:
            Mock docstring content
        """
        element = context.element
        lines: list[str] = []

        # Generate meaningful summary based on element name, type, and detected patterns
        summary = self._generate_description_from_name(
            element.name,
            element.element_type.value,
            element.parent_class,
            element.detected_patterns
        )

        # Add async note if applicable
        if element.is_async:
            summary = f"Asynchronously {summary[0].lower()}{summary[1:]}"

        lines.append(summary + ".")

        # Parameters
        if element.parameters:
            params = [p for p in element.parameters if p.name not in ("self", "cls")]
            if params:
                lines.append("")
                lines.append("Args:")
                for param in params:
                    # Use effective_type which prioritizes explicit type hint over inferred
                    param_type = param.effective_type or "Any"
                    param_desc = self._generate_param_description(param.name, param.effective_type)

                    # Add type inference note if type was inferred
                    if param.inferred_type and not param.type_hint:
                        if param.type_inference_confidence == "high":
                            param_desc += " (inferred)"
                        elif param.type_inference_confidence == "medium":
                            param_desc += " (likely)"
                        elif param.type_inference_confidence == "low":
                            param_desc += " (guessed)"

                    # Add optional note if has default
                    if param.default_value and param.default_value != "None":
                        param_desc += f". Defaults to {param.default_value}"
                    elif not param.is_required:
                        param_desc += ". Optional"

                    lines.append(f"    {param.name} ({param_type}): {param_desc}")

        # Returns
        if element.return_info:
            # Use effective_type which prioritizes explicit type hint over inferred
            return_type = element.return_info.effective_type
            if return_type and return_type.lower() not in ("none", "nonetype"):
                lines.append("")
                lines.append("Returns:")
                return_desc = self._generate_return_description(return_type, element.name)

                # Add type inference note if type was inferred
                if element.return_info.inferred_type and not element.return_info.type_hint:
                    if element.return_info.type_inference_confidence == "high":
                        return_desc += " (inferred)"
                    elif element.return_info.type_inference_confidence == "medium":
                        return_desc += " (likely)"
                    elif element.return_info.type_inference_confidence == "low":
                        return_desc += " (guessed)"

                lines.append(f"    {return_type}: {return_desc}")

        # Raises
        if element.raises:
            lines.append("")
            lines.append("Raises:")
            for exc in element.raises:
                # Generate contextual exception descriptions
                exc_desc = f"If {element.name.replace('_', ' ')} operation fails"
                if "Value" in exc.exception_type:
                    exc_desc = "If invalid input values are provided"
                elif "Type" in exc.exception_type:
                    exc_desc = "If arguments have incorrect types"
                elif "Key" in exc.exception_type:
                    exc_desc = "If required key is not found"
                elif "File" in exc.exception_type or "IO" in exc.exception_type:
                    exc_desc = "If file operation fails"
                elif "Connection" in exc.exception_type or "Network" in exc.exception_type:
                    exc_desc = "If network connection fails"
                elif "Permission" in exc.exception_type:
                    exc_desc = "If permission is denied"
                elif "NotImplemented" in exc.exception_type:
                    exc_desc = "If method is not implemented"
                elif "Attribute" in exc.exception_type:
                    exc_desc = "If required attribute is not found"
                elif "Index" in exc.exception_type:
                    exc_desc = "If index is out of range"
                elif "Runtime" in exc.exception_type:
                    exc_desc = "If runtime error occurs"

                lines.append(f"    {exc.exception_type}: {exc_desc}")

        # Add examples when appropriate
        if context.include_examples and self._should_include_example(element):
            example_lines = self._generate_example(element)
            if example_lines:
                lines.append("")
                lines.append("Example:")
                for example_line in example_lines:
                    lines.append(f"    {example_line}")

        # Add note about detected design patterns (excluding anti-patterns)
        design_patterns = [p for p in element.detected_patterns if not p.startswith("anti_pattern_")]
        if design_patterns:
            lines.append("")
            pattern_names = ", ".join(p.replace("_", " ").title() for p in design_patterns)
            lines.append(f"Note:")
            lines.append(f"    This element implements: {pattern_names}")

        return "\n".join(lines)

    async def test_connection(self) -> bool:
        """Test connection to the mock provider.

        Returns:
            Always returns True for mock provider
        """
        return True
