"""Unit tests for file_ops module.

This module tests the FileOperations class, particularly focusing on
the critical method insertion functionality.
"""

import ast
import tempfile
from pathlib import Path

import pytest

from docpilot.utils.file_ops import FileOperations


class TestFileOperations:
    """Test suite for FileOperations class."""

    def test_find_node_top_level_function(self):
        """Test finding a top-level function."""
        source = '''
def my_function():
    pass
'''
        tree = ast.parse(source)
        file_ops = FileOperations()

        node = file_ops._find_node(tree, "my_function", parent_class=None)

        assert node is not None
        assert isinstance(node, ast.FunctionDef)
        assert node.name == "my_function"

    def test_find_node_top_level_class(self):
        """Test finding a top-level class."""
        source = '''
class MyClass:
    pass
'''
        tree = ast.parse(source)
        file_ops = FileOperations()

        node = file_ops._find_node(tree, "MyClass", parent_class=None)

        assert node is not None
        assert isinstance(node, ast.ClassDef)
        assert node.name == "MyClass"

    def test_find_node_method_in_class(self):
        """Test finding a method inside a class.

        This is the critical bug fix test - methods were not being found
        when parent_class was provided.
        """
        source = '''
class Calculator:
    """Calculator class."""

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
'''
        tree = ast.parse(source)
        file_ops = FileOperations()

        # Test finding subtract method
        node = file_ops._find_node(tree, "subtract", parent_class="Calculator")

        assert node is not None, "Failed to find method 'subtract' in class 'Calculator'"
        assert isinstance(node, ast.FunctionDef)
        assert node.name == "subtract"

        # Test finding add method
        node = file_ops._find_node(tree, "add", parent_class="Calculator")

        assert node is not None, "Failed to find method 'add' in class 'Calculator'"
        assert isinstance(node, ast.FunctionDef)
        assert node.name == "add"

    def test_find_node_async_method(self):
        """Test finding an async method inside a class."""
        source = '''
class AsyncHandler:
    async def process(self, data):
        return data
'''
        tree = ast.parse(source)
        file_ops = FileOperations()

        node = file_ops._find_node(tree, "process", parent_class="AsyncHandler")

        assert node is not None
        assert isinstance(node, ast.AsyncFunctionDef)
        assert node.name == "process"

    def test_find_node_method_not_found(self):
        """Test that None is returned when method doesn't exist."""
        source = '''
class MyClass:
    def existing_method(self):
        pass
'''
        tree = ast.parse(source)
        file_ops = FileOperations()

        node = file_ops._find_node(tree, "nonexistent_method", parent_class="MyClass")

        assert node is None

    def test_find_node_class_not_found(self):
        """Test that None is returned when parent class doesn't exist."""
        source = '''
class MyClass:
    def my_method(self):
        pass
'''
        tree = ast.parse(source)
        file_ops = FileOperations()

        node = file_ops._find_node(tree, "my_method", parent_class="NonexistentClass")

        assert node is None

    def test_insert_docstring_for_method(self):
        """Test inserting a docstring for a method inside a class.

        This is the end-to-end test for the bug fix.
        """
        source = '''"""Module docstring."""

class Calculator:
    """Calculator class."""

    def subtract(self, a, b):
        return a - b
'''
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source)
            temp_path = Path(f.name)

        try:
            file_ops = FileOperations(dry_run=False)

            # Insert docstring for subtract method
            success = file_ops.insert_docstring(
                file_path=temp_path,
                element_name="subtract",
                docstring="Subtract b from a.",
                parent_class="Calculator"
            )

            assert success, "insert_docstring should return True"

            # Verify the docstring was inserted
            modified_content = temp_path.read_text(encoding='utf-8')

            assert 'def subtract(self, a, b):' in modified_content
            assert '"""Subtract b from a."""' in modified_content

            # Verify the original class docstring is still there
            assert '"""Calculator class."""' in modified_content

        finally:
            # Clean up
            temp_path.unlink()

    def test_insert_docstring_multiple_methods(self):
        """Test inserting docstrings for multiple methods in the same class."""
        source = '''class Calculator:
    """Calculator class."""

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b
'''
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source)
            temp_path = Path(f.name)

        try:
            file_ops = FileOperations(dry_run=False)

            # Insert docstring for each method
            methods = [
                ("add", "Add two numbers."),
                ("subtract", "Subtract b from a."),
                ("multiply", "Multiply two numbers.")
            ]

            for method_name, docstring in methods:
                success = file_ops.insert_docstring(
                    file_path=temp_path,
                    element_name=method_name,
                    docstring=docstring,
                    parent_class="Calculator"
                )
                assert success, f"Failed to insert docstring for {method_name}"

            # Verify all docstrings were inserted
            modified_content = temp_path.read_text(encoding='utf-8')

            assert '"""Add two numbers."""' in modified_content
            assert '"""Subtract b from a."""' in modified_content
            assert '"""Multiply two numbers."""' in modified_content

        finally:
            # Clean up
            temp_path.unlink()

    def test_insert_docstring_overwrite_existing(self):
        """Test that existing docstrings are replaced."""
        source = '''class Calculator:
    """Calculator class."""

    def add(self, a, b):
        """Old docstring."""
        return a + b
'''
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source)
            temp_path = Path(f.name)

        try:
            file_ops = FileOperations(dry_run=False)

            # Insert new docstring
            success = file_ops.insert_docstring(
                file_path=temp_path,
                element_name="add",
                docstring="New docstring for add method.",
                parent_class="Calculator"
            )

            assert success

            # Verify the new docstring replaced the old one
            modified_content = temp_path.read_text(encoding='utf-8')

            assert '"""New docstring for add method."""' in modified_content
            assert '"""Old docstring."""' not in modified_content

        finally:
            # Clean up
            temp_path.unlink()

    def test_insert_docstring_nested_classes(self):
        """Test finding methods in nested classes (should only find in direct parent)."""
        source = '''class OuterClass:
    """Outer class."""

    class InnerClass:
        """Inner class."""

        def inner_method(self):
            pass

    def outer_method(self):
        pass
'''
        tree = ast.parse(source)
        file_ops = FileOperations()

        # Should find outer_method in OuterClass
        node = file_ops._find_node(tree, "outer_method", parent_class="OuterClass")
        assert node is not None
        assert node.name == "outer_method"

        # Should find inner_method in InnerClass
        node = file_ops._find_node(tree, "inner_method", parent_class="InnerClass")
        assert node is not None
        assert node.name == "inner_method"

        # Should NOT find inner_method in OuterClass
        node = file_ops._find_node(tree, "inner_method", parent_class="OuterClass")
        assert node is None

    def test_insert_docstring_dry_run(self):
        """Test that dry-run mode doesn't modify files."""
        source = '''class Calculator:
    def add(self, a, b):
        return a + b
'''
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source)
            temp_path = Path(f.name)

        try:
            file_ops = FileOperations(dry_run=True)

            # Try to insert docstring in dry-run mode
            success = file_ops.insert_docstring(
                file_path=temp_path,
                element_name="add",
                docstring="Add two numbers.",
                parent_class="Calculator"
            )

            assert success

            # Verify file wasn't modified
            modified_content = temp_path.read_text(encoding='utf-8')
            assert modified_content == source

        finally:
            # Clean up
            temp_path.unlink()

    def test_find_node_does_not_find_nested_functions(self):
        """Test that top-level search doesn't return nested functions."""
        source = '''def outer_function():
    def inner_function():
        pass
    return inner_function

def top_level_function():
    pass
'''
        tree = ast.parse(source)
        file_ops = FileOperations()

        # Should find top-level function
        node = file_ops._find_node(tree, "top_level_function", parent_class=None)
        assert node is not None
        assert node.name == "top_level_function"

        # Should find outer function
        node = file_ops._find_node(tree, "outer_function", parent_class=None)
        assert node is not None
        assert node.name == "outer_function"

        # Should NOT find inner function as top-level
        node = file_ops._find_node(tree, "inner_function", parent_class=None)
        assert node is None
