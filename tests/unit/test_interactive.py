"""Tests for interactive approval mode.

This module tests the interactive approval functionality for reviewing
and approving docstrings before writing them to files.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from rich.console import Console

from docpilot.cli.interactive import (
    ApprovalAction,
    ApprovalResult,
    InteractiveApprover,
    InteractiveStats,
)
from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    DocstringStyle,
    GeneratedDocstring,
)


@pytest.fixture
def mock_console():
    """Create a mock Rich console."""
    console = Mock(spec=Console)
    console.clear = Mock()
    console.print = Mock()
    console.input = Mock()
    return console


@pytest.fixture
def approver(mock_console):
    """Create an InteractiveApprover instance with mock console."""
    return InteractiveApprover(console=mock_console)


@pytest.fixture
def sample_element():
    """Create a sample code element for testing."""
    return CodeElement(
        name="test_function",
        element_type=CodeElementType.FUNCTION,
        lineno=10,
        source_code="def test_function():\n    pass",
        docstring=None,
        is_public=True,
        parameters=[],
        return_info=None,
        raises=[],
        decorators=[],
        complexity_score=1,
        is_async=False,
        is_property=False,
    )


@pytest.fixture
def sample_element_with_docstring():
    """Create a sample code element with existing docstring."""
    return CodeElement(
        name="existing_function",
        element_type=CodeElementType.FUNCTION,
        lineno=20,
        source_code='def existing_function():\n    """Old docstring."""\n    pass',
        docstring="Old docstring.",
        is_public=True,
        parameters=[],
        return_info=None,
        raises=[],
        decorators=[],
        complexity_score=1,
        is_async=False,
        is_property=False,
    )


@pytest.fixture
def generated_docstring():
    """Create a sample generated docstring."""
    return GeneratedDocstring(
        element_name="test_function",
        element_type=CodeElementType.FUNCTION,
        docstring="This is a test function.\n\nReturns:\n    None",
        style=DocstringStyle.GOOGLE,
        confidence_score=0.95,
        warnings=[],
        metadata={},
    )


@pytest.fixture
def generated_docstring_with_warnings():
    """Create a sample generated docstring with warnings."""
    return GeneratedDocstring(
        element_name="test_function",
        element_type=CodeElementType.FUNCTION,
        docstring="This is a test function.",
        style=DocstringStyle.GOOGLE,
        confidence_score=0.75,
        warnings=[
            "Parameters without type hints: x, y",
            "Complex function (complexity 15) has brief documentation",
        ],
        metadata={},
    )


class TestInteractiveStats:
    """Tests for InteractiveStats class."""

    def test_initial_stats(self):
        """Test that stats are initialized to zero."""
        stats = InteractiveStats()
        assert stats.accepted == 0
        assert stats.rejected == 0
        assert stats.edited == 0
        assert stats.skipped == 0

    def test_total_processed(self):
        """Test total_processed property calculation."""
        stats = InteractiveStats(accepted=5, rejected=3, edited=2, skipped=1)
        assert stats.total_processed == 10

    def test_total_written(self):
        """Test total_written property calculation."""
        stats = InteractiveStats(accepted=5, rejected=3, edited=2, skipped=1)
        assert stats.total_written == 7  # accepted + edited


class TestInteractiveApprover:
    """Tests for InteractiveApprover class."""

    def test_initialization(self, mock_console):
        """Test approver initialization."""
        approver = InteractiveApprover(console=mock_console)
        assert approver.console == mock_console
        assert approver.stats.accepted == 0
        assert approver.stats.rejected == 0
        assert approver.stats.edited == 0
        assert approver.stats.skipped == 0

    def test_initialization_without_console(self):
        """Test approver initialization without console creates default."""
        approver = InteractiveApprover()
        assert approver.console is not None
        assert isinstance(approver.console, Console)

    @patch("docpilot.cli.interactive.Prompt.ask")
    def test_review_docstring_accept(
        self,
        mock_prompt,
        approver,
        sample_element,
        generated_docstring,
    ):
        """Test accepting a docstring in review."""
        mock_prompt.return_value = "a"

        result = approver.review_docstring(
            element=sample_element,
            generated=generated_docstring,
            file_path=Path("test.py"),
        )

        assert result.action == ApprovalAction.ACCEPT
        assert result.docstring == generated_docstring.docstring
        assert result.element_name == sample_element.name
        assert approver.stats.accepted == 1

    @patch("docpilot.cli.interactive.Prompt.ask")
    def test_review_docstring_reject(
        self,
        mock_prompt,
        approver,
        sample_element,
        generated_docstring,
    ):
        """Test rejecting a docstring in review."""
        mock_prompt.return_value = "r"

        result = approver.review_docstring(
            element=sample_element,
            generated=generated_docstring,
            file_path=Path("test.py"),
        )

        assert result.action == ApprovalAction.REJECT
        assert approver.stats.rejected == 1

    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    def test_review_docstring_quit(
        self,
        mock_prompt,
        mock_confirm,
        approver,
        sample_element,
        generated_docstring,
    ):
        """Test quitting during review."""
        mock_prompt.return_value = "q"
        mock_confirm.return_value = True  # Confirm quit

        result = approver.review_docstring(
            element=sample_element,
            generated=generated_docstring,
            file_path=Path("test.py"),
        )

        assert result.action == ApprovalAction.QUIT
        assert approver.stats.skipped == 1

    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    def test_review_docstring_quit_cancel(
        self,
        mock_prompt,
        mock_confirm,
        approver,
        sample_element,
        generated_docstring,
    ):
        """Test canceling quit and choosing another action."""
        # First attempt to quit is canceled, then accept
        mock_prompt.side_effect = ["q", "a"]
        mock_confirm.return_value = False  # Don't confirm quit

        result = approver.review_docstring(
            element=sample_element,
            generated=generated_docstring,
            file_path=Path("test.py"),
        )

        assert result.action == ApprovalAction.ACCEPT
        assert approver.stats.accepted == 1
        assert approver.stats.skipped == 0

    @patch("docpilot.cli.interactive.Prompt.ask")
    def test_review_docstring_with_warnings(
        self,
        mock_prompt,
        approver,
        sample_element,
        generated_docstring_with_warnings,
    ):
        """Test reviewing a docstring that has warnings."""
        mock_prompt.return_value = "a"

        result = approver.review_docstring(
            element=sample_element,
            generated=generated_docstring_with_warnings,
            file_path=Path("test.py"),
        )

        assert result.action == ApprovalAction.ACCEPT
        # Verify that warnings were displayed (check console.print was called)
        assert approver.console.print.called

    @patch("docpilot.cli.interactive.Prompt.ask")
    def test_review_docstring_with_existing(
        self,
        mock_prompt,
        approver,
        sample_element_with_docstring,
        generated_docstring,
    ):
        """Test reviewing a docstring when element already has one."""
        mock_prompt.return_value = "a"

        result = approver.review_docstring(
            element=sample_element_with_docstring,
            generated=generated_docstring,
            file_path=Path("test.py"),
        )

        assert result.action == ApprovalAction.ACCEPT
        # Verify console methods were called to show diff
        assert approver.console.clear.called
        assert approver.console.print.called

    def test_display_final_stats_no_processing(self, approver):
        """Test displaying stats when nothing was processed."""
        approver.display_final_stats()

        # Verify warning message was printed
        assert approver.console.print.called
        call_args = approver.console.print.call_args_list
        # Check that one of the calls contains "No docstrings"
        assert any("No docstrings" in str(call) for call in call_args)

    def test_display_final_stats_with_data(self, approver):
        """Test displaying stats with various actions taken."""
        # Simulate some actions
        approver.stats.accepted = 10
        approver.stats.rejected = 3
        approver.stats.edited = 2
        approver.stats.skipped = 1

        approver.display_final_stats()

        # Verify table was printed
        assert approver.console.print.called

    def test_update_stats_accept(self, approver):
        """Test updating stats for accept action."""
        approver._update_stats(ApprovalAction.ACCEPT)
        assert approver.stats.accepted == 1

    def test_update_stats_reject(self, approver):
        """Test updating stats for reject action."""
        approver._update_stats(ApprovalAction.REJECT)
        assert approver.stats.rejected == 1

    def test_update_stats_edit(self, approver):
        """Test updating stats for edit action."""
        approver._update_stats(ApprovalAction.EDIT)
        assert approver.stats.edited == 1

    def test_update_stats_quit(self, approver):
        """Test updating stats for quit action."""
        approver._update_stats(ApprovalAction.QUIT)
        assert approver.stats.skipped == 1

    def test_percentage_calculation(self, approver):
        """Test percentage calculation helper."""
        assert approver._percentage(5, 10) == "50.0"
        assert approver._percentage(1, 3) == "33.3"
        assert approver._percentage(0, 10) == "0.0"
        assert approver._percentage(5, 0) == "0.0"  # Division by zero case

    def test_get_editor_from_env(self, approver):
        """Test getting editor from environment variable."""
        with patch.dict("os.environ", {"EDITOR": "vim"}):
            editor = approver._get_editor()
            assert editor == "vim"

    def test_get_editor_common(self, approver):
        """Test getting common editor when EDITOR not set."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("docpilot.cli.interactive.InteractiveApprover._command_exists") as mock_exists:
                # Simulate vim exists
                mock_exists.side_effect = lambda cmd: cmd == "vim"
                editor = approver._get_editor()
                assert editor == "vim"

    def test_get_editor_none(self, approver):
        """Test when no editor is available."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("docpilot.cli.interactive.InteractiveApprover._command_exists") as mock_exists:
                # No editors exist
                mock_exists.return_value = False
                editor = approver._get_editor()
                assert editor is None

    def test_command_exists_true(self, approver):
        """Test command exists check when command is available."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/vim"
            assert approver._command_exists("vim") is True

    def test_command_exists_false(self, approver):
        """Test command exists check when command is not available."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            assert approver._command_exists("nonexistent") is False

    def test_extract_docstring_from_edited_multiline(self, approver):
        """Test extracting multiline docstring from edited content."""
        content = '''# This is a comment
"""
This is a test function.

