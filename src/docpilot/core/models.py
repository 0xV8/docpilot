"""Pydantic models for representing Python code elements and documentation.

This module defines the core data structures used throughout docpilot for
representing parsed code elements, their metadata, and generated documentation.
All models use Pydantic v2 for validation and serialization.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CodeElementType(str, Enum):
    """Types of Python code elements that can be documented."""

    MODULE = "module"
    CLASS = "class"
    METHOD = "method"
    FUNCTION = "function"
    PROPERTY = "property"
    ATTRIBUTE = "attribute"
    CONSTANT = "constant"


class DocstringStyle(str, Enum):
    """Supported docstring formatting styles."""

    GOOGLE = "google"
    NUMPY = "numpy"
    SPHINX = "sphinx"
    AUTO = "auto"  # Auto-detect from existing code


class ParameterInfo(BaseModel):
    """Information about a function/method parameter.

    Attributes:
        name: Parameter name
        type_hint: Type annotation as string (e.g., 'int', 'Optional[str]')
        default_value: Default value if parameter has one
        is_required: Whether parameter is required (no default)
        is_variadic: Whether parameter is *args
        is_keyword: Whether parameter is **kwargs
        description: Human-readable description (extracted or generated)
    """

    model_config = ConfigDict(frozen=True)

    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    is_required: bool = True
    is_variadic: bool = False
    is_keyword: bool = False
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that parameter name is not empty."""
        if not v or not v.strip():
            raise ValueError("Parameter name cannot be empty")
        return v.strip()


class ReturnInfo(BaseModel):
    """Information about a function/method return value.

    Attributes:
        type_hint: Return type annotation as string
        description: Human-readable description of return value
        is_generator: Whether function returns a generator
        is_async: Whether function is async (returns awaitable)
    """

    model_config = ConfigDict(frozen=True)

    type_hint: Optional[str] = None
    description: Optional[str] = None
    is_generator: bool = False
    is_async: bool = False


class ExceptionInfo(BaseModel):
    """Information about exceptions raised by a function/method.

    Attributes:
        exception_type: Exception class name (e.g., 'ValueError')
        description: When/why this exception is raised
    """

    model_config = ConfigDict(frozen=True)

    exception_type: str
    description: Optional[str] = None

    @field_validator("exception_type")
    @classmethod
    def validate_exception_type(cls, v: str) -> str:
        """Validate that exception type is not empty."""
        if not v or not v.strip():
            raise ValueError("Exception type cannot be empty")
        return v.strip()


