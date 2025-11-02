"""Unit tests for MockLLMProvider improvements."""

import pytest

from docpilot.core.generator import MockLLMProvider
from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    DocumentationContext,
    DocstringStyle,
    ExceptionInfo,
    ParameterInfo,
    ReturnInfo,
)


class TestMockProviderDescriptions:
    """Test that MockLLMProvider generates meaningful descriptions."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a mock provider instance."""
        return MockLLMProvider()

    @pytest.mark.asyncio
    async def test_class_docstring_not_generic(self, provider: MockLLMProvider) -> None:
        """Test that class docstrings are meaningful, not just 'Class User.'"""
        element = CodeElement(
            name="User",
            element_type=CodeElementType.CLASS,
            source_code="class User:\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        # Should not be just "Class User."
        assert docstring != "Class User."
        assert docstring.lower() != "class user."
        # Should have meaningful content
        assert "represents a user" in docstring.lower() or "user" in docstring.lower()
        assert len(docstring.split()) >= 3

    @pytest.mark.asyncio
    async def test_class_manager_pattern(self, provider: MockLLMProvider) -> None:
        """Test that manager classes get appropriate descriptions."""
        element = CodeElement(
            name="UserManager",
            element_type=CodeElementType.CLASS,
            source_code="class UserManager:\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "manages" in docstring.lower()
        assert "user" in docstring.lower()

    @pytest.mark.asyncio
    async def test_class_handler_pattern(self, provider: MockLLMProvider) -> None:
        """Test that handler classes get appropriate descriptions."""
        element = CodeElement(
            name="EventHandler",
            element_type=CodeElementType.CLASS,
            source_code="class EventHandler:\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "handles" in docstring.lower()
        assert "event" in docstring.lower()

    @pytest.mark.asyncio
    async def test_class_provider_pattern(self, provider: MockLLMProvider) -> None:
        """Test that provider classes get appropriate descriptions."""
        element = CodeElement(
            name="DataProvider",
            element_type=CodeElementType.CLASS,
            source_code="class DataProvider:\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "provides" in docstring.lower()
        assert "data" in docstring.lower()


class TestMockProviderFunctionDescriptions:
    """Test function description generation."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a mock provider instance."""
        return MockLLMProvider()

    @pytest.mark.asyncio
    async def test_get_function_description(self, provider: MockLLMProvider) -> None:
        """Test that get_* functions have proper descriptions."""
        element = CodeElement(
            name="get_user_data",
            element_type=CodeElementType.FUNCTION,
            source_code="def get_user_data():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "retrieves" in docstring.lower()
        assert "user data" in docstring.lower()

    @pytest.mark.asyncio
    async def test_create_function_description(self, provider: MockLLMProvider) -> None:
        """Test that create_* functions have proper descriptions."""
        element = CodeElement(
            name="create_user",
            element_type=CodeElementType.FUNCTION,
            source_code="def create_user():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "creates" in docstring.lower()
        assert "user" in docstring.lower()

    @pytest.mark.asyncio
    async def test_validate_function_description(self, provider: MockLLMProvider) -> None:
        """Test that validate_* functions have proper descriptions."""
        element = CodeElement(
            name="validate_email",
            element_type=CodeElementType.FUNCTION,
            source_code="def validate_email():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "validates" in docstring.lower()
        assert "email" in docstring.lower()

    @pytest.mark.asyncio
    async def test_async_function_description(self, provider: MockLLMProvider) -> None:
        """Test that async functions get 'Asynchronously' prefix."""
        element = CodeElement(
            name="fetch_data",
            element_type=CodeElementType.FUNCTION,
            source_code="async def fetch_data():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            is_async=True,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "asynchronously" in docstring.lower()
        assert "fetches" in docstring.lower()


class TestMockProviderParameterDescriptions:
    """Test parameter description generation with types."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a mock provider instance."""
        return MockLLMProvider()

    @pytest.mark.asyncio
    async def test_parameter_with_string_type(self, provider: MockLLMProvider) -> None:
        """Test that string parameters get type-aware descriptions."""
        element = CodeElement(
            name="process_name",
            element_type=CodeElementType.FUNCTION,
            source_code="def process_name(user_name: str):\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            parameters=[
                ParameterInfo(name="user_name", type_hint="str", is_required=True)
            ],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        # Should include type in description
        assert "str" in docstring
        assert "user_name" in docstring.lower()
        assert "string" in docstring.lower()

    @pytest.mark.asyncio
    async def test_parameter_with_list_type(self, provider: MockLLMProvider) -> None:
        """Test that list parameters get type-aware descriptions."""
        element = CodeElement(
            name="process_items",
            element_type=CodeElementType.FUNCTION,
            source_code="def process_items(items: list[str]):\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            parameters=[
                ParameterInfo(name="items", type_hint="list[str]", is_required=True)
            ],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "list[str]" in docstring
        assert "items" in docstring.lower()
        assert "list of" in docstring.lower()

    @pytest.mark.asyncio
    async def test_parameter_with_dict_type(self, provider: MockLLMProvider) -> None:
        """Test that dict parameters get type-aware descriptions."""
        element = CodeElement(
            name="process_config",
            element_type=CodeElementType.FUNCTION,
            source_code="def process_config(config: dict):\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            parameters=[
                ParameterInfo(name="config", type_hint="dict", is_required=True)
            ],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "dict" in docstring
        assert "config" in docstring.lower()
        assert "dictionary" in docstring.lower()

    @pytest.mark.asyncio
    async def test_parameter_with_bool_type(self, provider: MockLLMProvider) -> None:
        """Test that bool parameters get type-aware descriptions."""
        element = CodeElement(
            name="set_active",
            element_type=CodeElementType.FUNCTION,
            source_code="def set_active(is_active: bool):\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            parameters=[
                ParameterInfo(name="is_active", type_hint="bool", is_required=True)
            ],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "bool" in docstring
        assert "is_active" in docstring.lower()
        # Should have contextual description for boolean
        assert "whether" in docstring.lower() or "flag" in docstring.lower()

    @pytest.mark.asyncio
    async def test_parameter_with_path_type(self, provider: MockLLMProvider) -> None:
        """Test that path parameters get appropriate descriptions."""
        element = CodeElement(
            name="load_file",
            element_type=CodeElementType.FUNCTION,
            source_code="def load_file(file_path: Path):\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            parameters=[
                ParameterInfo(name="file_path", type_hint="Path", is_required=True)
            ],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "Path" in docstring
        assert "file_path" in docstring.lower()
        assert "path to" in docstring.lower()

    @pytest.mark.asyncio
    async def test_parameter_with_default_value(self, provider: MockLLMProvider) -> None:
        """Test that parameters with defaults mention the default value."""
        element = CodeElement(
            name="connect",
            element_type=CodeElementType.FUNCTION,
            source_code="def connect(timeout: int = 30):\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            parameters=[
                ParameterInfo(
                    name="timeout",
                    type_hint="int",
                    is_required=False,
                    default_value="30",
                )
            ],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "timeout" in docstring.lower()
        assert "defaults to 30" in docstring.lower() or "default" in docstring.lower()


class TestMockProviderReturnDescriptions:
    """Test return value description generation."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a mock provider instance."""
        return MockLLMProvider()

    @pytest.mark.asyncio
    async def test_return_bool_description(self, provider: MockLLMProvider) -> None:
        """Test that bool returns get contextual descriptions."""
        element = CodeElement(
            name="is_valid",
            element_type=CodeElementType.FUNCTION,
            source_code="def is_valid() -> bool:\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            return_info=ReturnInfo(type_hint="bool"),
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "Returns:" in docstring
        assert "bool" in docstring
        assert "true if" in docstring.lower() or "false" in docstring.lower()

    @pytest.mark.asyncio
    async def test_return_list_description(self, provider: MockLLMProvider) -> None:
        """Test that list returns get contextual descriptions."""
        element = CodeElement(
            name="get_users",
            element_type=CodeElementType.FUNCTION,
            source_code="def get_users() -> list[User]:\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            return_info=ReturnInfo(type_hint="list[User]"),
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "Returns:" in docstring
        assert "list[User]" in docstring
        assert "list of" in docstring.lower()

    @pytest.mark.asyncio
    async def test_return_dict_description(self, provider: MockLLMProvider) -> None:
        """Test that dict returns get contextual descriptions."""
        element = CodeElement(
            name="get_config",
            element_type=CodeElementType.FUNCTION,
            source_code="def get_config() -> dict:\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            return_info=ReturnInfo(type_hint="dict"),
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "Returns:" in docstring
        assert "dict" in docstring
        assert "dictionary" in docstring.lower() or "containing" in docstring.lower()

    @pytest.mark.asyncio
    async def test_no_return_section_for_none(self, provider: MockLLMProvider) -> None:
        """Test that None returns don't generate a Returns section."""
        element = CodeElement(
            name="process_data",
            element_type=CodeElementType.FUNCTION,
            source_code="def process_data() -> None:\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            return_info=ReturnInfo(type_hint="None"),
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        # Should not have Returns section for None
        assert "Returns:" not in docstring


class TestMockProviderExceptionDescriptions:
    """Test exception description generation."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a mock provider instance."""
        return MockLLMProvider()

    @pytest.mark.asyncio
    async def test_value_error_description(self, provider: MockLLMProvider) -> None:
        """Test that ValueError gets contextual description."""
        element = CodeElement(
            name="validate_input",
            element_type=CodeElementType.FUNCTION,
            source_code="def validate_input():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            raises=[ExceptionInfo(exception_type="ValueError")],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "Raises:" in docstring
        assert "ValueError" in docstring
        assert "invalid" in docstring.lower()

    @pytest.mark.asyncio
    async def test_file_error_description(self, provider: MockLLMProvider) -> None:
        """Test that FileNotFoundError gets contextual description."""
        element = CodeElement(
            name="load_file",
            element_type=CodeElementType.FUNCTION,
            source_code="def load_file():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            raises=[ExceptionInfo(exception_type="FileNotFoundError")],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "Raises:" in docstring
        assert "FileNotFoundError" in docstring
        assert "file" in docstring.lower()

    @pytest.mark.asyncio
    async def test_connection_error_description(self, provider: MockLLMProvider) -> None:
        """Test that ConnectionError gets contextual description."""
        element = CodeElement(
            name="connect_to_server",
            element_type=CodeElementType.FUNCTION,
            source_code="def connect_to_server():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            raises=[ExceptionInfo(exception_type="ConnectionError")],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "Raises:" in docstring
        assert "ConnectionError" in docstring
        assert "connection" in docstring.lower() or "network" in docstring.lower()


class TestMockProviderEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a mock provider instance."""
        return MockLLMProvider()

    @pytest.mark.asyncio
    async def test_complex_function_with_example(self, provider: MockLLMProvider) -> None:
        """Test that complex functions include example placeholders."""
        element = CodeElement(
            name="complex_calculation",
            element_type=CodeElementType.FUNCTION,
            source_code="def complex_calculation():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            complexity_score=8,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
            include_examples=True,
        )

        docstring = await provider.generate_docstring(context)

        assert "Example:" in docstring

    @pytest.mark.asyncio
    async def test_camel_case_conversion(self, provider: MockLLMProvider) -> None:
        """Test that camelCase names are converted to readable descriptions."""
        element = CodeElement(
            name="getUserData",
            element_type=CodeElementType.FUNCTION,
            source_code="def getUserData():\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        # Should convert camelCase to separate words
        assert "user" in docstring.lower()
        assert "data" in docstring.lower()

    @pytest.mark.asyncio
    async def test_multiple_parameters_all_documented(self, provider: MockLLMProvider) -> None:
        """Test that all parameters are documented with types."""
        element = CodeElement(
            name="create_user",
            element_type=CodeElementType.FUNCTION,
            source_code="def create_user(name: str, age: int, active: bool = True):\n    pass",
            lineno=1,
            file_path="test.py",
            module_path="test",
            end_lineno=2,
            parameters=[
                ParameterInfo(name="name", type_hint="str", is_required=True),
                ParameterInfo(name="age", type_hint="int", is_required=True),
                ParameterInfo(
                    name="active",
                    type_hint="bool",
                    is_required=False,
                    default_value="True",
                ),
            ],
        )
        context = DocumentationContext(
            element=element,
            style=DocstringStyle.GOOGLE,
        )

        docstring = await provider.generate_docstring(context)

        assert "Args:" in docstring
        assert "name (str):" in docstring
        assert "age (int):" in docstring
        assert "active (bool):" in docstring
        assert "Defaults to True" in docstring or "defaults to true" in docstring.lower()

    @pytest.mark.asyncio
    async def test_test_connection_returns_true(self, provider: MockLLMProvider) -> None:
        """Test that test_connection always returns True."""
        result = await provider.test_connection()
        assert result is True
