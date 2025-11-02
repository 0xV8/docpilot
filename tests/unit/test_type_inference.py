"""Unit tests for type inference module.

Tests the TypeInferencer class and its ability to infer types from
code patterns, default values, usage, and naming conventions.
"""

import ast

import pytest

from docpilot.core.type_inference import (
    ConfidenceLevel,
    InferredType,
    TypeInferencer,
    infer_param_type,
    infer_return_type,
)


class TestInferredType:
    """Tests for InferredType container class."""

    def test_inferred_type_creation(self):
        """Test creating an InferredType instance."""
        inferred = InferredType(
            "str",
            ConfidenceLevel.HIGH,
            "default_value",
            ["int", "bytes"]
        )

        assert inferred.type_string == "str"
        assert inferred.confidence == ConfidenceLevel.HIGH
        assert inferred.source == "default_value"
        assert inferred.alternatives == ["int", "bytes"]

    def test_inferred_type_str_representation(self):
        """Test string representation returns type string."""
        inferred = InferredType("int", ConfidenceLevel.MEDIUM, "usage")
        assert str(inferred) == "int"

    def test_inferred_type_repr(self):
        """Test detailed representation includes confidence."""
        inferred = InferredType("list", ConfidenceLevel.LOW, "name")
        assert "list" in repr(inferred)
        assert "low" in repr(inferred)


class TestReturnTypeInference:
    """Tests for return type inference from return statements."""

    def test_infer_return_type_single_string_literal(self):
        """Test inferring return type from single string return."""
        code = """
def get_name():
    return "John Doe"
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        assert result.type_string == "str"
        assert result.confidence == ConfidenceLevel.HIGH
        assert "consistent" in result.source

    def test_infer_return_type_single_int_literal(self):
        """Test inferring return type from single int return."""
        code = """
def get_count():
    return 42
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        assert result.type_string == "int"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_return_type_list_literal(self):
        """Test inferring return type from list literal."""
        code = """
def get_items():
    return [1, 2, 3]
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        assert result.type_string == "list[int]"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_return_type_dict_literal(self):
        """Test inferring return type from dict literal."""
        code = """
def get_config():
    return {"key": "value"}
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        assert result.type_string == "dict[str, str]"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_return_type_no_return(self):
        """Test inferring None for functions without return."""
        code = """
def do_something():
    print("hello")
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        assert result.type_string == "None"
        assert result.confidence == ConfidenceLevel.HIGH
        assert "no_return" in result.source

    def test_infer_return_type_multiple_same_type(self):
        """Test inferring return type when multiple returns have same type."""
        code = """
def get_message(status):
    if status:
        return "success"
    else:
        return "failure"
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        assert result.type_string == "str"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_return_type_optional_pattern(self):
        """Test inferring Optional type when None is one return."""
        code = """
def find_user(user_id):
    if user_id > 0:
        return {"id": user_id}
    return None
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        # Should detect Optional/Union pattern
        assert "None" in result.type_string
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_infer_return_type_union_types(self):
        """Test inferring union type for multiple different types."""
        code = """
def get_value(key):
    if key == "count":
        return 42
    elif key == "name":
        return "test"
    else:
        return True
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        # Should detect multiple types
        assert "|" in result.type_string or "Union" in result.type_string
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_infer_return_type_numeric_union(self):
        """Test inferring float for mixed int/float returns."""
        code = """
def calculate(x):
    if x > 0:
        return 42
    else:
        return 3.14
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        assert result.type_string == "float"
        assert result.confidence == ConfidenceLevel.MEDIUM


class TestParameterTypeInference:
    """Tests for parameter type inference."""

    def test_infer_param_type_from_int_default(self):
        """Test inferring int type from default value."""
        code = """
def foo(x=0):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]
        default = func_node.args.defaults[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, default)

        assert result.type_string == "int"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_param_type_from_string_default(self):
        """Test inferring str type from default value."""
        code = """
def greet(name="World"):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]
        default = func_node.args.defaults[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, default)

        assert result.type_string == "str"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_param_type_from_list_default(self):
        """Test inferring list type from default value."""
        code = """
