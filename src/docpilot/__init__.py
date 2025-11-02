"""docpilot - AI-powered documentation autopilot for Python projects."""

__version__ = "0.1.0"
__author__ = "docpilot contributors"
__license__ = "MIT"

from docpilot.core.parser import PythonParser
from docpilot.core.analyzer import CodeAnalyzer
from docpilot.core.generator import DocstringGenerator
from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    DocstringStyle,
    GeneratedDocstring,
    ParseResult,
)

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "PythonParser",
    "CodeAnalyzer",
    "DocstringGenerator",
    "CodeElement",
    "CodeElementType",
    "DocstringStyle",
    "GeneratedDocstring",
    "ParseResult",
]
