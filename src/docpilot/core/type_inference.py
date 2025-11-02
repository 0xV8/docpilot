"""Advanced type inference system for Python code without type hints.

This module provides comprehensive type inference capabilities by analyzing
code patterns, usage contexts, and AST structures to infer types when
explicit type hints are missing. This is particularly useful for legacy
codebases and dynamically typed Python code.
"""

from __future__ import annotations

import ast
import builtins
from collections import defaultdict
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ConfidenceLevel(str, Enum):
    """Confidence level for inferred types.

    Represents how confident we are about an inferred type based on
    the analysis method and available evidence.
    """

    HIGH = "high"           # Explicit type hints or obvious patterns
    MEDIUM = "medium"       # Inferred from clear usage patterns
    LOW = "low"             # Guessed from naming conventions
    UNKNOWN = "unknown"     # Unable to infer


class InferredType:
    """Container for an inferred type with metadata.

    Attributes:
        type_string: The inferred type as a string (e.g., "str", "List[int]")
        confidence: Confidence level of the inference
        source: Description of how the type was inferred
        alternatives: Other possible types with lower confidence
    """

    def __init__(
        self,
        type_string: str,
        confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN,
        source: str = "unknown",
        alternatives: list[str] | None = None,
    ) -> None:
        """Initialize an inferred type.

        Args:
            type_string: The inferred type as a string
            confidence: Confidence level of the inference
            source: Description of how type was inferred
            alternatives: Other possible types
        """
        self.type_string = type_string
        self.confidence = confidence
        self.source = source
        self.alternatives = alternatives or []

    def __str__(self) -> str:
        """Return string representation of inferred type."""
        return self.type_string

    def __repr__(self) -> str:
        """Return detailed representation including confidence."""
        return f"InferredType('{self.type_string}', {self.confidence.value})"


