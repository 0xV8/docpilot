"""Core functionality for code parsing, analysis, and docstring generation."""

from docpilot.core.parser import PythonParser, parse_file
from docpilot.core.analyzer import CodeAnalyzer, analyze_file, analyze_element
from docpilot.core.generator import DocstringGenerator, MockLLMProvider
from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    DocstringStyle,
    ParameterInfo,
    ReturnInfo,
    ExceptionInfo,
    DecoratorInfo,
    DocumentationContext,
    GeneratedDocstring,
    ParseResult,
)

__all__ = [
    "PythonParser",
    "parse_file",
    "CodeAnalyzer",
    "analyze_file",
    "analyze_element",
    "DocstringGenerator",
    "MockLLMProvider",
    "CodeElement",
    "CodeElementType",
    "DocstringStyle",
    "ParameterInfo",
    "ReturnInfo",
    "ExceptionInfo",
    "DecoratorInfo",
    "DocumentationContext",
    "GeneratedDocstring",
    "ParseResult",
]
