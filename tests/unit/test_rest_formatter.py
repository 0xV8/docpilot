"""Unit tests for the reStructuredText (reST) formatter."""

import pytest

from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    ExceptionInfo,
    ParameterInfo,
    ReturnInfo,
)
from docpilot.formatters.rest import RestFormatter


class TestRestFormatter:
    """Tests for the RestFormatter class."""

    @pytest.fixture
    def formatter(self):
        """Create a RestFormatter instance."""
        return RestFormatter()

    @pytest.fixture
    def sample_function(self):
        """Create a sample function element."""
        return CodeElement(
            name="calculate_sum",
            element_type=CodeElementType.FUNCTION,
            lineno=1,
            source_code="def calculate_sum(a: int, b: int) -> int:\n    return a + b",
            parameters=[
                ParameterInfo(
                    name="a", type_hint="int", is_required=True, description="First number"
                ),
                ParameterInfo(
                    name="b", type_hint="int", is_required=True, description="Second number"
                ),
            ],
            return_info=ReturnInfo(type_hint="int", description="Sum of a and b"),
        )

    @pytest.fixture
    def sample_method(self):
        """Create a sample method element."""
        return CodeElement(
            name="process_data",
            element_type=CodeElementType.METHOD,
            lineno=5,
            parent_class="DataProcessor",
            source_code="def process_data(self, data: list) -> dict:\n    pass",
            parameters=[
                ParameterInfo(name="self", is_required=True),
                ParameterInfo(
                    name="data",
                    type_hint="list",
                    is_required=True,
                    description="Input data to process",
                ),
            ],
            return_info=ReturnInfo(
                type_hint="dict", description="Processed data results"
            ),
            raises=[
                ExceptionInfo(
                    exception_type="ValueError", description="If data is invalid"
                ),
            ],
        )

    def test_format_summary(self, formatter):
        """Test formatting a summary line."""
        summary = "Calculate the sum of two numbers"
        result = formatter.format_summary(summary)

        assert result == "Calculate the sum of two numbers."
        assert result.endswith(".")

    def test_format_summary_with_existing_period(self, formatter):
        """Test formatting a summary that already has a period."""
        summary = "Calculate the sum of two numbers."
        result = formatter.format_summary(summary)

        assert result == "Calculate the sum of two numbers."
        assert result.count(".") == 1

    def test_format_parameters_with_types(self, formatter):
        """Test formatting parameters with type hints."""
        parameters = [
            ParameterInfo(name="x", type_hint="int", description="First value"),
            ParameterInfo(name="y", type_hint="str", description="Second value"),
        ]
        descriptions = {"x": "First value", "y": "Second value"}

        result = formatter.format_parameters(parameters, descriptions)

        assert ":param x: First value" in result
        assert ":type x: int" in result
        assert ":param y: Second value" in result
        assert ":type y: str" in result

    def test_format_parameters_without_types(self):
        """Test formatting parameters without type hints."""
        formatter = RestFormatter(include_types=False)
        parameters = [
            ParameterInfo(name="x", type_hint="int", description="First value"),
            ParameterInfo(name="y", description="Second value"),
        ]
        descriptions = {"x": "First value", "y": "Second value"}

        result = formatter.format_parameters(parameters, descriptions)

        assert ":param x: First value" in result
        assert ":param y: Second value" in result
        assert ":type" not in result

    def test_format_parameters_skip_self_and_cls(self, formatter):
        """Test that self and cls parameters are skipped."""
        parameters = [
            ParameterInfo(name="self"),
            ParameterInfo(name="x", type_hint="int", description="Value"),
            ParameterInfo(name="cls"),
        ]
        descriptions = {"x": "Value"}

        result = formatter.format_parameters(parameters, descriptions)

        assert "self" not in result
        assert "cls" not in result
        assert ":param x: Value" in result

    def test_format_returns_with_type(self, formatter):
        """Test formatting return value with type hint."""
        result = formatter.format_returns("int", "The calculated sum")

        assert ":returns: The calculated sum" in result
        assert ":rtype: int" in result

    def test_format_returns_without_type(self):
        """Test formatting return value without type hint."""
        formatter = RestFormatter(include_types=False)
        result = formatter.format_returns(None, "The calculated sum")

        assert ":returns: The calculated sum" in result
        assert ":rtype:" not in result

    def test_format_raises(self, formatter):
        """Test formatting exception information."""
        exceptions = {
            "ValueError": "If input is invalid",
            "TypeError": "If wrong type provided",
        }

        result = formatter.format_raises(exceptions)

        assert ":raises ValueError: If input is invalid" in result
        assert ":raises TypeError: If wrong type provided" in result

    def test_format_yields(self, formatter):
        """Test formatting yields information."""
        result = formatter.format_yields("Individual items from the collection")

        assert result == ":yields: Individual items from the collection"

    def test_format_examples(self, formatter):
        """Test formatting examples section."""
        examples = 'result = calculate_sum(5, 3)\nprint(result)  # Output: 8'
        result = formatter.format_examples(examples)

        assert ".. code-block:: python" in result
        assert "result = calculate_sum(5, 3)" in result
        assert "print(result)" in result

    def test_format_notes(self, formatter):
        """Test formatting notes section."""
        notes = "This is an important note about the function"
        result = formatter.format_notes(notes)

        assert ".. note::" in result
        assert "important note" in result

    def test_format_warnings(self, formatter):
        """Test formatting warnings section."""
        warnings = "This function may be deprecated in future versions"
        result = formatter.format_warnings(warnings)

        assert ".. warning::" in result
        assert "deprecated" in result

    def test_format_complete_function(self, formatter, sample_function):
        """Test formatting a complete function docstring."""
        content = """Calculate the sum of two numbers.

Args:
    a: First number
    b: Second number

Returns:
    Sum of a and b
"""
        result = formatter.format(sample_function, content)

        # Check summary
        assert "Calculate the sum of two numbers." in result

        # Check parameters
        assert ":param a: First number" in result
        assert ":type a: int" in result
        assert ":param b: Second number" in result
        assert ":type b: int" in result

        # Check returns
        assert ":returns: Sum of a and b" in result
        assert ":rtype: int" in result

    def test_format_complete_method_with_raises(self, formatter, sample_method):
        """Test formatting a method with exceptions."""
        content = """Process input data.

Args:
    data: Input data to process

Returns:
    Processed data results

Raises:
    ValueError: If data is invalid
"""
        result = formatter.format(sample_method, content)

        # Check summary
        assert "Process input data." in result

        # Check parameters (should skip self)
        assert "self" not in result
        assert ":param data: Input data to process" in result
        assert ":type data: list" in result

        # Check returns
        assert ":returns: Processed data results" in result
        assert ":rtype: dict" in result

        # Check raises
        assert ":raises ValueError: If data is invalid" in result

    def test_format_with_separate_type_lines_disabled(self, sample_function):
        """Test formatting without separate type lines."""
        formatter = RestFormatter(separate_type_lines=False)
        content = """Calculate the sum.

Args:
    a: First number
    b: Second number
"""
        result = formatter.format(sample_function, content)

        # Should have param lines but no separate type lines
        assert ":param a: First number" in result
        assert ":param b: Second number" in result
        assert ":type a:" not in result
        assert ":type b:" not in result

    def test_clean_content_removes_extra_whitespace(self, formatter):
        """Test that clean_content removes extra whitespace."""
        content = """

Summary line.


Extra blank lines removed.


"""
        result = formatter.clean_content(content)

        # Should not start or end with blank lines
        assert not result.startswith("\n")
        assert not result.endswith("\n\n")
        assert "Summary line." in result
        assert "Extra blank lines removed." in result

    def test_wrap_text_respects_max_length(self, formatter):
        """Test that text wrapping respects max line length."""
        long_text = "This is a very long line that should be wrapped " * 5
        result = formatter.wrap_text(long_text, width=80)

        # Check that no line exceeds 80 characters
        for line in result.split("\n"):
            assert len(line) <= 80

    def test_format_generator_function(self, formatter):
        """Test formatting a generator function."""
        generator = CodeElement(
            name="generate_items",
            element_type=CodeElementType.FUNCTION,
            lineno=1,
            source_code="def generate_items():\n    yield 1",
            return_info=ReturnInfo(
                type_hint="Iterator[int]",
                description="Numbers from the sequence",
                is_generator=True,
            ),
        )

        content = """Generate a sequence of numbers.

Yields:
    Numbers from the sequence
"""
        result = formatter.format(generator, content)

        assert "Generate a sequence of numbers." in result
        assert ":yields: Numbers from the sequence" in result

    def test_format_async_function(self, formatter):
        """Test formatting an async function."""
        async_func = CodeElement(
            name="fetch_data",
            element_type=CodeElementType.FUNCTION,
            lineno=1,
            source_code="async def fetch_data(url: str) -> dict:\n    pass",
            is_async=True,
            parameters=[
                ParameterInfo(name="url", type_hint="str", description="Data source URL")
            ],
            return_info=ReturnInfo(
                type_hint="dict", description="Fetched data", is_async=True
            ),
        )

        content = """Fetch data from URL.

Args:
    url: Data source URL

Returns:
    Fetched data
"""
        result = formatter.format(async_func, content)

        assert "Fetch data from URL." in result
        assert ":param url: Data source URL" in result
        assert ":type url: str" in result
        assert ":returns: Fetched data" in result
        assert ":rtype: dict" in result

    def test_parse_raises_section(self, formatter):
        """Test parsing raises section."""
        raises_text = """ValueError: If value is invalid
TypeError: If type is wrong
KeyError: If key not found"""

        result = formatter._parse_raises_section(raises_text)

        assert result["ValueError"] == "If value is invalid"
        assert result["TypeError"] == "If type is wrong"
        assert result["KeyError"] == "If key not found"

    def test_format_with_missing_descriptions(self, formatter):
        """Test formatting when descriptions are missing."""
        parameters = [
            ParameterInfo(name="x", type_hint="int"),
            ParameterInfo(name="y", type_hint="int"),
        ]
        descriptions = {}  # No descriptions provided

        result = formatter.format_parameters(parameters, descriptions)

        # Should use default "Description needed"
        assert "Description needed" in result
        assert ":param x: Description needed" in result
        assert ":param y: Description needed" in result