class DecoratorInfo(BaseModel):
    """Information about a decorator applied to a code element.

    Attributes:
        name: Decorator name (e.g., 'property', 'classmethod')
        arguments: Arguments passed to decorator as strings
    """

    model_config = ConfigDict(frozen=True)

    name: str
    arguments: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that decorator name is not empty."""
        if not v or not v.strip():
            raise ValueError("Decorator name cannot be empty")
        return v.strip()


class CodeElement(BaseModel):
    """Base representation of a Python code element.

    This model captures all metadata needed to generate comprehensive
    documentation for any Python code construct.

    Attributes:
        name: Element name (function name, class name, etc.)
        element_type: Type of code element
        lineno: Line number where element is defined
        end_lineno: Line number where element definition ends
        source_code: Raw source code of the element
        docstring: Existing docstring (if any)
        file_path: Absolute path to source file
        parent_class: Parent class name for methods/nested classes
        module_path: Dotted module path (e.g., 'package.module')
        is_public: Whether element is part of public API (no leading underscore)
        is_abstract: Whether element is abstract (for classes/methods)
        is_async: Whether element is async (for functions/methods)
        is_property: Whether element is a property (for methods)
        is_classmethod: Whether element is a classmethod
        is_staticmethod: Whether element is a staticmethod
        parameters: Function/method parameters
        return_info: Return value information
        raises: Exceptions that can be raised
        decorators: Applied decorators
        base_classes: Base classes (for classes)
        attributes: Class/module attributes
        complexity_score: Cyclomatic complexity (if calculated)
        metadata: Additional metadata for extensibility
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core identification
    name: str
    element_type: CodeElementType
    lineno: int
    end_lineno: Optional[int] = None
    source_code: str
    docstring: Optional[str] = None
    file_path: str
    parent_class: Optional[str] = None
    module_path: str

    # Visibility and modifiers
    is_public: bool = True
    is_abstract: bool = False
    is_async: bool = False
    is_property: bool = False
    is_classmethod: bool = False
    is_staticmethod: bool = False

    # Function/Method specific
    parameters: list[ParameterInfo] = Field(default_factory=list)
    return_info: Optional[ReturnInfo] = None
    raises: list[ExceptionInfo] = Field(default_factory=list)
    decorators: list[DecoratorInfo] = Field(default_factory=list)

    # Class specific
    base_classes: list[str] = Field(default_factory=list)
    attributes: list[tuple[str, Optional[str]]] = Field(default_factory=list)

    # Analysis metadata
    complexity_score: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that element name is not empty."""
        if not v or not v.strip():
            raise ValueError("Element name cannot be empty")
        return v.strip()

    @field_validator("lineno")
    @classmethod
    def validate_lineno(cls, v: int) -> int:
        """Validate that line number is positive."""
        if v < 1:
            raise ValueError("Line number must be positive")
        return v

    @property
    def full_name(self) -> str:
        """Get fully qualified name including module and parent class."""
        parts = [self.module_path]
        if self.parent_class:
            parts.append(self.parent_class)
        parts.append(self.name)
        return ".".join(parts)

    @property
    def has_parameters(self) -> bool:
        """Check if element has parameters (excluding self/cls)."""
        return bool(
            [p for p in self.parameters if p.name not in ("self", "cls")]
        )

    @property
    def has_docstring(self) -> bool:
        """Check if element has an existing docstring."""
        return bool(self.docstring and self.docstring.strip())

    def get_decorator(self, name: str) -> Optional[DecoratorInfo]:
        """Get decorator by name if it exists.

        Args:
            name: Decorator name to search for

        Returns:
            DecoratorInfo if found, None otherwise
        """
        for decorator in self.decorators:
            if decorator.name == name:
                return decorator
        return None


class DocumentationContext(BaseModel):
    """Context information for documentation generation.

    This model provides additional context that LLMs can use to generate
    more accurate and helpful documentation.

    Attributes:
        element: The code element to document
        style: Desired docstring style
        project_name: Name of the project
        project_description: Brief project description
        include_examples: Whether to include usage examples
        include_type_hints: Whether to include type information
        infer_types: Whether to infer types from usage if not annotated
        max_line_length: Maximum line length for formatting
        context_elements: Related code elements for context
        custom_instructions: Additional instructions for generation
    """

    element: CodeElement
    style: DocstringStyle = DocstringStyle.GOOGLE
    project_name: Optional[str] = None
    project_description: Optional[str] = None
    include_examples: bool = True
    include_type_hints: bool = True
    infer_types: bool = True
    max_line_length: int = 88
    context_elements: list[CodeElement] = Field(default_factory=list)
    custom_instructions: Optional[str] = None


class GeneratedDocstring(BaseModel):
    """Result of docstring generation.

    Attributes:
        element_name: Name of documented element
        element_type: Type of documented element
        docstring: Generated docstring content
        style: Style used for generation
        confidence_score: Confidence in generation quality (0.0-1.0)
        warnings: Any warnings about the generation
        metadata: Additional generation metadata
    """

    element_name: str
    element_type: CodeElementType
    docstring: str
    style: DocstringStyle
    confidence_score: float = Field(ge=0.0, le=1.0, default=1.0)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("docstring")
    @classmethod
    def validate_docstring(cls, v: str) -> str:
        """Validate that docstring is not empty."""
        if not v or not v.strip():
            raise ValueError("Generated docstring cannot be empty")
        return v


class ParseResult(BaseModel):
    """Result of parsing a Python file.

    Attributes:
        file_path: Path to parsed file
        module_path: Dotted module path
        elements: All code elements found in file
        parse_errors: Any errors encountered during parsing
        encoding: File encoding
        total_lines: Total lines in file
        code_lines: Non-comment, non-blank lines
    """

    file_path: str
    module_path: str
    elements: list[CodeElement] = Field(default_factory=list)
    parse_errors: list[str] = Field(default_factory=list)
    encoding: str = "utf-8"
    total_lines: int = 0
    code_lines: int = 0

    @property
    def has_errors(self) -> bool:
        """Check if parsing encountered any errors."""
        return bool(self.parse_errors)

    @property
    def public_elements(self) -> list[CodeElement]:
        """Get only public code elements."""
        return [elem for elem in self.elements if elem.is_public]

    def get_elements_by_type(
        self, element_type: CodeElementType
    ) -> list[CodeElement]:
        """Get all elements of a specific type.

        Args:
            element_type: Type of elements to retrieve

        Returns:
            List of matching code elements
        """
        return [elem for elem in self.elements if elem.element_type == element_type]
