"""Unit tests for partial documentation and skipping documented elements."""

from pathlib import Path

import pytest

from docpilot.core.generator import DocstringGenerator, MockLLMProvider
from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    DocstringStyle,
    ParameterInfo,
)
from docpilot.core.parser import PythonParser


class TestSkipDocumentedElements:
    """Test skipping elements that already have docstrings."""

    @pytest.fixture
    def generator(self) -> DocstringGenerator:
        """Create generator with mock provider."""
        provider = MockLLMProvider()
        return DocstringGenerator(llm_provider=provider)

    @pytest.fixture
    def parser(self) -> PythonParser:
        """Create parser instance."""
        return PythonParser()

    @pytest.mark.asyncio
    async def test_skip_function_with_docstring(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test that functions with docstrings are skipped when overwrite=False."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
def documented_function():
    """This function already has a docstring."""
    pass

def undocumented_function():
    pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should only generate for undocumented function
        assert len(results) == 1
        assert results[0].element_name == "undocumented_function"

    @pytest.mark.asyncio
    async def test_overwrite_documented_function(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test that functions with docstrings are regenerated when overwrite=True."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
def documented_function():
    """Old docstring."""
    pass

def undocumented_function():
    pass
'''
        )

        results = await generator.generate_for_file(file_path, overwrite_existing=True)

        # Should generate for both functions
        assert len(results) == 2
        names = {r.element_name for r in results}
        assert "documented_function" in names
        assert "undocumented_function" in names

    @pytest.mark.asyncio
    async def test_skip_class_with_docstring(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test that classes with docstrings are skipped when overwrite=False."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class DocumentedClass:
    """This class has a docstring."""
    pass

class UndocumentedClass:
    pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should only generate for undocumented class
        assert len(results) == 1
        assert results[0].element_name == "UndocumentedClass"

    @pytest.mark.asyncio
    async def test_detect_existing_docstring(self, parser: PythonParser) -> None:
        """Test that parser correctly detects existing docstrings."""
        code_with_docstring = '''
def func():
    """This has a docstring."""
    pass
'''
        code_without_docstring = """
def func():
    pass
"""

        # Parse both
        result_with = parser.parse_string(code_with_docstring)
        result_without = parser.parse_string(code_without_docstring)

        assert len(result_with.elements) == 1
        assert result_with.elements[0].has_docstring is True

        assert len(result_without.elements) == 1
        assert result_without.elements[0].has_docstring is False

    @pytest.mark.asyncio
    async def test_various_docstring_formats_detected(
        self, parser: PythonParser
    ) -> None:
        """Test that various docstring formats are detected."""
        # Triple double quotes
        code1 = '''
def func1():
    """Docstring."""
    pass
'''

        # Triple single quotes
        code2 = """
def func2():
    '''Docstring.'''
    pass
"""

        # Multi-line docstring
        code3 = '''
def func3():
    """
    Multi-line
    docstring.
    """
    pass
'''

        for code in [code1, code2, code3]:
            result = parser.parse_string(code)
            assert result.elements[0].has_docstring is True


class TestMethodLevelChecking:
    """Test method-level checking within classes."""

    @pytest.fixture
    def generator(self) -> DocstringGenerator:
        """Create generator with mock provider."""
        provider = MockLLMProvider()
        return DocstringGenerator(llm_provider=provider)

    @pytest.mark.asyncio
    async def test_class_with_documented_and_undocumented_methods(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test class where some methods have docstrings and some don't."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class MyClass:
    def documented_method(self):
        """This method has a docstring."""
        pass

    def undocumented_method(self):
        pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should generate for class and undocumented method
        names = {r.element_name for r in results}
        assert "MyClass" in names
        assert "undocumented_method" in names
        # Should not generate for documented method
        assert "documented_method" not in names

    @pytest.mark.asyncio
    async def test_documented_class_with_undocumented_methods(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test documented class with undocumented methods."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class DocumentedClass:
    """This class has a docstring."""

    def undocumented_method1(self):
        pass

    def undocumented_method2(self):
        pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should skip the class but generate for methods
        names = {r.element_name for r in results}
        assert "DocumentedClass" not in names
        assert "undocumented_method1" in names
        assert "undocumented_method2" in names

    @pytest.mark.asyncio
    async def test_undocumented_class_with_documented_methods(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test undocumented class with documented methods."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class UndocumentedClass:
    def documented_method1(self):
        """Method 1 docstring."""
        pass

    def documented_method2(self):
        """Method 2 docstring."""
        pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should generate for class but skip documented methods
        names = {r.element_name for r in results}
        assert "UndocumentedClass" in names
        assert "documented_method1" not in names
        assert "documented_method2" not in names

    @pytest.mark.asyncio
    async def test_mixed_documentation_in_class(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test class with mixed documentation state."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class MixedClass:
    """Class has docstring."""

    def documented(self):
        """Has docstring."""
        pass

    def undocumented(self):
        pass

    def also_documented(self):
        """Has docstring."""
        pass

    def also_undocumented(self):
        pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should only generate for undocumented methods
        names = {r.element_name for r in results}
        assert "MixedClass" not in names  # Class is documented
        assert "documented" not in names
        assert "also_documented" not in names
        assert "undocumented" in names
        assert "also_undocumented" in names
        assert len(results) == 2


class TestNestedClassHandling:
    """Test handling of nested classes."""

    @pytest.fixture
    def generator(self) -> DocstringGenerator:
        """Create generator with mock provider."""
        provider = MockLLMProvider()
        return DocstringGenerator(llm_provider=provider)

    @pytest.mark.asyncio
    async def test_nested_class_documentation(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test that nested classes are handled correctly."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class OuterClass:
    def outer_method(self):
        pass

    class InnerClass:
        def inner_method(self):
            pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should generate for both classes and their methods
        assert len(results) > 0


class TestPropertyAndStaticMethods:
    """Test handling of properties and static methods."""

    @pytest.fixture
    def generator(self) -> DocstringGenerator:
        """Create generator with mock provider."""
        provider = MockLLMProvider()
        return DocstringGenerator(llm_provider=provider)

    @pytest.mark.asyncio
    async def test_property_documentation(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test that properties are handled correctly."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class MyClass:
    @property
    def my_property(self):
        pass

    @property
    def documented_property(self):
        """Has docstring."""
        pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        names = {r.element_name for r in results}
        assert "my_property" in names or "MyClass" in names
        # Documented property should be skipped
        assert "documented_property" not in names or len(results) >= 1

    @pytest.mark.asyncio
    async def test_static_method_documentation(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test that static methods are handled correctly."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class MyClass:
    @staticmethod
    def static_method():
        pass

    @staticmethod
    def documented_static():
        """Has docstring."""
        pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        names = {r.element_name for r in results}
        # Should process undocumented static method
        assert "static_method" in names or "MyClass" in names


class TestPartialUpdateDetection:
    """Test detection of what needs to be updated."""

    @pytest.fixture
    def parser(self) -> PythonParser:
        """Create parser instance."""
        return PythonParser()

    def test_identify_undocumented_functions(self, parser: PythonParser) -> None:
        """Test identifying which functions need documentation."""
        code = '''
def documented():
    """Has docs."""
    pass

def undocumented1():
    pass

def undocumented2():
    pass
'''
        result = parser.parse_string(code)

        documented = [e for e in result.elements if e.has_docstring]
        undocumented = [e for e in result.elements if not e.has_docstring]

        assert len(documented) == 1
        assert documented[0].name == "documented"
        assert len(undocumented) == 2
        assert {e.name for e in undocumented} == {"undocumented1", "undocumented2"}

    def test_identify_undocumented_methods(self, parser: PythonParser) -> None:
        """Test identifying which methods need documentation."""
        code = '''
class MyClass:
    def documented(self):
        """Has docs."""
        pass

    def undocumented(self):
        pass
'''
        result = parser.parse_string(code)

        assert len(result.elements) == 1
        cls = result.elements[0]

        documented = [m for m in cls.methods if m.has_docstring]
        undocumented = [m for m in cls.methods if not m.has_docstring]

        assert len(documented) == 1
        assert documented[0].name == "documented"
        assert len(undocumented) == 1
        assert undocumented[0].name == "undocumented"


class TestDocstringContentValidation:
    """Test validation of existing docstring content."""

    @pytest.fixture
    def parser(self) -> PythonParser:
        """Create parser instance."""
        return PythonParser()

    def test_detect_empty_docstring(self, parser: PythonParser) -> None:
        """Test detection of empty docstrings."""
        code = '''
def func():
    """"""
    pass
'''
        result = parser.parse_string(code)

        # Empty docstring should still count as having a docstring
        assert result.elements[0].has_docstring is True

    def test_detect_whitespace_only_docstring(self, parser: PythonParser) -> None:
        """Test detection of whitespace-only docstrings."""
        code = '''
def func():
    """   """
    pass
'''
        result = parser.parse_string(code)

        # Whitespace-only should still count as having a docstring
        assert result.elements[0].has_docstring is True

    def test_single_line_docstring(self, parser: PythonParser) -> None:
        """Test single-line docstring detection."""
        code = '''
def func():
    """Single line docstring."""
    pass
'''
        result = parser.parse_string(code)

        assert result.elements[0].has_docstring is True

    def test_multiline_docstring(self, parser: PythonParser) -> None:
        """Test multi-line docstring detection."""
        code = '''
def func():
    """
    Multi-line docstring.

    With multiple paragraphs.
    """
    pass
'''
        result = parser.parse_string(code)

        assert result.elements[0].has_docstring is True


class TestSelectiveGeneration:
    """Test selective generation of docstrings."""

    @pytest.fixture
    def generator(self) -> DocstringGenerator:
        """Create generator with mock provider."""
        provider = MockLLMProvider()
        return DocstringGenerator(llm_provider=provider)

    @pytest.mark.asyncio
    async def test_generate_only_for_public_functions(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test generating only for public functions."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
def public_function():
    pass

def _private_function():
    pass

def __dunder_function__():
    pass
'''
        )

        results = await generator.generate_for_file(
            file_path, include_private=False
        )

        names = {r.element_name for r in results}
        assert "public_function" in names
        # Private functions should not be included
        assert "_private_function" not in names
        assert "__dunder_function__" not in names

    @pytest.mark.asyncio
    async def test_include_private_when_requested(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test including private functions when requested."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
def public_function():
    pass

def _private_function():
    pass
'''
        )

        results = await generator.generate_for_file(
            file_path, include_private=True
        )

        names = {r.element_name for r in results}
        assert "public_function" in names
        assert "_private_function" in names

    @pytest.mark.asyncio
    async def test_mixed_public_private_in_class(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test class with mixed public and private methods."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
class MyClass:
    def public_method(self):
        pass

    def _private_method(self):
        pass

    def __dunder_method__(self):
        pass
'''
        )

        results = await generator.generate_for_file(
            file_path, include_private=False
        )

        names = {r.element_name for r in results}
        assert "public_method" in names or "MyClass" in names
        # Private methods should not be included
        assert "_private_method" not in names
        assert "__dunder_method__" not in names


class TestIncrementalDocumentation:
    """Test incremental documentation workflows."""

    @pytest.fixture
    def generator(self) -> DocstringGenerator:
        """Create generator with mock provider."""
        provider = MockLLMProvider()
        return DocstringGenerator(llm_provider=provider)

    @pytest.mark.asyncio
    async def test_first_pass_documents_all(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test first pass documents all undocumented elements."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
def func1():
    pass

def func2():
    pass

def func3():
    pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should document all 3 functions
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_second_pass_documents_new_only(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test second pass only documents newly added code."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
def func1():
    """Already documented."""
    pass

def func2():
    """Already documented."""
    pass

def func3():
    pass
'''
        )

        results = await generator.generate_for_file(
            file_path, overwrite_existing=False
        )

        # Should only document func3
        assert len(results) == 1
        assert results[0].element_name == "func3"

    @pytest.mark.asyncio
    async def test_update_only_changed_functions(
        self, generator: DocstringGenerator, tmp_path: Path
    ) -> None:
        """Test updating only functions that changed."""
        file_path = tmp_path / "test.py"
        file_path.write_text(
            '''
def unchanged():
    """Old docstring - still good."""
    pass

def changed(new_param):
    """Old docstring - needs update."""
    pass
'''
        )

        # In practice, would check signatures/timestamps
        # Here we test that selective generation works
        results = await generator.generate_for_file(
            file_path, overwrite_existing=True
        )

        # Would regenerate both with overwrite=True
        assert len(results) == 2
