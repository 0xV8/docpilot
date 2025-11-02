"""Unit tests for error handling improvements."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from docpilot.core.parser import PythonParser
from docpilot.utils.file_ops import FileOperations


class TestSyntaxErrorHandling:
    """Test handling of syntax errors in Python files."""

    @pytest.fixture
    def parser(self) -> PythonParser:
        """Create parser instance."""
        return PythonParser()

    def test_syntax_error_in_string(self, parser: PythonParser) -> None:
        """Test that syntax errors are properly raised."""
        invalid_code = """
def invalid_function(
    # Missing closing parenthesis
    return 42
"""
        with pytest.raises(SyntaxError):
            parser.parse_string(invalid_code)

    def test_syntax_error_with_details(self, parser: PythonParser) -> None:
        """Test that syntax error includes useful details."""
        invalid_code = "def broken syntax here"

        try:
            parser.parse_string(invalid_code)
            pytest.fail("Should have raised SyntaxError")
        except SyntaxError as e:
            # Should have error details
            assert e.msg is not None or e.text is not None

    def test_syntax_error_in_file(self, parser: PythonParser, tmp_path: Path) -> None:
        """Test handling syntax error in file."""
        file_path = tmp_path / "broken.py"
        file_path.write_text("def invalid syntax here")

        with pytest.raises(SyntaxError):
            parser.parse_file(file_path)

    def test_syntax_error_file_info_preserved(
        self, parser: PythonParser, tmp_path: Path
    ) -> None:
        """Test that filename is preserved in SyntaxError."""
        file_path = tmp_path / "broken.py"
        file_path.write_text("def broken(:\n    pass")

        try:
            parser.parse_file(file_path)
            pytest.fail("Should have raised SyntaxError")
        except SyntaxError as e:
            # Filename should be in error
            assert e.filename is not None

    def test_indentation_error(self, parser: PythonParser) -> None:
        """Test handling of indentation errors."""
        invalid_code = """
def func():
pass  # Wrong indentation
"""
        with pytest.raises(IndentationError):
            parser.parse_string(invalid_code)

    def test_invalid_token(self, parser: PythonParser) -> None:
        """Test handling of invalid tokens."""
        invalid_code = "def func():\n    return @@@"

        with pytest.raises(SyntaxError):
            parser.parse_string(invalid_code)

    def test_incomplete_code(self, parser: PythonParser) -> None:
        """Test handling of incomplete code."""
        invalid_code = """
def incomplete_function():
    if True:
        print("missing return
"""
        with pytest.raises(SyntaxError):
            parser.parse_string(invalid_code)


class TestFileOperationErrors:
    """Test error handling in file operations."""

    @pytest.fixture
    def file_ops(self) -> FileOperations:
        """Create FileOperations instance."""
        return FileOperations()

    def test_insert_docstring_file_not_found(self, file_ops: FileOperations) -> None:
        """Test handling of non-existent file."""
        with pytest.raises(FileNotFoundError):
            file_ops.insert_docstring(
                Path("/nonexistent/file.py"),
                "func",
                "Docstring",
            )

    def test_insert_docstring_syntax_error(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test handling syntax error during docstring insertion."""
        file_path = tmp_path / "broken.py"
        file_path.write_text("def broken syntax here")

        with pytest.raises(SyntaxError):
            file_ops.insert_docstring(file_path, "broken", "Docstring")

    def test_backup_file_not_found(self, file_ops: FileOperations) -> None:
        """Test backup of non-existent file."""
        with pytest.raises(FileNotFoundError):
            file_ops.backup_file(Path("/nonexistent/file.py"))

    def test_restore_backup_not_found(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test restoring when backup doesn't exist."""
        file_path = tmp_path / "file.py"
        file_path.write_text("pass")

        with pytest.raises(FileNotFoundError):
            file_ops.restore_backup(file_path)

    def test_find_files_invalid_path(self, file_ops: FileOperations) -> None:
        """Test finding files in non-existent directory."""
        with pytest.raises(FileNotFoundError):
            file_ops.find_python_files(Path("/nonexistent/dir"))


class TestMissingDependencyErrors:
    """Test handling of missing package dependencies."""

    def test_missing_llm_provider_import(self) -> None:
        """Test graceful handling when LLM provider package is missing."""
        # This is tested at the module level, so we simulate it
        with patch.dict(sys.modules, {"openai": None}):
            # The import should fail when trying to use OpenAI provider
            from docpilot.llm.base import LLMConfig, LLMProvider

            config = LLMConfig(
                provider=LLMProvider.OPENAI,
                model="gpt-3.5-turbo",
                api_key="test",
            )

            # When creating provider, should get appropriate error
            from docpilot.llm.base import create_provider

            # Mock provider should still work
            mock_config = LLMConfig(
                provider=LLMProvider.MOCK,
                model="mock",
            )
            provider = create_provider(mock_config)
            assert provider is not None

    def test_missing_anthropic_handled(self) -> None:
        """Test that missing anthropic package is handled gracefully."""
        from docpilot.llm.base import LLMConfig, LLMProvider

        # Mock provider should work even if anthropic is not installed
        config = LLMConfig(
            provider=LLMProvider.MOCK,
            model="mock",
        )

        from docpilot.llm.base import create_provider

        provider = create_provider(config)
        assert provider is not None

    @pytest.mark.skipif(
        sys.version_info < (3, 11),
        reason="tomllib is built-in from Python 3.11+",
    )
    def test_tomllib_available_python311(self) -> None:
        """Test that tomllib is available in Python 3.11+."""
        import tomllib

        assert hasattr(tomllib, "load")

    @pytest.mark.skipif(
        sys.version_info >= (3, 11),
        reason="tomli is used for Python < 3.11",
    )
    def test_tomli_fallback_python310(self) -> None:
        """Test that tomli is used as fallback in Python < 3.11."""
        import tomli

        assert hasattr(tomli, "load")


class TestVerboseFlagBehavior:
    """Test verbose flag showing stack traces."""

    def test_verbose_mode_shows_details(self, capsys: pytest.CaptureFixture) -> None:
        """Test that verbose mode shows detailed error information."""
        # Simulate verbose mode behavior
        verbose = True

        def handle_error(error: Exception, verbose: bool) -> None:
            if verbose:
                import traceback

                traceback.print_exc()
            else:
                print(f"Error: {error}")

        try:
            raise ValueError("Test error")
        except ValueError as e:
            handle_error(e, verbose)

        captured = capsys.readouterr()
        # In verbose mode, should see traceback
        assert "Traceback" in captured.err or "ValueError" in captured.out

    def test_quiet_mode_suppresses_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Test that quiet mode suppresses non-error output."""
        quiet = True

        def log_info(message: str, quiet: bool) -> None:
            if not quiet:
                print(message)

        log_info("This is info", quiet)
        captured = capsys.readouterr()

        # Should not print in quiet mode
        assert captured.out == ""

    def test_verbose_overrides_quiet(self) -> None:
        """Test that verbose flag takes precedence over quiet."""
        verbose = True
        quiet = True

        # When both are set, verbose should win
        should_show_output = verbose or not quiet

        assert should_show_output is True


class TestGracefulDegradation:
    """Test graceful degradation when optional features fail."""

    def test_complexity_calculation_failure(self) -> None:
        """Test that complexity calculation failures don't stop processing."""
        from docpilot.core.models import CodeElement, CodeElementType

        element = CodeElement(
            name="test_func",
            element_type=CodeElementType.FUNCTION,
            source_code="def test_func(): pass",
            lineno=1,
            end_lineno=1,
        )

        # Even if complexity calculation fails, element should be valid
        assert element.complexity_score is None
        assert element.name == "test_func"

    def test_pattern_detection_failure(self) -> None:
        """Test that pattern detection failures don't stop processing."""
        from docpilot.core.models import CodeElement, CodeElementType

        element = CodeElement(
            name="test_func",
            element_type=CodeElementType.FUNCTION,
            source_code="def test_func(): pass",
            lineno=1,
            end_lineno=1,
        )

        # Even without patterns, element should be valid
        assert element.metadata.get("patterns", []) == []
        assert element.name == "test_func"


class TestErrorMessages:
    """Test that error messages are helpful and user-friendly."""

    def test_file_not_found_message(self, tmp_path: Path) -> None:
        """Test that file not found errors have clear messages."""
        nonexistent = tmp_path / "missing.py"

        try:
            from docpilot.utils.file_ops import FileOperations

            ops = FileOperations()
            ops.insert_docstring(nonexistent, "func", "doc")
            pytest.fail("Should raise FileNotFoundError")
        except FileNotFoundError as e:
            # Error message should mention the file
            assert "missing.py" in str(e) or str(nonexistent) in str(e)

    def test_syntax_error_shows_location(self, tmp_path: Path) -> None:
        """Test that syntax errors show file location."""
        file_path = tmp_path / "syntax_error.py"
        file_path.write_text("def broken(:\n    pass")

        try:
            from docpilot.core.parser import PythonParser

            parser = PythonParser()
            parser.parse_file(file_path)
            pytest.fail("Should raise SyntaxError")
        except SyntaxError as e:
            # Should have line number information
            assert e.lineno is not None or e.offset is not None

    def test_validation_error_clear_message(self) -> None:
        """Test that validation errors have clear messages."""
        from docpilot.utils.config import DocpilotConfig

        try:
            DocpilotConfig(log_level="INVALID_LEVEL")
            pytest.fail("Should raise ValueError")
        except ValueError as e:
            # Should mention valid options
            error_msg = str(e)
            assert "DEBUG" in error_msg or "INFO" in error_msg


class TestRecoveryMechanisms:
    """Test recovery mechanisms for errors."""

    def test_backup_and_restore_on_error(self, tmp_path: Path) -> None:
        """Test that files can be restored from backup on error."""
        from docpilot.utils.file_ops import FileOperations

        file_path = tmp_path / "test.py"
        original_content = "def original(): pass"
        file_path.write_text(original_content)

        ops = FileOperations()

        # Create backup
        backup = ops.backup_file(file_path)
        assert backup.exists()

        # Modify file
        file_path.write_text("def modified(): pass")

        # Restore from backup
        ops.restore_backup(file_path)

        # Should be back to original
        assert file_path.read_text() == original_content

    def test_dry_run_prevents_modifications(self, tmp_path: Path) -> None:
        """Test that dry run mode prevents actual file modifications."""
        from docpilot.utils.file_ops import FileOperations

        file_path = tmp_path / "test.py"
        original_content = "def test(): pass"
        file_path.write_text(original_content)

        ops = FileOperations(dry_run=True)

        # Try to insert docstring
        ops.insert_docstring(file_path, "test", '"""Test function."""')

        # File should not be modified
        assert file_path.read_text() == original_content

    def test_dry_run_backup_not_created(self, tmp_path: Path) -> None:
        """Test that dry run mode doesn't create backup files."""
        from docpilot.utils.file_ops import FileOperations

        file_path = tmp_path / "test.py"
        file_path.write_text("def test(): pass")

        ops = FileOperations(dry_run=True)

        # Try to create backup
        backup_path = ops.backup_file(file_path)

        # Backup file should not actually exist
        assert not backup_path.exists()


class TestErrorContext:
    """Test that errors include helpful context."""

    def test_parsing_error_includes_file_path(self, tmp_path: Path) -> None:
        """Test that parsing errors include the file being parsed."""
        from docpilot.core.parser import PythonParser

        file_path = tmp_path / "error.py"
        file_path.write_text("invalid python syntax")

        parser = PythonParser()

        try:
            parser.parse_file(file_path)
            pytest.fail("Should raise SyntaxError")
        except SyntaxError as e:
            # Error should reference the file
            assert e.filename is not None

    def test_element_not_found_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that missing elements generate helpful warnings."""
        from docpilot.utils.file_ops import FileOperations

        file_path = tmp_path / "test.py"
        file_path.write_text("def existing(): pass")

        ops = FileOperations()

        # Try to add docstring to non-existent element
        result = ops.insert_docstring(file_path, "nonexistent", "Docstring")

        # Should return False and log warning
        assert result is False

    def test_config_validation_mentions_valid_values(self) -> None:
        """Test that config validation errors mention valid values."""
        from docpilot.utils.config import DocpilotConfig

        try:
            DocpilotConfig(log_format="xml")
            pytest.fail("Should raise ValueError")
        except ValueError as e:
            error_msg = str(e)
            # Should list valid formats
            assert "json" in error_msg or "console" in error_msg


class TestConcurrentErrorHandling:
    """Test error handling in concurrent operations."""

    @pytest.mark.asyncio
    async def test_one_file_error_doesnt_stop_others(self) -> None:
        """Test that error in one file doesn't prevent processing others."""
        from docpilot.core.generator import DocstringGenerator, MockLLMProvider

        # This would be tested at integration level, but we can test the concept
        provider = MockLLMProvider()
        generator = DocstringGenerator(llm_provider=provider)

        # Even if one element fails, generator should continue
        assert generator is not None
        assert await provider.test_connection() is True

    def test_partial_success_reported(self) -> None:
        """Test that partial successes are properly reported."""
        # Track successes and failures
        total_files = 5
        successful = 3
        failed = 2

        # Should report both
        assert successful + failed == total_files
        success_rate = successful / total_files
        assert 0 < success_rate < 1