def process(items=[]):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]
        default = func_node.args.defaults[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, default)

        assert result.type_string == "list"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_param_type_from_dict_default(self):
        """Test inferring dict type from default value."""
        code = """
def configure(options={}):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]
        default = func_node.args.defaults[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, default)

        assert result.type_string == "dict"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_param_type_from_isinstance_check(self):
        """Test inferring type from isinstance check in function body."""
        code = """
def process(data):
    if isinstance(data, str):
        return data.upper()
    return None
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, func_node.body)

        assert result.type_string == "str"
        assert result.confidence == ConfidenceLevel.HIGH
        assert "isinstance" in result.source

    def test_infer_param_type_from_isinstance_union(self):
        """Test inferring union type from isinstance with tuple."""
        code = """
def process(value):
    if isinstance(value, (int, float)):
        return value * 2
    return 0
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, func_node.body)

        # Should detect union of int and float
        assert "int" in result.type_string
        assert "float" in result.type_string
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_param_type_from_string_method_usage(self):
        """Test inferring str type from string method usage."""
        code = """
def capitalize_name(name):
    return name.upper().strip()
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, func_node.body)

        assert result.type_string == "str"
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_infer_param_type_from_list_method_usage(self):
        """Test inferring list type from list method usage."""
        code = """
def add_item(items, item):
    items.append(item)
    return items
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, func_node.body)

        assert result.type_string == "list"
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_infer_param_type_from_dict_method_usage(self):
        """Test inferring dict type from dict method usage."""
        code = """
def get_value(data, key):
    return data.get(key, None)
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, func_node.body)

        assert result.type_string == "dict"
        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_infer_param_type_from_name_convention_id(self):
        """Test inferring int type from _id suffix."""
        code = """
def find_by_id(user_id):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, None)

        assert result.type_string == "int"
        assert result.confidence == ConfidenceLevel.LOW
        assert "name_convention" in result.source

    def test_infer_param_type_from_name_convention_bool(self):
        """Test inferring bool type from is_ prefix."""
        code = """
def check_status(is_active):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, None)

        assert result.type_string == "bool"
        assert result.confidence == ConfidenceLevel.LOW

    def test_infer_param_type_from_name_convention_list(self):
        """Test inferring list type from plural name."""
        code = """
def process_items(items):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, None)

        assert result.type_string == "list"
        assert result.confidence == ConfidenceLevel.LOW


class TestExpressionInference:
    """Tests for inferring types from expressions."""

    def test_infer_from_constant_bool(self):
        """Test inferring bool from True/False."""
        inferencer = TypeInferencer()

        true_expr = ast.Constant(value=True)
        result = inferencer.infer_from_usage(true_expr)
        assert result.type_string == "bool"

    def test_infer_from_constant_none(self):
        """Test inferring None type."""
        inferencer = TypeInferencer()

        none_expr = ast.Constant(value=None)
        result = inferencer.infer_from_usage(none_expr)
        assert result.type_string == "None"

    def test_infer_from_list_comprehension(self):
        """Test inferring list type from list comprehension."""
        code = "[x * 2 for x in range(10)]"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string.startswith("list")
        assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_infer_from_dict_comprehension(self):
        """Test inferring dict type from dict comprehension."""
        code = "{k: v for k, v in items}"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string.startswith("dict")
        assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_infer_from_set_literal(self):
        """Test inferring set type from set literal."""
        code = "{1, 2, 3}"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "set"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_tuple_literal(self):
        """Test inferring tuple type from tuple literal."""
        code = "(1, 'two', 3.0)"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string.startswith("tuple")
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_comparison(self):
        """Test inferring bool from comparison."""
        code = "x > 5"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "bool"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_bool_operation(self):
        """Test inferring bool from boolean operation."""
        code = "x and y"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "bool"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_arithmetic_int(self):
        """Test inferring int from arithmetic on ints."""
        code = "5 + 3"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "int"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_arithmetic_float(self):
        """Test inferring float from arithmetic with float."""
        code = "5.0 + 3"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "float"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_string_concat(self):
        """Test inferring str from string concatenation."""
        code = "'hello' + ' world'"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "str"
        assert result.confidence == ConfidenceLevel.HIGH


class TestBuiltinFunctionCalls:
    """Tests for inferring types from builtin function calls."""

    def test_infer_from_len_call(self):
        """Test inferring int from len() call."""
        code = "len(items)"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "int"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_str_constructor(self):
        """Test inferring str from str() constructor."""
        code = "str(value)"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "str"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_list_constructor(self):
        """Test inferring list from list() constructor."""
        code = "list(items)"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "list"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_sorted_call(self):
        """Test inferring list from sorted() call."""
        code = "sorted(items)"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "list"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_isinstance_call(self):
        """Test inferring bool from isinstance() call."""
        code = "isinstance(obj, str)"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        assert result.type_string == "bool"
        assert result.confidence == ConfidenceLevel.HIGH


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_infer_return_type_convenience_function(self):
        """Test the infer_return_type convenience function."""
        code = """
