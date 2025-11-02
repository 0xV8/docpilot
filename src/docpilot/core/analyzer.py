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
                element.detected_patterns = patterns
                element.metadata["patterns"] = patterns  # Maintain backward compatibility

                # Calculate pattern confidence based on how many patterns detected
                # and whether they're anti-patterns
                anti_patterns = [p for p in patterns if p.startswith("anti_pattern_")]
                design_patterns = [p for p in patterns if not p.startswith("anti_pattern_")]

                # Higher confidence with more design patterns, lower with anti-patterns
                base_confidence = min(0.9, 0.5 + (len(design_patterns) * 0.1))
                confidence_penalty = len(anti_patterns) * 0.15
                element.pattern_confidence = max(0.0, base_confidence - confidence_penalty)

                # Generate suggestions based on detected patterns
                element.suggestions = self._generate_suggestions(element, patterns)

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
        """Detect common code patterns, design patterns, and anti-patterns.

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

            if "abstractmethod" in decorator_names or "abc.abstractmethod" in decorator_names:
                patterns.append("abstract_method")

            if "staticmethod" in decorator_names:
                patterns.append("static_method")

            if "classmethod" in decorator_names:
                patterns.append("class_method")

            # Detect patterns from naming conventions
            name_lower = element.name.lower()

            # CRUD patterns
            if name_lower.startswith("get_") or name_lower.startswith("fetch_") or name_lower.startswith("retrieve_"):
                patterns.append("crud_read")
            elif name_lower.startswith("set_") or name_lower.startswith("update_"):
                patterns.append("crud_update")
            elif name_lower.startswith("create_") or name_lower.startswith("add_"):
                patterns.append("crud_create")
            elif name_lower.startswith("delete_") or name_lower.startswith("remove_"):
                patterns.append("crud_delete")

            # Common patterns
            if name_lower.startswith("is_") or name_lower.startswith("has_") or name_lower.startswith("can_"):
                patterns.append("predicate")
            elif name_lower.startswith("make_"):
                patterns.append("factory_method")
            elif name_lower.startswith("build_"):
                patterns.append("builder_method")
            elif name_lower.startswith("validate_"):
                patterns.append("validation")
            elif name_lower.startswith("serialize_") or name_lower.startswith("deserialize_"):
                patterns.append("serialization")
            elif name_lower.startswith("parse_"):
                patterns.append("parser")
            elif name_lower.startswith("format_"):
                patterns.append("formatter")

            # Detect design patterns from source code
            if element.source_code:
                source_lower = element.source_code.lower()

                # Design Patterns
                # Singleton pattern
                if "__new__" in element.source_code and "instance" in source_lower:
                    patterns.append("singleton")

                # Factory pattern
                if element.element_type == CodeElementType.CLASS:
                    if any(word in name_lower for word in ["factory", "creator"]):
                        patterns.append("factory")
                elif element.element_type in (CodeElementType.FUNCTION, CodeElementType.METHOD):
                    if "return " in source_lower and element.name.startswith(("create_", "make_", "build_")):
                        patterns.append("factory_method")

                # Strategy pattern
                if element.element_type == CodeElementType.CLASS and any(word in name_lower for word in ["strategy", "algorithm"]):
                    patterns.append("strategy")

                # Observer pattern
                if any(word in source_lower for word in ["subscribe", "notify", "observer", "listener"]):
                    patterns.append("observer")

                # Decorator pattern (not Python decorators, but GoF decorator)
                if element.element_type == CodeElementType.CLASS and "wrapper" in name_lower:
                    patterns.append("decorator_pattern")

                # Adapter pattern
                if element.element_type == CodeElementType.CLASS and "adapter" in name_lower:
                    patterns.append("adapter")

                # Iterator pattern
                if "__iter__" in element.source_code or "__next__" in element.source_code:
                    patterns.append("iterator")

                # Context manager
                if "__enter__" in element.source_code and "__exit__" in element.source_code:
                    patterns.append("context_manager")

                # Descriptor
                if "__get__" in element.source_code or "__set__" in element.source_code:
                    patterns.append("descriptor")

                # Template method pattern
                if element.element_type == CodeElementType.CLASS and "raise NotImplementedError" in element.source_code:
                    patterns.append("template_method")

                # Command pattern
                if element.element_type == CodeElementType.CLASS and "execute" in source_lower:
                    patterns.append("command")

                # Anti-patterns detection
                # God class - too many methods
                if element.element_type == CodeElementType.CLASS:
                    method_count = element.metadata.get("method_count", 0)
                    if method_count > 20:
                        patterns.append("anti_pattern_god_class")

                # Long method - high complexity or many lines
                if element.element_type in (CodeElementType.FUNCTION, CodeElementType.METHOD):
                    lines = element.source_code.split('\n')
                    if len(lines) > 100:
                        patterns.append("anti_pattern_long_method")

                    if element.complexity_score and element.complexity_score > 15:
                        patterns.append("anti_pattern_high_complexity")

                # Too many parameters
                param_count = len([p for p in element.parameters if p.name not in ("self", "cls")])
                if param_count > 5:
                    patterns.append("anti_pattern_too_many_parameters")

                # Magic numbers
                if element.element_type in (CodeElementType.FUNCTION, CodeElementType.METHOD):
                    import re
                    # Find numeric literals that aren't 0, 1, -1, or 2
                    numbers = re.findall(r'\b(?<![\.\d])(?!0\b|1\b|2\b|-1\b)\d+(?![\.\d])\b', element.source_code)
                    if len(numbers) > 3:
                        patterns.append("anti_pattern_magic_numbers")

        except Exception as e:
            self._log.warning(
                "pattern_detection_failed", error=str(e), element=element.name
            )

        return patterns

    def _generate_suggestions(self, element: CodeElement, patterns: list[str]) -> list[str]:
        """Generate improvement suggestions based on detected patterns.

        Args:
            element: Code element being analyzed
            patterns: List of detected patterns

        Returns:
            List of suggestions for improvement
        """
        suggestions: list[str] = []

        # Suggestions for anti-patterns
        if "anti_pattern_god_class" in patterns:
            suggestions.append(
                "Consider breaking this class into smaller, more focused classes following the Single Responsibility Principle"
            )

        if "anti_pattern_long_method" in patterns:
            suggestions.append(
                "Consider refactoring this method into smaller, more focused functions"
            )

        if "anti_pattern_high_complexity" in patterns:
            suggestions.append(
                f"High cyclomatic complexity ({element.complexity_score}). Consider simplifying logic or extracting methods"
            )

        if "anti_pattern_too_many_parameters" in patterns:
            param_count = len([p for p in element.parameters if p.name not in ("self", "cls")])
            suggestions.append(
                f"This function has {param_count} parameters. Consider using a configuration object or builder pattern"
            )

        if "anti_pattern_magic_numbers" in patterns:
            suggestions.append(
                "Consider extracting magic numbers into named constants for better readability"
            )

        # Suggestions for design pattern opportunities
        if "factory_method" in patterns and element.element_type in (CodeElementType.FUNCTION, CodeElementType.METHOD):
            suggestions.append(
                "Factory method detected. Ensure proper error handling and consider adding type hints for return value"
            )

        if "singleton" in patterns:
            suggestions.append(
                "Singleton pattern detected. Consider thread-safety if used in concurrent environments"
            )

        # Suggestions for missing patterns
        if element.element_type in (CodeElementType.FUNCTION, CodeElementType.METHOD):
            # Check if parameters lack type hints
            untyped_params = [p for p in element.parameters if not p.type_hint and p.name not in ("self", "cls")]
            if untyped_params and len(untyped_params) > 2:
                suggestions.append(
                    "Add type hints to parameters for better code clarity and IDE support"
                )

            # Check if missing return type
            if element.return_info and not element.return_info.type_hint:
                suggestions.append(
                    "Add return type hint for better code documentation"
                )

        # Suggestions for CRUD operations
        crud_patterns = ["crud_create", "crud_read", "crud_update", "crud_delete"]
        detected_crud = [p for p in patterns if p in crud_patterns]
        if detected_crud:
            if "crud_read" in patterns:
                suggestions.append(
                    "CRUD read operation detected. Document expected return values and handle missing data cases"
                )
            if "crud_create" in patterns:
                suggestions.append(
                    "CRUD create operation detected. Ensure proper validation and document error cases"
                )
            if "crud_update" in patterns:
                suggestions.append(
                    "CRUD update operation detected. Consider idempotency and partial update handling"
                )
            if "crud_delete" in patterns:
                suggestions.append(
                    "CRUD delete operation detected. Document cascading behavior and handle non-existent resources"
                )

        return suggestions

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
