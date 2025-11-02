"""Unit tests for the code parser."""

import pytest

from docpilot.core.models import CodeElementType
from docpilot.core.parser import PythonParser


class TestPythonParser:
    """Tests for the PythonParser class."""

    def test_parse_simple_function(self):
        """Test parsing a simple function."""
        code = """
def add(x: int, y: int) -> int:
    '''Add two numbers.'''
    return x + y
"""
        parser = PythonParser()
        result = parser.parse_string(code)

        assert len(result.elements) == 1
        func = result.elements[0]
        assert func.name == "add"
        assert func.element_type == CodeElementType.FUNCTION
        assert len(func.parameters) == 2
        assert func.return_type == "int"

    def test_parse_class_with_methods(self):
        """Test parsing a class with methods."""
        code = """
class Calculator:
    '''A simple calculator.'''

    def add(self, x: int, y: int) -> int:
        '''Add two numbers.'''
        return x + y
"""
        parser = PythonParser()
        result = parser.parse_string(code)

        assert len(result.elements) == 1
        cls = result.elements[0]
        assert cls.name == "Calculator"
        assert cls.element_type == CodeElementType.CLASS
        assert len(cls.methods) == 1
        assert cls.methods[0].name == "add"

    def test_parse_async_function(self):
        """Test parsing an async function."""
        code = """
async def fetch_data(url: str) -> dict:
    '''Fetch data from URL.'''
    return {}
"""
        parser = PythonParser()
        result = parser.parse_string(code)

        assert len(result.elements) == 1
        func = result.elements[0]
        assert func.name == "fetch_data"
        assert func.is_async is True

    def test_parse_with_decorators(self):
        """Test parsing functions with decorators."""
        code = """
@property
@cache
def get_value(self) -> int:
    '''Get cached value.'''
    return 42
"""
        parser = PythonParser()
        result = parser.parse_string(code)

        assert len(result.elements) == 1
        func = result.elements[0]
        assert len(func.decorators) == 2
        assert any(d.name == "property" for d in func.decorators)
        assert any(d.name == "cache" for d in func.decorators)

    def test_parse_file(self, sample_python_file):
        """Test parsing a Python file."""
        parser = PythonParser()
        result = parser.parse_file(sample_python_file)

        assert str(result.file_path) == str(sample_python_file)
        assert len(result.elements) > 0

    def test_parse_invalid_syntax(self):
        """Test parsing code with invalid syntax."""
        code = "def invalid syntax here"
        parser = PythonParser()

        with pytest.raises(SyntaxError):
            parser.parse_string(code)