Args:
    x: First parameter

Returns:
    None
"""
'''
        result = approver._extract_docstring_from_edited(content)
        expected = "This is a test function.\n\nArgs:\n    x: First parameter\n\nReturns:\n    None"
        assert result == expected

    def test_extract_docstring_from_edited_single_line(self, approver):
        """Test extracting single-line docstring from edited content."""
        content = '''# Comment
"""This is a one-liner."""
'''
        result = approver._extract_docstring_from_edited(content)
        assert result == "This is a one-liner."

    def test_extract_docstring_from_edited_with_single_quotes(self, approver):
        """Test extracting docstring using single quotes."""
        content = """# Comment
'''
Test docstring.
'''
"""
        result = approver._extract_docstring_from_edited(content)
        assert result == "Test docstring."

    @patch("subprocess.run")
    @patch("builtins.open")
    @patch("tempfile.NamedTemporaryFile")
    @patch("docpilot.cli.interactive.InteractiveApprover._get_editor")
    def test_edit_docstring_success(
        self,
        mock_get_editor,
        mock_temp_file,
        mock_open,
        mock_subprocess,
        approver,
    ):
        """Test successful docstring editing."""
        mock_get_editor.return_value = "vim"

        # Mock temporary file
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test.py"
        mock_temp.__enter__ = Mock(return_value=mock_temp)
        mock_temp.__exit__ = Mock(return_value=False)
        mock_temp_file.return_value = mock_temp

        # Mock subprocess (editor)
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Mock reading edited file
        edited_content = '"""Edited docstring."""'
        mock_open.return_value.__enter__.return_value.read.return_value = edited_content

        original_docstring = "Original docstring."
        result = approver._edit_docstring(original_docstring)

        assert result == "Edited docstring."
        mock_subprocess.assert_called_once()

    @patch("docpilot.cli.interactive.InteractiveApprover._get_editor")
    def test_edit_docstring_no_editor(self, mock_get_editor, approver):
        """Test editing when no editor is available."""
        mock_get_editor.return_value = None

        original_docstring = "Original docstring."
        result = approver._edit_docstring(original_docstring)

        # Should return unchanged docstring
        assert result == original_docstring
        # Should print error message
        assert approver.console.print.called

    @patch("subprocess.run")
    @patch("docpilot.cli.interactive.InteractiveApprover._get_editor")
    def test_edit_docstring_editor_error(
        self,
        mock_get_editor,
        mock_subprocess,
        approver,
    ):
        """Test handling editor errors."""
        mock_get_editor.return_value = "vim"
        mock_subprocess.side_effect = Exception("Editor failed")

        original_docstring = "Original docstring."
        result = approver._edit_docstring(original_docstring)

        # Should return unchanged docstring
        assert result == original_docstring
        # Should print error message
        assert approver.console.print.called


class TestApprovalResult:
    """Tests for ApprovalResult dataclass."""

    def test_approval_result_creation(self):
        """Test creating an ApprovalResult."""
        result = ApprovalResult(
            action=ApprovalAction.ACCEPT,
            docstring="Test docstring",
            element_name="test_func",
        )

        assert result.action == ApprovalAction.ACCEPT
        assert result.docstring == "Test docstring"
        assert result.element_name == "test_func"


class TestApprovalAction:
    """Tests for ApprovalAction enum."""

    def test_approval_action_values(self):
        """Test that all expected approval actions exist."""
        assert ApprovalAction.ACCEPT.value == "accept"
        assert ApprovalAction.REJECT.value == "reject"
        assert ApprovalAction.EDIT.value == "edit"
        assert ApprovalAction.QUIT.value == "quit"

    def test_approval_action_from_string(self):
        """Test creating approval action from string."""
        assert ApprovalAction("accept") == ApprovalAction.ACCEPT
        assert ApprovalAction("reject") == ApprovalAction.REJECT
        assert ApprovalAction("edit") == ApprovalAction.EDIT
        assert ApprovalAction("quit") == ApprovalAction.QUIT
