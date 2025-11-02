"""Code analysis and metadata extraction for enhanced documentation.

This module provides advanced analysis of code elements to extract additional
metadata that can improve documentation quality, including complexity metrics,
type inference, and code pattern detection.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import structlog

from docpilot.core.models import CodeElement, CodeElementType, ParseResult
from docpilot.core.parser import PythonParser

logger = structlog.get_logger(__name__)


class CodeAnalyzer:
    """Analyzes Python code to extract metadata and quality metrics.

    This analyzer enhances parsed code elements with additional information
    such as complexity scores, type hints inference, and usage patterns.

    Attributes:
        calculate_complexity: Whether to calculate cyclomatic complexity
        infer_types: Whether to attempt type inference for untyped code
        detect_patterns: Whether to detect common code patterns
    """

    def __init__(
        self,
        calculate_complexity: bool = True,
        infer_types: bool = True,
        detect_patterns: bool = True,
    ) -> None:
        """Initialize the analyzer.

        Args:
            calculate_complexity: Enable complexity calculation
            infer_types: Enable type inference from usage
            detect_patterns: Enable pattern detection
        """
        self.calculate_complexity = calculate_complexity
        self.infer_types = infer_types
        self.detect_patterns = detect_patterns
        self._log = logger.bind(component="analyzer")

    def analyze_file(self, file_path: str | Path) -> ParseResult:
        """Parse and analyze a Python file.

        Args:
            file_path: Path to Python file

        Returns:
            ParseResult with enhanced metadata
        """
        self._log.info("analyzing_file", path=str(file_path))

        # First parse the file
        parser = PythonParser()
        result = parser.parse_file(file_path)

        # Enhance each element with analysis
        for element in result.elements:
            self._analyze_element(element)

        return result

    def analyze_element(self, element: CodeElement) -> CodeElement:
        """Analyze a single code element and enhance its metadata.

        Args:
            element: Code element to analyze

        Returns:
            Enhanced code element (modified in place, also returned)
        """
        self._analyze_element(element)
        return element

    def _analyze_element(self, element: CodeElement) -> None:
        """Perform all analyses on a code element.

        Args:
            element: Code element to analyze (modified in place)
        """
        # Calculate complexity for functions/methods
        if self.calculate_complexity and element.element_type in (
            CodeElementType.FUNCTION,
            CodeElementType.METHOD,
        ):
            element.complexity_score = self._calculate_complexity(element.source_code)

        # Infer types for parameters without type hints
        if self.infer_types and element.parameters:
            self._infer_parameter_types(element)

        # Detect common patterns
        if self.detect_patterns:
            patterns = self._detect_patterns(element)
            if patterns:
                element.metadata["patterns"] = patterns

        # Extract additional metadata based on element type
        if element.element_type == CodeElementType.CLASS:
            self._analyze_class(element)
        elif element.element_type in (CodeElementType.FUNCTION, CodeElementType.METHOD):
            self._analyze_function(element)

    def _calculate_complexity(self, source_code: str) -> int:
        """Calculate cyclomatic complexity of a function.

        Uses a simplified McCabe complexity metric counting decision points.

        Args:
            source_code: Source code of the function

        Returns:
            Complexity score (1 = simple, higher = more complex)
        """
        try:
            tree = ast.parse(source_code)
            complexity = 1  # Base complexity

            for node in ast.walk(tree):
                # Count decision points
                if isinstance(
                    node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler)
                ):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    # Each additional boolean operator adds complexity
                    complexity += len(node.values) - 1
                elif isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp)):
                    # Comprehensions with conditions
                    complexity += sum(1 for gen in node.generators for _ in gen.ifs)

            return complexity

        except Exception as e:
            self._log.warning("complexity_calculation_failed", error=str(e))
            return 1

    def _infer_parameter_types(self, element: CodeElement) -> None:
        """Infer types for parameters without type hints.

        Args:
            element: Code element with parameters (modified in place)
        """
        try:
            tree = ast.parse(element.source_code)

            # Build a map of parameter names to inferred types
            type_hints: dict[str, str] = {}

            for node in ast.walk(tree):
                # Look for parameter usage patterns
                if isinstance(node, ast.Compare):
                    # e.g., if x is None: -> x could be Optional
                    for comparator in node.comparators:
                        if (
                            isinstance(comparator, ast.Constant)
                            and comparator.value is None
                        ) and isinstance(node.left, ast.Name):
                            type_hints[node.left.id] = "Optional"

                # Look for method calls to infer object types
                elif isinstance(node, ast.Call) and (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                ):
                    obj_name = node.func.value.id
                    method_name = node.func.attr

                    # Common method patterns
                    if method_name in ("append", "extend", "pop"):
                        type_hints[obj_name] = "list"
                    elif method_name in ("add", "remove", "discard"):
                        type_hints[obj_name] = "set"
                    elif method_name in ("keys", "values", "items", "get"):
                        type_hints[obj_name] = "dict"
                    elif method_name in (
                        "strip",
                        "split",
                        "join",
                        "lower",
                        "upper",
                    ):
                        type_hints[obj_name] = "str"

            # Update parameters with inferred types (only if no type hint exists)
            for param in element.parameters:
                if not param.type_hint and param.name in type_hints:
                    # Create a new ParameterInfo with updated type hint
                    # (Note: ParameterInfo is frozen, so we need to track this in metadata)
                    element.metadata.setdefault("inferred_types", {})[param.name] = (
                        type_hints[param.name]
                    )

        except Exception as e:
            self._log.warning(
                "type_inference_failed", error=str(e), element=element.name
            )

    def _detect_patterns(self, element: CodeElement) -> list[str]:
        """Detect common code patterns.

        Args:
            element: Code element to analyze

        Returns:
            List of detected pattern names
        """
        patterns: list[str] = []

        try:
            # Detect patterns based on decorators
            decorator_names = {dec.name for dec in element.decorators}

            if "property" in decorator_names:
                patterns.append("property_accessor")

            if "cached_property" in decorator_names or "lru_cache" in decorator_names:
                patterns.append("cached_computation")

            if any(name.startswith("validate") for name in decorator_names):
                patterns.append("validation")

            if "contextmanager" in decorator_names:
                patterns.append("context_manager")

            # Detect patterns from naming conventions
            name_lower = element.name.lower()

            if name_lower.startswith("get_"):
                patterns.append("getter")
            elif name_lower.startswith("set_"):
                patterns.append("setter")
            elif name_lower.startswith("is_") or name_lower.startswith("has_"):
                patterns.append("predicate")
            elif name_lower.startswith("create_") or name_lower.startswith("make_"):
                patterns.append("factory")
            elif name_lower.startswith("build_"):
                patterns.append("builder")

            # Detect patterns from source code
            if element.source_code:
                # Singleton pattern
                if (
                    "instance" in element.source_code
                    and "__new__" in element.source_code
                ):
                    patterns.append("singleton")

                # Iterator pattern
                if (
                    "__iter__" in element.source_code
                    or "__next__" in element.source_code
                ):
                    patterns.append("iterator")

                # Context manager
                if (
                    "__enter__" in element.source_code
                    and "__exit__" in element.source_code
                ):
                    patterns.append("context_manager")

                # Descriptor
                if "__get__" in element.source_code or "__set__" in element.source_code:
                    patterns.append("descriptor")

        except Exception as e:
            self._log.warning(
                "pattern_detection_failed", error=str(e), element=element.name
            )

        return patterns

    def _analyze_class(self, element: CodeElement) -> None:
        """Perform class-specific analysis.

        Args:
            element: Class element to analyze (modified in place)
        """
        metadata: dict[str, Any] = {}

        # Detect class patterns
        if element.base_classes:
            metadata["has_inheritance"] = True

            # Detect common base classes
            if "ABC" in element.base_classes or "abc.ABC" in element.base_classes:
                metadata["is_abstract_base"] = True

            if any("Exception" in base for base in element.base_classes):
                metadata["is_exception"] = True

            if any("Enum" in base for base in element.base_classes):
                metadata["is_enum"] = True

        # Detect dataclass/pydantic
        decorator_names = {dec.name for dec in element.decorators}
        if "dataclass" in decorator_names or "dataclasses.dataclass" in decorator_names:
            metadata["is_dataclass"] = True

        if any("pydantic" in dec.name.lower() for dec in element.decorators):
            metadata["is_pydantic_model"] = True

        # Count methods by type
        if element.source_code:
            metadata["method_count"] = len(
                re.findall(r"\n\s+def\s+", element.source_code)
            )
            metadata["property_count"] = len(
                re.findall(r"\n\s+@property", element.source_code)
            )
            metadata["has_init"] = "__init__" in element.source_code

        element.metadata.update(metadata)

    def _analyze_function(self, element: CodeElement) -> None:
        """Perform function/method-specific analysis.

        Args:
            element: Function/method element to analyze (modified in place)
        """
        metadata: dict[str, Any] = {}

        # Analyze return behavior
        if element.source_code:
            # Count return statements
            return_count = len(re.findall(r"\breturn\b", element.source_code))
            metadata["return_count"] = return_count

            # Check for early returns (guard clauses)
            if return_count > 1:
                metadata["has_early_returns"] = True

            # Check for yield (generator)
            if "yield" in element.source_code:
                metadata["is_generator"] = True

            # Check for async/await
            if "await" in element.source_code:
                metadata["uses_await"] = True

            # Detect common function patterns
            if "raise NotImplementedError" in element.source_code:
                metadata["is_abstract_method"] = True

            # Detect recursion
            if f"{element.name}(" in element.source_code:
                # Simple check - could be improved
                metadata["might_be_recursive"] = True

        # Analyze parameter characteristics
        if element.parameters:
            param_count = len(
                [p for p in element.parameters if p.name not in ("self", "cls")]
            )
            metadata["parameter_count"] = param_count

            # Count required vs optional
            required = len([p for p in element.parameters if p.is_required])
            optional = len([p for p in element.parameters if not p.is_required])
            metadata["required_params"] = required
            metadata["optional_params"] = optional

            # Check for variadic arguments
            has_varargs = any(p.is_variadic for p in element.parameters)
            has_kwargs = any(p.is_keyword for p in element.parameters)
            metadata["has_varargs"] = has_varargs
            metadata["has_kwargs"] = has_kwargs

        element.metadata.update(metadata)

    def analyze_project(self, project_path: str | Path) -> list[ParseResult]:
        """Analyze all Python files in a project.

        Args:
            project_path: Path to project directory

        Returns:
            List of ParseResult for each file
        """
        project_path = Path(project_path)
        self._log.info("analyzing_project", path=str(project_path))

        results: list[ParseResult] = []

        # Find all Python files
        python_files = list(project_path.rglob("*.py"))

        for py_file in python_files:
            # Skip common directories
            if any(
                part.startswith(".") or part == "__pycache__" for part in py_file.parts
            ):
                continue

            try:
                result = self.analyze_file(py_file)
                results.append(result)
            except Exception as e:
                self._log.error("file_analysis_failed", path=str(py_file), error=str(e))

        self._log.info(
            "project_analysis_complete",
            files_analyzed=len(results),
            total_elements=sum(len(r.elements) for r in results),
        )

        return results


def analyze_file(
    file_path: str | Path,
    calculate_complexity: bool = True,
    infer_types: bool = True,
    detect_patterns: bool = True,
) -> ParseResult:
    """Convenience function to analyze a Python file.

    Args:
        file_path: Path to Python file
        calculate_complexity: Enable complexity calculation
        infer_types: Enable type inference
        detect_patterns: Enable pattern detection

    Returns:
        ParseResult with analysis metadata
    """
    analyzer = CodeAnalyzer(
        calculate_complexity=calculate_complexity,
        infer_types=infer_types,
        detect_patterns=detect_patterns,
    )
    return analyzer.analyze_file(file_path)


def analyze_element(element: CodeElement) -> CodeElement:
    """Convenience function to analyze a single code element.

    Args:
        element: Code element to analyze

    Returns:
        Enhanced code element
    """
    analyzer = CodeAnalyzer()
    return analyzer.analyze_element(element)
