"""File operations utilities for docpilot.

This module provides utilities for finding, filtering, and modifying
Python source files safely.
"""

from __future__ import annotations

import ast
import difflib
import shutil
from pathlib import Path

import pathspec
import structlog

logger = structlog.get_logger(__name__)


class FileOperations:
    """Utilities for file operations.

    Attributes:
        backup_suffix: Suffix for backup files
        dry_run: If True, don't actually modify files
    """

    def __init__(
        self,
        backup_suffix: str = ".bak",
        dry_run: bool = False,
    ) -> None:
        """Initialize file operations.

        Args:
            backup_suffix: Suffix for backup files
            dry_run: If True, simulate operations without modifying files
        """
        self.backup_suffix = backup_suffix
        self.dry_run = dry_run
        self._log = logger.bind(component="file_ops")

    def find_python_files(
        self,
        root_path: Path,
        pattern: str = "**/*.py",
        exclude_patterns: list[str] | None = None,
    ) -> list[Path]:
        """Find Python files matching pattern, excluding specified patterns.

        Args:
            root_path: Root directory to search
            pattern: Glob pattern for files to include
            exclude_patterns: Patterns to exclude (gitignore-style)

        Returns:
            List of matching Python file paths
        """
        root_path = Path(root_path).resolve()

        if not root_path.exists():
            raise FileNotFoundError(f"Path not found: {root_path}")

        # Find all files matching pattern
        all_files = list(root_path.glob(pattern))

        # Apply exclusions
        if exclude_patterns:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)
            filtered_files = [
                f
                for f in all_files
                if not spec.match_file(str(f.relative_to(root_path)))
            ]
        else:
            filtered_files = all_files

        self._log.info(
            "files_found",
            total=len(all_files),
            filtered=len(filtered_files),
            excluded=len(all_files) - len(filtered_files),
        )

        return sorted(filtered_files)

    def backup_file(self, file_path: Path) -> Path:
        """Create a backup of a file.

        Args:
            file_path: File to backup

        Returns:
            Path to backup file

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        backup_path = file_path.with_suffix(file_path.suffix + self.backup_suffix)

        if self.dry_run:
            self._log.info("dry_run_backup", file=str(file_path))
            return backup_path

        shutil.copy2(file_path, backup_path)
        self._log.info(
            "file_backed_up", original=str(file_path), backup=str(backup_path)
        )

        return backup_path

    def restore_backup(self, file_path: Path) -> None:
        """Restore a file from its backup.

        Args:
            file_path: Original file path

        Raises:
            FileNotFoundError: If backup doesn't exist
        """
        file_path = Path(file_path)
        backup_path = file_path.with_suffix(file_path.suffix + self.backup_suffix)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")

        if self.dry_run:
            self._log.info("dry_run_restore", file=str(file_path))
            return

        shutil.copy2(backup_path, file_path)
        self._log.info("file_restored", file=str(file_path))

    def remove_backup(self, file_path: Path) -> None:
        """Remove backup file if it exists.

        Args:
            file_path: Original file path
        """
        file_path = Path(file_path)
        backup_path = file_path.with_suffix(file_path.suffix + self.backup_suffix)

        if backup_path.exists():
            if not self.dry_run:
                backup_path.unlink()
            self._log.info("backup_removed", backup=str(backup_path))

    def insert_docstring(
        self,
        file_path: Path,
        element_name: str,
        docstring: str,
        parent_class: str | None = None,
    ) -> bool:
        """Insert or replace a docstring in a Python file.

        Args:
            file_path: Path to Python file
            element_name: Name of function/class to document
            docstring: Docstring content to insert
            parent_class: Parent class name if documenting a method

        Returns:
            True if file was modified, False otherwise

        Raises:
            FileNotFoundError: If file doesn't exist
            SyntaxError: If file has invalid Python syntax
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read original content
        original_content = file_path.read_text(encoding="utf-8")

        # Parse AST
        try:
            tree = ast.parse(original_content)
        except SyntaxError as e:
            self._log.error("syntax_error", file=str(file_path), error=str(e))
            raise

        # Find the target element
        target_node = self._find_node(tree, element_name, parent_class)

        if not target_node:
            self._log.warning(
                "element_not_found",
                file=str(file_path),
                element=element_name,
                parent=parent_class,
            )
            return False

        # Generate modified content
        modified_content = self._insert_docstring_at_node(
            original_content, target_node, docstring
        )

        if modified_content == original_content:
            self._log.debug("no_changes", file=str(file_path))
            return False

        # Write modified content
        if not self.dry_run:
            file_path.write_text(modified_content, encoding="utf-8")
            self._log.info(
                "docstring_inserted", file=str(file_path), element=element_name
            )
        else:
            self._log.info(
                "dry_run_insert",
                file=str(file_path),
                element=element_name,
            )

        return True

    def _find_node(
        self,
        tree: ast.AST,
        element_name: str,
        parent_class: str | None = None,
    ) -> ast.AST | None:
        """Find a node in the AST by name.

        Args:
            tree: AST tree
            element_name: Element name to find
            parent_class: Parent class name if looking for a method

        Returns:
            AST node if found, None otherwise
        """
        if parent_class:
            # Find method within class
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == parent_class:
                    for item in node.body:
                        if (
                            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and item.name == element_name
                        ):
                            return item
            return None
        else:
            # Find top-level function or class
            # Use ast.Module body to avoid nested elements
            if isinstance(tree, ast.Module):
                for node in tree.body:
                    if (
                        isinstance(
                            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                        )
                        and node.name == element_name
                    ):
                        return node

        return None

    def _insert_docstring_at_node(
        self,
        source_code: str,
        node: ast.AST,
        docstring: str,
    ) -> str:
        """Insert docstring at a specific node.

        Args:
            source_code: Original source code
            node: AST node where docstring should be inserted
            docstring: Docstring content

        Returns:
            Modified source code
        """
        lines = source_code.splitlines(keepends=True)

        # Determine indentation
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Get indentation from the line after def/class
            def_line_idx = node.lineno - 1
            if def_line_idx + 1 < len(lines):
                next_line = lines[def_line_idx + 1]
                indent = len(next_line) - len(next_line.lstrip())
            else:
                indent = 4
        else:
            indent = 4

        indent_str = " " * indent

        # Format docstring
        formatted_docstring = self._format_docstring_for_insertion(
            docstring, indent_str
        )

        # Find insertion point - lineno attribute exists on all statement nodes
        insert_line = getattr(node, "lineno", 1)  # Line after def/class

        # Check if existing docstring
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            existing_docstring = ast.get_docstring(node)
            if existing_docstring:
                # Find and replace existing docstring
                # Look for the docstring in the lines
                for i in range(insert_line, min(insert_line + 10, len(lines))):
                    if '"""' in lines[i] or "'''" in lines[i]:
                        # Found start of docstring, find end
                        quote = '"""' if '"""' in lines[i] else "'''"
                        end_line = i
                        if lines[i].count(quote) >= 2:
                            # Single line docstring
                            end_line = i
                        else:
                            # Multi-line docstring
                            for j in range(i + 1, len(lines)):
                                if quote in lines[j]:
                                    end_line = j
                                    break

                        # Replace lines
                        new_lines = (
                            lines[:i] + [formatted_docstring] + lines[end_line + 1 :]
                        )
                        return "".join(new_lines)

        # No existing docstring, insert new one
        new_lines = lines[:insert_line] + [formatted_docstring] + lines[insert_line:]

        return "".join(new_lines)

    def _format_docstring_for_insertion(self, docstring: str, indent: str) -> str:
        """Format docstring for insertion into source code.

        Args:
            docstring: Docstring content
            indent: Indentation string

        Returns:
            Formatted docstring with quotes and indentation
        """
        # Split into lines
        lines = docstring.strip().splitlines()

        if len(lines) == 1:
            # Single line docstring
            return f'{indent}"""{lines[0]}"""\n'

        # Multi-line docstring
        result_lines = [f'{indent}"""']
        for line in lines:
            if line.strip():
                result_lines.append(f"{indent}{line}")
            else:
                result_lines.append("")
        result_lines.append(f'{indent}"""\n')

        return "\n".join(result_lines)

    def generate_diff(
        self,
        file_path: Path,
        original_content: str,
        modified_content: str,
    ) -> str:
        """Generate a unified diff between original and modified content.

        Args:
            file_path: File being modified
            original_content: Original file content
            modified_content: Modified file content

        Returns:
            Unified diff as string
        """
        original_lines = original_content.splitlines(keepends=True)
        modified_lines = modified_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{file_path.name}",
            tofile=f"b/{file_path.name}",
        )

        return "".join(diff)


def find_python_files(
    root_path: Path | str,
    pattern: str = "**/*.py",
    exclude_patterns: list[str] | None = None,
) -> list[Path]:
    """Convenience function to find Python files.

    Args:
        root_path: Root directory to search
        pattern: Glob pattern for files
        exclude_patterns: Patterns to exclude

    Returns:
        List of Python file paths
    """
    ops = FileOperations()
    return ops.find_python_files(Path(root_path), pattern, exclude_patterns)


def backup_file(file_path: Path | str) -> Path:
    """Convenience function to backup a file.

    Args:
        file_path: File to backup

    Returns:
        Path to backup file
    """
    ops = FileOperations()
    return ops.backup_file(Path(file_path))