def get_name():
    return "test"
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        result = infer_return_type(func_node)

        assert result.type_string == "str"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_param_type_convenience_function(self):
        """Test the infer_param_type convenience function."""
        code = """
def process(count=0):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]
        default = func_node.args.defaults[0]

        result = infer_param_type(param, default)

        assert result.type_string == "int"
        assert result.confidence == ConfidenceLevel.HIGH


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_infer_param_type_no_hints_no_usage(self):
        """Test inferring type with no hints, no usage, generic name."""
        code = """
def process(x):
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]
        param = func_node.args.args[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_param_type(param, None, func_node.body)

        # Should fall back to Any
        assert result.type_string == "Any"
        assert result.confidence == ConfidenceLevel.UNKNOWN

    def test_infer_return_type_empty_function(self):
        """Test inferring return type for empty function."""
        code = """
def empty():
    pass
"""
        tree = ast.parse(code)
        func_node = tree.body[0]

        inferencer = TypeInferencer()
        result = inferencer.infer_return_type(func_node)

        assert result.type_string == "None"
        assert result.confidence == ConfidenceLevel.HIGH

    def test_infer_from_complex_nested_expression(self):
        """Test inferring type from complex nested expression."""
        code = "[[x * 2 for x in range(5)] for _ in range(3)]"
        expr = ast.parse(code, mode="eval").body

        inferencer = TypeInferencer()
        result = inferencer.infer_from_usage(expr)

        # Should infer nested list
        assert result.type_string.startswith("list")
        assert result.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_confidence_levels_are_correct(self):
        """Test that confidence levels are appropriate for different sources."""
        inferencer = TypeInferencer()

        # High confidence: explicit literal
        code_high = "42"
        expr_high = ast.parse(code_high, mode="eval").body
        result_high = inferencer.infer_from_usage(expr_high)
        assert result_high.confidence == ConfidenceLevel.HIGH

        # Medium confidence: function call
        code_med = "len(items)"
        expr_med = ast.parse(code_med, mode="eval").body
        result_med = inferencer.infer_from_usage(expr_med)
        assert result_med.confidence == ConfidenceLevel.HIGH  # len is builtin

        # Low confidence: name inference
        code_low = """
def foo(count):
    pass
"""
        tree = ast.parse(code_low)
        func_node = tree.body[0]
        param = func_node.args.args[0]
        result_low = inferencer.infer_param_type(param, None, None)
        assert result_low.confidence == ConfidenceLevel.LOW


class TestIntegrationWithParser:
    """Integration tests to verify type inference works with parser."""

    def test_parser_integration_basic(self):
        """Test that type inference integrates properly with parser."""
        # This test would require importing the parser
        # and verifying the full integration works
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
