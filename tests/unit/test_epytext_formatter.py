"""Unit tests for the Epytext formatter."""

import pytest

from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    ExceptionInfo,
    ParameterInfo,
    ReturnInfo,
)
from docpilot.formatters.epytext import EpytextFormatter


class TestEpytextFormatter:
    """Tests for the EpytextFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create an EpytextFormatter instance."""
        return EpytextFormatter()

    @pytest.fixture
    def sample_function(self):
        """Create a sample function element."""
        return CodeElement(
            name="multiply",
            element_type=CodeElementType.FUNCTION,
            lineno=1,
            source_code="def multiply(x: int, y: int) -> int:\n    return x * y",
            parameters=[
                ParameterInfo(
                    name="x", type_hint="int", is_required=True, description="First factor"
                ),
                ParameterInfo(
                    name="y",
                    type_hint="int",
                    is_required=True,
                    description="Second factor",
                ),
            ],
            return_info=ReturnInfo(type_hint="int", description="Product of x and y"),
        )

    @pytest.fixture
    def sample_class_method(self):
        """Create a sample class method element."""
        return CodeElement(
            name="validate",
            element_type=CodeElementType.METHOD,
            lineno=10,
            parent_class="Validator",
            source_code="def validate(self, input: str) -> bool:\n    pass",
            parameters=[
                ParameterInfo(name="self", is_required=True),
                ParameterInfo(
                    name="input",
                    type_hint="str",
                    is_required=True,
                    description="String to validate",
                ),
            ],
            return_info=ReturnInfo(
                type_hint="bool", description="True if valid, False otherwise"
            ),
            raises=[
                ExceptionInfo(
                    exception_type="ValueError", description="If input is empty"
                ),
                ExceptionInfo(
                    exception_type="TypeError", description="If input is not a string"
                ),
            ],
        )

    def test_format_summary(self, formatter):
        """Test formatting a summary line."""
        summary = "Multiply two numbers together"
        result = formatter.format_summary(summary)

        assert result == "Multiply two numbers together."
        assert result.endswith(".")

    def test_format_summary_preserves_existing_punctuation(self, formatter):
        """Test that existing punctuation is preserved."""
        summary = "Multiply two numbers!"
        result = formatter.format_summary(summary)

        assert result == "Multiply two numbers!"
        assert not result.endswith(".!")

    def test_format_parameters_with_types(self, formatter):
        """Test formatting parameters with type hints."""
        parameters = [
            ParameterInfo(name="name", type_hint="str", description="User's name"),
            ParameterInfo(name="age", type_hint="int", description="User's age"),
        ]
        descriptions = {"name": "User's name", "age": "User's age"}

        result = formatter.format_parameters(parameters, descriptions)

        assert "@param name: User's name" in result
        assert "@type name: str" in result
        assert "@param age: User's age" in result
        assert "@type age: int" in result

    def test_format_parameters_without_types(self):
        """Test formatting parameters without type information."""
        formatter = EpytextFormatter(include_types=False)
        parameters = [
            ParameterInfo(name="value", type_hint="int", description="Input value"),
        ]
        descriptions = {"value": "Input value"}

        result = formatter.format_parameters(parameters, descriptions)

        assert "@param value: Input value" in result
        assert "@type" not in result

    def test_format_parameters_skip_self_and_cls(self, formatter):
        """Test that self and cls parameters are excluded."""
        parameters = [
            ParameterInfo(name="self"),
            ParameterInfo(name="data", type_hint="dict", description="Data to process"),
            ParameterInfo(name="cls"),
        ]
        descriptions = {"data": "Data to process"}

        result = formatter.format_parameters(parameters, descriptions)

        assert "self" not in result
        assert "cls" not in result
        assert "@param data: Data to process" in result

    def test_format_returns_with_type(self, formatter):
        """Test formatting return value with type hint."""
        result = formatter.format_returns("bool", "True if successful")

        assert "@return: True if successful" in result
        assert "@rtype: bool" in result

    def test_format_returns_without_type(self):
        """Test formatting return value without type hint."""
        formatter = EpytextFormatter(include_types=False)
        result = formatter.format_returns(None, "Status of operation")

        assert "@return: Status of operation" in result
        assert "@rtype:" not in result

    def test_format_raises(self, formatter):
        """Test formatting exception information."""
        exceptions = {
            "ValueError": "When value is out of range",
            "KeyError": "When key is not found",
        }

        result = formatter.format_raises(exceptions)

        # Note: Epytext uses @raise (singular) not @raises
        assert "@raise ValueError: When value is out of range" in result
        assert "@raise KeyError: When key is not found" in result

    def test_format_yields(self, formatter):
        """Test formatting yields information."""
        result = formatter.format_yields("Items from the generator")

        # Note: Epytext uses @yield not @yields
        assert result == "@yield: Items from the generator"

    def test_format_examples(self, formatter):
        """Test formatting examples section."""
        examples = 'result = multiply(4, 5)\nprint(result)  # 20'
        result = formatter.format_examples(examples)

        assert "@example:" in result
        assert "result = multiply(4, 5)" in result
        assert "print(result)" in result

    def test_format_notes(self, formatter):
        """Test formatting notes section."""
        notes = "This function uses memoization for performance"
        result = formatter.format_notes(notes)

        assert "@note:" in result
        assert "memoization" in result

    def test_format_warnings(self, formatter):
        """Test formatting warnings section."""
        warnings = "This API may change in future releases"
        result = formatter.format_warnings(warnings)

        assert "@warning:" in result
        assert "may change" in result

    def test_format_complete_function(self, formatter, sample_function):
        """Test formatting a complete function docstring."""
        content = """Multiply two integers.

Args:
    x: First factor
    y: Second factor

Returns:
    Product of x and y
"""
        result = formatter.format(sample_function, content)

        # Check summary
        assert "Multiply two integers." in result

        # Check parameters
        assert "@param x: First factor" in result
        assert "@type x: int" in result
        assert "@param y: Second factor" in result
        assert "@type y: int" in result

        # Check returns
        assert "@return: Product of x and y" in result
        assert "@rtype: int" in result

    def test_format_method_with_exceptions(self, formatter, sample_class_method):
        """Test formatting a method with exception information."""
        content = """Validate input string.

Args:
    input: String to validate

Returns:
    True if valid, False otherwise

Raises:
    ValueError: If input is empty
    TypeError: If input is not a string
"""
        result = formatter.format(sample_class_method, content)

        # Check summary
        assert "Validate input string." in result

        # Check parameters (should skip self)
        assert "self" not in result
        assert "@param input: String to validate" in result
        assert "@type input: str" in result

        # Check returns
        assert "@return: True if valid, False otherwise" in result
        assert "@rtype: bool" in result

        # Check raises
        assert "@raise ValueError: If input is empty" in result
        assert "@raise TypeError: If input is not a string" in result

    def test_format_with_separate_type_lines_disabled(self, sample_function):
        """Test formatting without separate type lines."""
        formatter = EpytextFormatter(separate_type_lines=False)
        content = """Multiply two numbers.

Args:
    x: First factor
    y: Second factor
"""
        result = formatter.format(sample_function, content)

        # Should have param tags but no separate type tags
        assert "@param x: First factor" in result
        assert "@param y: Second factor" in result
        assert "@type x:" not in result
        assert "@type y:" not in result

    def test_clean_content_normalizes_whitespace(self, formatter):
        """Test that clean_content normalizes whitespace."""
        content = """


Summary with extra blank lines.



Description paragraph.


"""
        result = formatter.clean_content(content)

        # Should not start or end with blank lines
        assert not result.startswith("\n")
        assert not result.endswith("\n\n")

    def test_format_generator_function(self, formatter):
        """Test formatting a generator function."""
        generator = CodeElement(
            name="item_generator",
            element_type=CodeElementType.FUNCTION,
            lineno=1,
            source_code="def item_generator():\n    yield item",
            return_info=ReturnInfo(
                type_hint="Generator[Item]",
                description="Stream of items",
                is_generator=True,
            ),
        )

        content = """Generate items one by one.

Yields:
    Stream of items
"""
        result = formatter.format(generator, content)

        assert "Generate items one by one." in result
        assert "@yield: Stream of items" in result

    def test_format_async_method(self, formatter):
        """Test formatting an async method."""
        async_method = CodeElement(
            name="fetch_user",
            element_type=CodeElementType.METHOD,
            lineno=5,
            parent_class="UserService",
            source_code="async def fetch_user(self, user_id: int) -> User:\n    pass",
            is_async=True,
            parameters=[
                ParameterInfo(name="self", is_required=True),
                ParameterInfo(
                    name="user_id", type_hint="int", description="ID of user to fetch"
                ),
            ],
            return_info=ReturnInfo(
                type_hint="User", description="User object", is_async=True
            ),
        )

        content = """Fetch user by ID.

Args:
    user_id: ID of user to fetch

Returns:
    User object
"""
        result = formatter.format(async_method, content)

        assert "Fetch user by ID." in result
        assert "@param user_id: ID of user to fetch" in result
        assert "@type user_id: int" in result
        assert "@return: User object" in result
        assert "@rtype: User" in result

    def test_parse_raises_section(self, formatter):
        """Test parsing the raises section."""
        raises_text = """RuntimeError: If operation fails
ConnectionError: If network is unavailable
TimeoutError: If request times out"""

        result = formatter._parse_raises_section(raises_text)

        assert result["RuntimeError"] == "If operation fails"
        assert result["ConnectionError"] == "If network is unavailable"
        assert result["TimeoutError"] == "If request times out"

    def test_format_with_default_descriptions(self, formatter):
        """Test that default descriptions are used when missing."""
        parameters = [
            ParameterInfo(name="arg1", type_hint="str"),
            ParameterInfo(name="arg2", type_hint="int"),
        ]
        descriptions = {}  # Empty descriptions

        result = formatter.format_parameters(parameters, descriptions)

        # Should use "Description needed" for missing descriptions
        assert "Description needed" in result

    def test_format_complex_types(self, formatter):
        """Test formatting with complex type hints."""
        parameters = [
            ParameterInfo(
                name="items",
                type_hint="List[Dict[str, Any]]",
                description="List of configuration dictionaries",
            ),
            ParameterInfo(
                name="callback",
                type_hint="Optional[Callable[[int], None]]",
                description="Optional callback function",
            ),
        ]
        descriptions = {
            "items": "List of configuration dictionaries",
            "callback": "Optional callback function",
        }

        result = formatter.format_parameters(parameters, descriptions)

        assert "@param items: List of configuration dictionaries" in result
        assert "@type items: List[Dict[str, Any]]" in result
        assert "@param callback: Optional callback function" in result
        assert "@type callback: Optional[Callable[[int], None]]" in result

    def test_format_property_method(self, formatter):
        """Test formatting a property method."""
        property_method = CodeElement(
            name="value",
            element_type=CodeElementType.PROPERTY,
            lineno=1,
            source_code="@property\ndef value(self) -> int:\n    return self._value",
            is_property=True,
            parameters=[ParameterInfo(name="self")],
            return_info=ReturnInfo(type_hint="int", description="The current value"),
        )

        content = """Get the current value.

Returns:
    The current value
"""
        result = formatter.format(property_method, content)

        assert "Get the current value." in result
        assert "@return: The current value" in result
        assert "@rtype: int" in result
        # Should not include self parameter
        assert "@param self" not in result

    def test_format_with_multiline_descriptions(self, formatter):
        """Test formatting with multiline parameter descriptions."""
        parameters = [
            ParameterInfo(
                name="config",
                type_hint="dict",
                description="Configuration dictionary",
            ),
        ]
        descriptions = {
            "config": """Configuration dictionary containing settings.
This includes database credentials, API keys, and feature flags."""
        }

        result = formatter.format_parameters(parameters, descriptions)

        assert "@param config:" in result
        assert "Configuration dictionary" in result

    def test_format_empty_content(self, formatter, sample_function):
        """Test formatting with minimal content."""
        content = "Multiply two numbers"

        result = formatter.format(sample_function, content)

        # Should still have basic structure
        assert "Multiply two numbers." in result
        # Should include parameters from element
        assert "@param x:" in result
        assert "@param y:" in result

    def test_wrap_text_respects_max_length(self, formatter):
        """Test that text wrapping respects maximum line length."""
        long_text = "This is a really long description that needs wrapping " * 10
        result = formatter.wrap_text(long_text, width=80)

        # Each line should be <= 80 characters
        for line in result.split("\n"):
            assert len(line) <= 80

    def test_format_with_all_sections(self, formatter):
        """Test formatting with all possible sections."""
        complex_function = CodeElement(
            name="complex_operation",
            element_type=CodeElementType.FUNCTION,
            lineno=1,
            source_code="def complex_operation(data: dict) -> Result:\n    pass",
            parameters=[
                ParameterInfo(
                    name="data", type_hint="dict", description="Input data"
                ),
            ],
            return_info=ReturnInfo(
                type_hint="Result", description="Operation result"
            ),
            raises=[
                ExceptionInfo(
                    exception_type="ValueError", description="If data is invalid"
                ),
            ],
        )

        content = """Perform a complex operation.

This is a detailed description of what the operation does.

Args:
    data: Input data

Returns:
    Operation result

Raises:
    ValueError: If data is invalid

Examples:
    result = complex_operation({"key": "value"})

Notes:
    This operation is expensive

Warnings:
    Use with caution in production
"""
        result = formatter.format(complex_function, content)

        assert "Perform a complex operation." in result
        assert "@param data: Input data" in result
        assert "@return: Operation result" in result
        assert "@raise ValueError: If data is invalid" in result
        assert "@example:" in result
        assert "@note:" in result
        assert "@warning:" in result