class TypeInferencer:
    """Advanced type inference engine for Python code.

    This class analyzes AST nodes to infer types through multiple strategies:
    - Analyzing return statements
    - Examining default parameter values
    - Detecting usage patterns (method calls, operators)
    - Recognizing isinstance() checks and type guards
    - Inferring from variable names and patterns

    Attributes:
        _log: Structured logger instance
        _builtin_types: Set of Python builtin type names
    """

    def __init__(self) -> None:
        """Initialize the type inferencer."""
        self._log = logger.bind(component="type_inference")
        self._builtin_types = {
            name for name in dir(builtins)
            if isinstance(getattr(builtins, name), type)
        }

    def infer_return_type(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> InferredType:
        """Infer return type from function return statements.

        Analyzes all return statements in a function to determine the
        most likely return type based on returned values and patterns.

        Args:
            func_node: Function definition AST node

        Returns:
            InferredType with confidence level

        Examples:
            >>> # return "hello" -> str
            >>> # return 42 -> int
            >>> # return [1, 2, 3] -> list
            >>> # return {"key": "value"} -> dict
        """
        self._log.debug("inferring_return_type", function=func_node.name)

        # Extract all return statements
        return_nodes: list[ast.Return] = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value:
                return_nodes.append(node)

        if not return_nodes:
            # No explicit returns found
            return InferredType(
                "None",
                ConfidenceLevel.HIGH,
                "no_return_statements"
            )

        # Analyze each return statement
        inferred_types: list[str] = []
        for ret_node in return_nodes:
            if ret_node.value:
                ret_type = self._infer_from_expression(ret_node.value)
                inferred_types.append(ret_type.type_string)

        # Determine the most common or general return type
        if not inferred_types:
            return InferredType("None", ConfidenceLevel.MEDIUM, "empty_returns")

        # Check if all returns are the same type
        unique_types = list(set(inferred_types))
        if len(unique_types) == 1:
            return InferredType(
                unique_types[0],
                ConfidenceLevel.HIGH,
                "consistent_return_type"
            )

        # Multiple return types - try to find common base or use Union
        if all(t in ("int", "float") for t in unique_types):
            return InferredType(
                "float",
                ConfidenceLevel.MEDIUM,
                "numeric_union"
            )

        # Check if None is one of the return types (Optional pattern)
        if "None" in unique_types:
            non_none_types = [t for t in unique_types if t != "None"]
            if len(non_none_types) == 1:
                return InferredType(
                    f"{non_none_types[0]} | None",
                    ConfidenceLevel.MEDIUM,
                    "optional_pattern",
                    alternatives=[non_none_types[0]]
                )

        # Multiple different types - use Union
        union_str = " | ".join(sorted(unique_types))
        return InferredType(
            union_str,
            ConfidenceLevel.MEDIUM,
            "multiple_return_types",
            alternatives=unique_types
        )

    def infer_param_type(
        self,
        param: ast.arg,
        default: ast.expr | None = None,
        func_body: list[ast.stmt] | None = None
    ) -> InferredType:
        """Infer parameter type from default value or usage patterns.

        Uses multiple strategies to infer parameter types:
        1. Analyze default value if present
        2. Scan function body for isinstance() checks
        3. Analyze how parameter is used (method calls, operations)
        4. Use naming conventions as fallback

        Args:
            param: Parameter AST node
            default: Default value expression if present
            func_body: Function body statements for usage analysis

        Returns:
            InferredType with confidence level

        Examples:
            >>> # def foo(x=0): -> int
            >>> # def foo(name=""): -> str
            >>> # def foo(items=[]): -> list
            >>> # def foo(config=None): -> Any | None
        """
        param_name = param.arg
        self._log.debug("inferring_param_type", parameter=param_name)

        # Strategy 1: Infer from default value
        if default is not None:
            default_type = self._infer_from_expression(default)
            if default_type.confidence != ConfidenceLevel.UNKNOWN:
                # Enhance source information
                default_type.source = f"default_value: {ast.unparse(default)}"
                return default_type

        # Strategy 2: Look for isinstance checks in function body
        if func_body:
            isinstance_type = self._infer_from_isinstance(param_name, func_body)
            if isinstance_type:
                return isinstance_type

        # Strategy 3: Analyze usage patterns in function body
        if func_body:
            usage_type = self._infer_from_usage(param_name, func_body)
            if usage_type.confidence != ConfidenceLevel.UNKNOWN:
                return usage_type

        # Strategy 4: Fallback to naming conventions
        name_type = self._infer_from_name(param_name)
        return name_type

    def infer_from_usage(self, node: ast.AST) -> InferredType:
        """Infer type from how a variable or expression is used.

        Analyzes method calls, attribute access, and operations to
        determine the most likely type.

        Args:
            node: AST node to analyze

        Returns:
            InferredType based on usage patterns

        Examples:
            >>> # x.append() -> List
            >>> # x.keys() -> Dict
            >>> # x.strip() -> str
            >>> # x + 1 -> int or float
        """
        return self._infer_from_expression(node)

    def _infer_from_expression(self, expr: ast.expr) -> InferredType:
        """Infer type from an expression node.

        Args:
            expr: Expression AST node

        Returns:
            InferredType based on expression analysis
        """
        # Literal values
        if isinstance(expr, ast.Constant):
            return self._infer_from_constant(expr)

        # List literal
        if isinstance(expr, ast.List):
            if expr.elts:
                # Try to infer element type
                element_types = [self._infer_from_expression(e) for e in expr.elts[:3]]
                if all(et.type_string == element_types[0].type_string for et in element_types):
                    return InferredType(
                        f"list[{element_types[0].type_string}]",
                        ConfidenceLevel.HIGH,
                        "list_literal"
                    )
            return InferredType("list", ConfidenceLevel.HIGH, "list_literal")

        # Dict literal
        if isinstance(expr, ast.Dict):
            if expr.keys and expr.values:
                # Try to infer key and value types
                key_type = self._infer_from_expression(expr.keys[0])
                val_type = self._infer_from_expression(expr.values[0])
                return InferredType(
                    f"dict[{key_type.type_string}, {val_type.type_string}]",
                    ConfidenceLevel.HIGH,
                    "dict_literal"
                )
            return InferredType("dict", ConfidenceLevel.HIGH, "dict_literal")

        # Set literal
        if isinstance(expr, ast.Set):
            return InferredType("set", ConfidenceLevel.HIGH, "set_literal")

        # Tuple literal
        if isinstance(expr, ast.Tuple):
            if expr.elts:
                element_types = [self._infer_from_expression(e).type_string for e in expr.elts]
                return InferredType(
                    f"tuple[{', '.join(element_types)}]",
                    ConfidenceLevel.HIGH,
                    "tuple_literal"
                )
            return InferredType("tuple", ConfidenceLevel.HIGH, "tuple_literal")

        # List/Dict/Set comprehensions
        if isinstance(expr, ast.ListComp):
            element_type = self._infer_from_expression(expr.elt)
            return InferredType(
                f"list[{element_type.type_string}]",
                ConfidenceLevel.MEDIUM,
                "list_comprehension"
            )

        if isinstance(expr, ast.DictComp):
            key_type = self._infer_from_expression(expr.key)
            val_type = self._infer_from_expression(expr.value)
            return InferredType(
                f"dict[{key_type.type_string}, {val_type.type_string}]",
                ConfidenceLevel.MEDIUM,
                "dict_comprehension"
            )

        if isinstance(expr, ast.SetComp):
            element_type = self._infer_from_expression(expr.elt)
            return InferredType(
                f"set[{element_type.type_string}]",
                ConfidenceLevel.MEDIUM,
                "set_comprehension"
            )

        # Binary operations
        if isinstance(expr, ast.BinOp):
            return self._infer_from_binop(expr)

        # Comparison operations
        if isinstance(expr, ast.Compare):
            return InferredType("bool", ConfidenceLevel.HIGH, "comparison")

        # Boolean operations
        if isinstance(expr, ast.BoolOp):
            return InferredType("bool", ConfidenceLevel.HIGH, "bool_operation")

        # Unary operations
        if isinstance(expr, ast.UnaryOp):
            return self._infer_from_unaryop(expr)

        # Function calls
        if isinstance(expr, ast.Call):
            return self._infer_from_call(expr)

        # Attribute access (method calls handled above)
        if isinstance(expr, ast.Attribute):
            # Can't reliably infer without more context
            return InferredType("Any", ConfidenceLevel.LOW, "attribute_access")

        # Name reference
        if isinstance(expr, ast.Name):
            # Check if it's a known builtin
            if expr.id in self._builtin_types:
                return InferredType(expr.id, ConfidenceLevel.MEDIUM, "builtin_type")
            return self._infer_from_name(expr.id)

        # Lambda
        if isinstance(expr, ast.Lambda):
            return InferredType("Callable", ConfidenceLevel.MEDIUM, "lambda")

        # Generator expression
        if isinstance(expr, ast.GeneratorExp):
            element_type = self._infer_from_expression(expr.elt)
            return InferredType(
                f"Generator[{element_type.type_string}, None, None]",
                ConfidenceLevel.MEDIUM,
                "generator_expression"
            )

        # Default fallback
        return InferredType("Any", ConfidenceLevel.UNKNOWN, "unknown_expression")

    def _infer_from_constant(self, const: ast.Constant) -> InferredType:
        """Infer type from a constant value.

        Args:
            const: Constant AST node

        Returns:
            InferredType based on constant type
        """
        value = const.value

        if value is None:
            return InferredType("None", ConfidenceLevel.HIGH, "none_literal")
        elif isinstance(value, bool):
            return InferredType("bool", ConfidenceLevel.HIGH, "bool_literal")
        elif isinstance(value, int):
            return InferredType("int", ConfidenceLevel.HIGH, "int_literal")
        elif isinstance(value, float):
            return InferredType("float", ConfidenceLevel.HIGH, "float_literal")
        elif isinstance(value, str):
            return InferredType("str", ConfidenceLevel.HIGH, "str_literal")
        elif isinstance(value, bytes):
            return InferredType("bytes", ConfidenceLevel.HIGH, "bytes_literal")
        else:
            return InferredType("Any", ConfidenceLevel.LOW, "unknown_constant")

    def _infer_from_binop(self, binop: ast.BinOp) -> InferredType:
        """Infer type from binary operation.

        Args:
            binop: BinOp AST node

        Returns:
            InferredType based on operation
        """
        left_type = self._infer_from_expression(binop.left)
        right_type = self._infer_from_expression(binop.right)

        # Arithmetic operations
        if isinstance(binop.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
            # If both are numbers, result is number
            if left_type.type_string in ("int", "float") and right_type.type_string in ("int", "float"):
                if left_type.type_string == "float" or right_type.type_string == "float":
                    return InferredType("float", ConfidenceLevel.HIGH, "arithmetic_float")
                return InferredType("int", ConfidenceLevel.HIGH, "arithmetic_int")

            # String concatenation
            if isinstance(binop.op, ast.Add) and left_type.type_string == "str":
                return InferredType("str", ConfidenceLevel.HIGH, "string_concat")

            # List concatenation
            if isinstance(binop.op, ast.Add) and left_type.type_string.startswith("list"):
                return left_type

        # Bitwise operations -> int
        if isinstance(binop.op, (ast.BitOr, ast.BitXor, ast.BitAnd, ast.LShift, ast.RShift)):
            return InferredType("int", ConfidenceLevel.HIGH, "bitwise_operation")

        return InferredType("Any", ConfidenceLevel.LOW, "unknown_binop")

    def _infer_from_unaryop(self, unaryop: ast.UnaryOp) -> InferredType:
        """Infer type from unary operation.

        Args:
            unaryop: UnaryOp AST node

        Returns:
            InferredType based on operation
        """
        operand_type = self._infer_from_expression(unaryop.operand)

        if isinstance(unaryop.op, ast.Not):
            return InferredType("bool", ConfidenceLevel.HIGH, "not_operation")

        if isinstance(unaryop.op, (ast.UAdd, ast.USub)):
            if operand_type.type_string in ("int", "float"):
                return operand_type
            return InferredType("int", ConfidenceLevel.MEDIUM, "unary_arithmetic")

        if isinstance(unaryop.op, ast.Invert):
            return InferredType("int", ConfidenceLevel.HIGH, "bitwise_invert")

        return operand_type

    def _infer_from_call(self, call: ast.Call) -> InferredType:
        """Infer type from function call.

        Args:
            call: Call AST node

        Returns:
            InferredType based on called function
        """
        # Get function name
        func_name = None
        if isinstance(call.func, ast.Name):
            func_name = call.func.id
        elif isinstance(call.func, ast.Attribute):
            func_name = call.func.attr

        if not func_name:
            return InferredType("Any", ConfidenceLevel.LOW, "unknown_call")

        # Common builtin constructors
        type_constructors = {
            "int": "int",
            "float": "float",
            "str": "str",
            "bool": "bool",
            "list": "list",
            "dict": "dict",
            "set": "set",
            "tuple": "tuple",
            "bytes": "bytes",
            "bytearray": "bytearray",
            "frozenset": "frozenset",
        }

        if func_name in type_constructors:
            return InferredType(
                type_constructors[func_name],
                ConfidenceLevel.HIGH,
                f"{func_name}_constructor"
            )

        # Common functions with known return types
        known_returns = {
            "len": "int",
            "range": "range",
            "enumerate": "enumerate",
            "zip": "zip",
            "map": "map",
            "filter": "filter",
            "sorted": "list",
            "reversed": "reversed",
            "open": "TextIOWrapper",
            "abs": "int",
            "max": "Any",
            "min": "Any",
            "sum": "int",
            "all": "bool",
            "any": "bool",
            "isinstance": "bool",
            "issubclass": "bool",
            "callable": "bool",
            "hasattr": "bool",
            "getattr": "Any",
            "setattr": "None",
            "delattr": "None",
            "type": "type",
            "id": "int",
            "hash": "int",
            "ord": "int",
            "chr": "str",
            "hex": "str",
            "oct": "str",
            "bin": "str",
            "format": "str",
            "repr": "str",
            "ascii": "str",
            "input": "str",
            "print": "None",
        }

        if func_name in known_returns:
            return InferredType(
                known_returns[func_name],
                ConfidenceLevel.HIGH,
                f"builtin_{func_name}"
            )

        # String methods that return strings
        string_methods = {
            "strip", "lstrip", "rstrip", "lower", "upper", "title", "capitalize",
            "replace", "join", "format", "center", "ljust", "rjust", "zfill",
            "expandtabs", "translate", "swapcase", "casefold",
        }

        if func_name in string_methods:
            return InferredType("str", ConfidenceLevel.MEDIUM, f"str_method_{func_name}")

        # String methods that return bool
        string_bool_methods = {
            "startswith", "endswith", "isalpha", "isdigit", "isalnum", "isascii",
            "isdecimal", "isnumeric", "isidentifier", "islower", "isupper",
            "isspace", "istitle", "isprintable",
        }

        if func_name in string_bool_methods:
            return InferredType("bool", ConfidenceLevel.MEDIUM, f"str_method_{func_name}")

        # String methods that return int
        if func_name in ("count", "find", "rfind", "index", "rindex"):
            return InferredType("int", ConfidenceLevel.MEDIUM, f"str_method_{func_name}")

        # String methods that return list
        if func_name in ("split", "rsplit", "splitlines", "partition", "rpartition"):
            return InferredType("list[str]", ConfidenceLevel.MEDIUM, f"str_method_{func_name}")

        # List/sequence methods
        if func_name in ("append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse"):
            return InferredType("None", ConfidenceLevel.MEDIUM, f"list_method_{func_name}")

        # Dict methods
        if func_name == "keys":
            return InferredType("dict_keys", ConfidenceLevel.MEDIUM, "dict_keys")
        if func_name == "values":
            return InferredType("dict_values", ConfidenceLevel.MEDIUM, "dict_values")
        if func_name == "items":
            return InferredType("dict_items", ConfidenceLevel.MEDIUM, "dict_items")
        if func_name in ("get", "pop", "popitem", "setdefault", "update", "clear"):
            return InferredType("Any", ConfidenceLevel.LOW, f"dict_method_{func_name}")

        return InferredType("Any", ConfidenceLevel.LOW, "function_call")

    def _infer_from_isinstance(
        self,
        param_name: str,
        func_body: list[ast.stmt]
    ) -> InferredType | None:
        """Infer type from isinstance checks in function body.

        Args:
            param_name: Parameter name to look for
            func_body: Function body statements

        Returns:
            InferredType if isinstance check found, None otherwise
        """
        for node in ast.walk(ast.Module(body=func_body)):
            if isinstance(node, ast.Call):
                # Check if it's an isinstance call
                if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                    if len(node.args) >= 2:
                        # Check if first arg is our parameter
                        if isinstance(node.args[0], ast.Name) and node.args[0].id == param_name:
                            # Extract type from second argument
                            type_arg = node.args[1]
                            if isinstance(type_arg, ast.Name):
                                return InferredType(
                                    type_arg.id,
                                    ConfidenceLevel.HIGH,
                                    "isinstance_check"
                                )
                            elif isinstance(type_arg, ast.Tuple):
                                # Multiple types in isinstance
                                types = []
                                for elt in type_arg.elts:
                                    if isinstance(elt, ast.Name):
                                        types.append(elt.id)
                                if types:
                                    return InferredType(
                                        " | ".join(types),
                                        ConfidenceLevel.HIGH,
                                        "isinstance_union",
                                        alternatives=types
                                    )

        return None

    def _infer_from_usage(
        self,
        param_name: str,
        func_body: list[ast.stmt]
    ) -> InferredType:
        """Infer type from how parameter is used in function body.

        Args:
            param_name: Parameter name to analyze
            func_body: Function body statements

        Returns:
            InferredType based on usage patterns
        """
        # Track method calls on the parameter
        method_calls: set[str] = set()
        operations: set[str] = set()

        for node in ast.walk(ast.Module(body=func_body)):
            # Method calls: param.method()
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == param_name:
                        method_calls.add(node.func.attr)

            # Attribute access: param.attr
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id == param_name:
                    method_calls.add(node.attr)

            # Binary operations
            elif isinstance(node, ast.BinOp):
                if isinstance(node.left, ast.Name) and node.left.id == param_name:
                    operations.add(type(node.op).__name__)
                elif isinstance(node.right, ast.Name) and node.right.id == param_name:
                    operations.add(type(node.op).__name__)

            # Subscript access: param[key]
            elif isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and node.value.id == param_name:
                    operations.add("subscript")

        # Infer based on method calls
        if method_calls:
            # String methods
            if method_calls & {"strip", "lower", "upper", "split", "replace", "startswith", "endswith"}:
                return InferredType("str", ConfidenceLevel.MEDIUM, "string_methods_used")

            # List methods
            if method_calls & {"append", "extend", "pop", "remove", "insert", "index", "count"}:
                return InferredType("list", ConfidenceLevel.MEDIUM, "list_methods_used")

            # Dict methods
            if method_calls & {"keys", "values", "items", "get", "update", "setdefault"}:
                return InferredType("dict", ConfidenceLevel.MEDIUM, "dict_methods_used")

            # Set methods
            if method_calls & {"add", "remove", "discard", "union", "intersection", "difference"}:
                return InferredType("set", ConfidenceLevel.MEDIUM, "set_methods_used")

        # Infer from operations
        if "subscript" in operations:
            if method_calls & {"keys", "values", "items"}:
                return InferredType("dict", ConfidenceLevel.MEDIUM, "dict_subscript")
            return InferredType("Sequence", ConfidenceLevel.LOW, "subscript_access")

        if "Add" in operations:
            return InferredType("int | str | list", ConfidenceLevel.LOW, "addition_operator")

        return InferredType("Any", ConfidenceLevel.UNKNOWN, "no_clear_usage")

    def _infer_from_name(self, name: str) -> InferredType:
        """Infer type from variable/parameter name using conventions.

        Args:
            name: Variable or parameter name

        Returns:
            InferredType based on naming conventions
        """
        name_lower = name.lower()

        # Common naming patterns
        if name_lower.endswith("_id") or name_lower in ("id", "count", "index", "size", "length"):
            return InferredType("int", ConfidenceLevel.LOW, "name_convention_int")

        if name_lower.endswith("_name") or name_lower in ("name", "title", "description", "text", "message"):
            return InferredType("str", ConfidenceLevel.LOW, "name_convention_str")

        if name_lower.startswith("is_") or name_lower.startswith("has_") or name_lower.startswith("can_"):
            return InferredType("bool", ConfidenceLevel.LOW, "name_convention_bool")

        if name_lower.endswith("_list") or name_lower.endswith("s") or name_lower in ("items", "elements"):
            return InferredType("list", ConfidenceLevel.LOW, "name_convention_list")

        if name_lower.endswith("_dict") or name_lower in ("data", "config", "settings", "options"):
            return InferredType("dict", ConfidenceLevel.LOW, "name_convention_dict")

        if name_lower.endswith("_set"):
            return InferredType("set", ConfidenceLevel.LOW, "name_convention_set")

        if name_lower.endswith("_tuple"):
            return InferredType("tuple", ConfidenceLevel.LOW, "name_convention_tuple")

        if name_lower.endswith("_path") or name_lower in ("path", "file", "filename", "filepath"):
            return InferredType("str | Path", ConfidenceLevel.LOW, "name_convention_path")

        return InferredType("Any", ConfidenceLevel.UNKNOWN, "no_name_pattern")


def infer_return_type(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> InferredType:
    """Convenience function to infer return type.

    Args:
        func_node: Function definition node

    Returns:
        InferredType for the return value
    """
    inferencer = TypeInferencer()
    return inferencer.infer_return_type(func_node)


def infer_param_type(
    param: ast.arg,
    default: ast.expr | None = None,
    func_body: list[ast.stmt] | None = None
) -> InferredType:
    """Convenience function to infer parameter type.

    Args:
        param: Parameter node
        default: Default value expression
        func_body: Function body for usage analysis

    Returns:
        InferredType for the parameter
    """
    inferencer = TypeInferencer()
    return inferencer.infer_param_type(param, default, func_body)
