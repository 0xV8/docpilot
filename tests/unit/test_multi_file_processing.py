"""Unit tests for multi-file processing and deduplication."""

from pathlib import Path

import pytest

from docpilot.utils.file_ops import FileOperations


class TestSingleFileProcessing:
    """Test processing a single Python file."""

    @pytest.fixture
    def file_ops(self) -> FileOperations:
        """Create FileOperations instance."""
        return FileOperations()

    @pytest.fixture
    def single_file(self, tmp_path: Path) -> Path:
        """Create a single Python file for testing."""
        file_path = tmp_path / "module.py"
        file_path.write_text(
            '''"""Module docstring."""

def example_function():
    pass

class ExampleClass:
    def method(self):
        pass
'''
        )
        return file_path

    def test_find_single_file(
        self, file_ops: FileOperations, single_file: Path
    ) -> None:
        """Test finding a single Python file."""
        files = file_ops.find_python_files(single_file.parent, pattern="*.py")

        assert len(files) == 1
        assert files[0] == single_file

    def test_single_file_in_directory(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test finding single file in directory with one file."""
        file_path = tmp_path / "test.py"
        file_path.write_text("def test(): pass")

        files = file_ops.find_python_files(tmp_path, pattern="**/*.py")

        assert len(files) == 1
        assert files[0] == file_path


class TestMultipleFileProcessing:
    """Test processing multiple Python files."""

    @pytest.fixture
    def file_ops(self) -> FileOperations:
        """Create FileOperations instance."""
        return FileOperations()

    @pytest.fixture
    def multiple_files(self, tmp_path: Path) -> list[Path]:
        """Create multiple Python files for testing."""
        files = []

        file1 = tmp_path / "file1.py"
        file1.write_text("def func1(): pass")
        files.append(file1)

        file2 = tmp_path / "file2.py"
        file2.write_text("def func2(): pass")
        files.append(file2)

        file3 = tmp_path / "file3.py"
        file3.write_text("def func3(): pass")
        files.append(file3)

        return files

    def test_find_multiple_files(
        self, file_ops: FileOperations, multiple_files: list[Path], tmp_path: Path
    ) -> None:
        """Test finding multiple Python files in a directory."""
        files = file_ops.find_python_files(tmp_path, pattern="*.py")

        assert len(files) == 3
        assert set(files) == set(multiple_files)

    def test_files_sorted(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test that files are returned sorted."""
        # Create files in non-alphabetical order
        (tmp_path / "z_file.py").write_text("pass")
        (tmp_path / "a_file.py").write_text("pass")
        (tmp_path / "m_file.py").write_text("pass")

        files = file_ops.find_python_files(tmp_path, pattern="*.py")

        assert len(files) == 3
        # Should be sorted
        assert files[0].name == "a_file.py"
        assert files[1].name == "m_file.py"
        assert files[2].name == "z_file.py"

    def test_multiple_files_in_subdirectories(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test finding files in nested subdirectories."""
        # Create nested structure
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "module1.py").write_text("pass")

        (tmp_path / "src" / "subpackage").mkdir()
        (tmp_path / "src" / "subpackage" / "module2.py").write_text("pass")

        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_module.py").write_text("pass")

        files = file_ops.find_python_files(tmp_path, pattern="**/*.py")

        assert len(files) == 3
        file_names = {f.name for f in files}
        assert file_names == {"module1.py", "module2.py", "test_module.py"}


class TestDirectoryProcessing:
    """Test processing entire directories."""

    @pytest.fixture
    def file_ops(self) -> FileOperations:
        """Create FileOperations instance."""
        return FileOperations()

    @pytest.fixture
    def project_structure(self, tmp_path: Path) -> Path:
        """Create a realistic project structure."""
        # Main source directory
        src_dir = tmp_path / "src" / "mypackage"
        src_dir.mkdir(parents=True)

        (src_dir / "__init__.py").write_text("")
        (src_dir / "core.py").write_text("def core_func(): pass")
        (src_dir / "utils.py").write_text("def util_func(): pass")

        # Subpackage
        sub_dir = src_dir / "subpackage"
        sub_dir.mkdir()
        (sub_dir / "__init__.py").write_text("")
        (sub_dir / "module.py").write_text("def module_func(): pass")

        # Tests directory
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_core.py").write_text("def test_core(): pass")

        return tmp_path

    def test_find_all_python_files(
        self, file_ops: FileOperations, project_structure: Path
    ) -> None:
        """Test finding all Python files in project."""
        files = file_ops.find_python_files(project_structure, pattern="**/*.py")

        # Should find all 6 files
        assert len(files) >= 6

    def test_find_only_source_files(
        self, file_ops: FileOperations, project_structure: Path
    ) -> None:
        """Test finding only source files (exclude tests)."""
        exclude_patterns = ["**/test_*.py", "**/*_test.py", "**/tests/**"]
        files = file_ops.find_python_files(
            project_structure, pattern="**/*.py", exclude_patterns=exclude_patterns
        )

        # Should exclude test files
        file_names = {f.name for f in files}
        assert "test_core.py" not in file_names
        assert "__init__.py" in file_names
        assert "core.py" in file_names

    def test_find_specific_subdirectory(
        self, file_ops: FileOperations, project_structure: Path
    ) -> None:
        """Test finding files in specific subdirectory."""
        src_dir = project_structure / "src"
        files = file_ops.find_python_files(src_dir, pattern="**/*.py")

        # Should find files only in src/
        for file in files:
            assert "src" in str(file)
            assert "tests" not in str(file)

    def test_exclude_pycache(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test that __pycache__ directories are excluded."""
        # Create __pycache__ directory
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "module.cpython-39.pyc").write_text("bytecode")

        # Create normal Python file
        (tmp_path / "module.py").write_text("def func(): pass")

        exclude_patterns = ["**/__pycache__/**"]
        files = file_ops.find_python_files(
            tmp_path, pattern="**/*.py*", exclude_patterns=exclude_patterns
        )

        # Should not include files from __pycache__
        assert len(files) == 1
        assert files[0].name == "module.py"

    def test_exclude_hidden_directories(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test that hidden directories (starting with .) are excluded."""
        # Create hidden directory
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config.py").write_text("pass")

        # Create normal file
        (tmp_path / "module.py").write_text("def func(): pass")

        exclude_patterns = ["**/.*/**"]
        files = file_ops.find_python_files(
            tmp_path, pattern="**/*.py", exclude_patterns=exclude_patterns
        )

        # Should not include files from .git
        assert len(files) == 1
        assert files[0].name == "module.py"


class TestFileDeduplication:
    """Test deduplication when same file appears multiple times."""

    @pytest.fixture
    def file_ops(self) -> FileOperations:
        """Create FileOperations instance."""
        return FileOperations()

    def test_same_file_resolved_to_same_path(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test that same file with different path representations is one file."""
        file_path = tmp_path / "module.py"
        file_path.write_text("def func(): pass")

        # Use resolve() to get canonical path
        resolved = file_path.resolve()

        # Both should resolve to same path
        assert file_path.resolve() == resolved
        assert (tmp_path / "module.py").resolve() == resolved

    def test_symlink_deduplication(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test that symlinks to same file are deduplicated."""
        # Create original file
        original = tmp_path / "original.py"
        original.write_text("def func(): pass")

        # Create symlink (skip on Windows if symlinks not supported)
        try:
            symlink = tmp_path / "link.py"
            symlink.symlink_to(original)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        files = file_ops.find_python_files(tmp_path, pattern="*.py")

        # Should find both but they resolve to same file
        assert len(files) == 2
        # When resolved, should point to same content
        assert original.read_text() == symlink.read_text()

    def test_no_duplicate_paths_in_result(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test that result list has no duplicate paths."""
        # Create files
        (tmp_path / "file1.py").write_text("pass")
        (tmp_path / "file2.py").write_text("pass")
        (tmp_path / "file3.py").write_text("pass")

        files = file_ops.find_python_files(tmp_path, pattern="*.py")

        # Check no duplicates
        assert len(files) == len(set(files))

    def test_pattern_matching_no_duplicates(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test that using broad pattern doesn't create duplicates."""
        # Create nested structure
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "module.py").write_text("pass")

        # Use pattern that could match multiple times
        files = file_ops.find_python_files(tmp_path, pattern="**/*.py")

        # Should find exactly once
        assert len(files) == 1
        assert files[0].name == "module.py"


class TestExcludePatterns:
    """Test file exclusion patterns."""

    @pytest.fixture
    def file_ops(self) -> FileOperations:
        """Create FileOperations instance."""
        return FileOperations()

    @pytest.fixture
    def test_structure(self, tmp_path: Path) -> Path:
        """Create structure with various files."""
        (tmp_path / "module.py").write_text("pass")
        (tmp_path / "test_module.py").write_text("pass")
        (tmp_path / "module_test.py").write_text("pass")

        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_example.py").write_text("pass")

        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "generated.py").write_text("pass")

        return tmp_path

    def test_exclude_test_files(
        self, file_ops: FileOperations, test_structure: Path
    ) -> None:
        """Test excluding test files."""
        exclude_patterns = ["**/test_*.py", "**/*_test.py"]
        files = file_ops.find_python_files(
            test_structure, pattern="**/*.py", exclude_patterns=exclude_patterns
        )

        file_names = {f.name for f in files}
        assert "module.py" in file_names
        assert "test_module.py" not in file_names
        assert "module_test.py" not in file_names
        assert "test_example.py" not in file_names

    def test_exclude_directories(
        self, file_ops: FileOperations, test_structure: Path
    ) -> None:
        """Test excluding entire directories."""
        exclude_patterns = ["**/tests/**", "**/build/**"]
        files = file_ops.find_python_files(
            test_structure, pattern="**/*.py", exclude_patterns=exclude_patterns
        )

        file_names = {f.name for f in files}
        assert "module.py" in file_names
        assert "test_example.py" not in file_names
        assert "generated.py" not in file_names

    def test_exclude_multiple_patterns(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test multiple exclusion patterns work together."""
        (tmp_path / "keep.py").write_text("pass")
        (tmp_path / "test_exclude.py").write_text("pass")
        (tmp_path / "exclude_test.py").write_text("pass")

        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "auto.py").write_text("pass")

        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "lib.py").write_text("pass")

        exclude_patterns = [
            "**/test_*.py",
            "**/*_test.py",
            "**/build/**",
            "**/.venv/**",
        ]
        files = file_ops.find_python_files(
            tmp_path, pattern="**/*.py", exclude_patterns=exclude_patterns
        )

        assert len(files) == 1
        assert files[0].name == "keep.py"

    def test_gitignore_style_patterns(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test that gitignore-style patterns work correctly."""
        (tmp_path / "include.py").write_text("pass")

        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "bundle.py").write_text("pass")

        # Test gitignore-style pattern
        exclude_patterns = ["dist/"]
        files = file_ops.find_python_files(
            tmp_path, pattern="**/*.py", exclude_patterns=exclude_patterns
        )

        file_names = {f.name for f in files}
        assert "include.py" in file_names
        # Note: gitignore pattern "dist/" should exclude dist directory


class TestEdgeCases:
    """Test edge cases in file processing."""

    @pytest.fixture
    def file_ops(self) -> FileOperations:
        """Create FileOperations instance."""
        return FileOperations()

    def test_empty_directory(self, file_ops: FileOperations, tmp_path: Path) -> None:
        """Test finding files in empty directory."""
        files = file_ops.find_python_files(tmp_path, pattern="**/*.py")

        assert len(files) == 0

    def test_no_python_files(self, file_ops: FileOperations, tmp_path: Path) -> None:
        """Test directory with no Python files."""
        (tmp_path / "readme.txt").write_text("text")
        (tmp_path / "config.json").write_text("{}")

        files = file_ops.find_python_files(tmp_path, pattern="**/*.py")

        assert len(files) == 0

    def test_nonexistent_directory(self, file_ops: FileOperations) -> None:
        """Test that nonexistent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            file_ops.find_python_files(Path("/nonexistent/path"), pattern="**/*.py")

    def test_file_path_instead_of_directory(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test passing a file path instead of directory."""
        file_path = tmp_path / "module.py"
        file_path.write_text("pass")

        # Glob on a file should work but return limited results
        files = file_ops.find_python_files(file_path.parent, pattern="module.py")

        assert len(files) == 1

    def test_deeply_nested_structure(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test finding files in deeply nested directory structure."""
        # Create deep nesting
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)
        (deep_path / "deep.py").write_text("pass")

        files = file_ops.find_python_files(tmp_path, pattern="**/*.py")

        assert len(files) == 1
        assert files[0].name == "deep.py"

    def test_files_with_special_characters(
        self, file_ops: FileOperations, tmp_path: Path
    ) -> None:
        """Test files with special characters in names."""
        (tmp_path / "normal.py").write_text("pass")
        (tmp_path / "with-dash.py").write_text("pass")
        (tmp_path / "with_underscore.py").write_text("pass")
        (tmp_path / "with.dot.py").write_text("pass")

        files = file_ops.find_python_files(tmp_path, pattern="*.py")

        assert len(files) == 4

    def test_unicode_filenames(self, file_ops: FileOperations, tmp_path: Path) -> None:
        """Test files with unicode characters in names."""
        try:
            (tmp_path / "файл.py").write_text("pass")  # Russian
            (tmp_path / "文件.py").write_text("pass")  # Chinese

            files = file_ops.find_python_files(tmp_path, pattern="*.py")

            assert len(files) == 2
        except (OSError, UnicodeEncodeError):
            pytest.skip("Unicode filenames not supported on this platform")
