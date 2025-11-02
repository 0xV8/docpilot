"""AST-based Python code parser for extracting code elements and metadata.

This module provides comprehensive parsing of Python source files using the
Abstract Syntax Tree (AST) to extract all documentable code elements with
their complete metadata.
"""

from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import structlog

from docpilot.core.models import (
    CodeElement,
    CodeElementType,
    DecoratorInfo,
    ExceptionInfo,
    ParameterInfo,
    ParseResult,
    ReturnInfo,
)

logger = structlog.get_logger(__name__)


class PythonParser:
    """AST-based parser for Python source code.

    This parser analyzes Python files to extract all documentable code elements
    including modules, classes, functions, methods, and their metadata.

    Attributes:
        encoding: Default file encoding to use
        extract_private: Whether to extract private elements (leading underscore)
    """

    def __init__(
        self,
        encoding: str = "utf-8",
        extract_private: bool = False,
    ) -> None:
        """Initialize the parser.

        Args:
            encoding: File encoding to use when reading source files
            extract_private: Whether to include private/internal elements
        """
        self.encoding = encoding
        self.extract_private = extract_private
        self._log = logger.bind(component="parser")

    def parse_file(self, file_path: str | Path) -> ParseResult:
        """Parse a Python file and extract all code elements.

        Args:
            file_path: Path to Python file to parse

        Returns:
            ParseResult containing all extracted code elements

        Raises:
            FileNotFoundError: If file does not exist
            SyntaxError: If file contains invalid Python syntax
        """
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self._log.info("parsing_file", path=str(file_path))

        try:
            # Read source code
            source_code = file_path.read_text(encoding=self.encoding)

            # Parse AST
            tree = ast.parse(source_code, filename=str(file_path))

            # Calculate module path
            module_path = self._get_module_path(file_path)

            # Extract elements
            elements: list[CodeElement] = []
            parse_errors: list[str] = []

            # Module-level docstring
            ast.get_docstring(tree)

            # Parse all module-level elements
            for node in ast.iter_child_nodes(tree):
                try:
                    if isinstance(node, ast.FunctionDef):
                        element = self._parse_function(
                            node, module_path, str(file_path)
                        )
                        if element and (self.extract_private or element.is_public):
                            elements.append(element)

                    elif isinstance(node, ast.AsyncFunctionDef):
                        element = self._parse_function(
                            node, module_path, str(file_path), is_async=True
                        )
                        if element and (self.extract_private or element.is_public):
                            elements.append(element)

                    elif isinstance(node, ast.ClassDef):
                        class_elements = self._parse_class(
                            node, module_path, str(file_path)
                        )
                        if self.extract_private:
                            elements.extend(class_elements)
                        else:
                            elements.extend([e for e in class_elements if e.is_public])

                except Exception as e:
                    error_msg = f"Error parsing {getattr(node, 'name', 'unknown')}: {e}"
                    parse_errors.append(error_msg)
                    self._log.warning(
                        "parse_error", error=str(e), node=type(node).__name__
                    )

            # Calculate line counts
            lines = source_code.splitlines()
            total_lines = len(lines)
            code_lines = sum(
                1 for line in lines if line.strip() and not line.strip().startswith("#")
            )

            return ParseResult(
                file_path=str(file_path),
                module_path=module_path,
                elements=elements,
                parse_errors=parse_errors,
                encoding=self.encoding,
                total_lines=total_lines,
                code_lines=code_lines,
            )

        except SyntaxError as e:
            self._log.error("syntax_error", path=str(file_path), error=str(e))
            raise

        except Exception as e:
            self._log.error("parse_failed", path=str(file_path), error=str(e))
            raise

    def parse_string(self, code: str) -> ParseResult:
        """Parse Python source code from a string.

        Args:
            code: Python source code as a string

        Returns:
            ParseResult containing all extracted code elements

        Raises:
            SyntaxError: If code contains invalid Python syntax
        """
        # Create a temporary file to reuse parse_file logic
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            encoding=self.encoding,
            delete=False,
        ) as temp_file:
            temp_file.write(code)
            temp_path = Path(temp_file.name)

        try:
            # Parse the temporary file
            result = self.parse_file(temp_path)
            return result
        finally:
            # Clean up the temporary file
            temp_path.unlink(missing_ok=True)

    def _parse_class(
        self, node: ast.ClassDef, module_path: str, file_path: str
    ) -> list[CodeElement]:
        """Parse a class definition and its members.

        Args:
            node: AST ClassDef node
            module_path: Dotted module path
            file_path: Source file path

        Returns:
            List of CodeElements (class and its methods/properties)
        """
        elements: list[CodeElement] = []

        # Extract base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(ast.unparse(base))

        # Extract class attributes
        attributes: list[tuple[str, str | None]] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                attr_name = item.target.id
                attr_type = ast.unparse(item.annotation) if item.annotation else None
                attributes.append((attr_name, attr_type))
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes.append((target.id, None))

        # Extract decorators
        decorators = [self._parse_decorator(dec) for dec in node.decorator_list]

        # Check if abstract
        is_abstract = any(
            dec.name in ("abstractmethod", "abc.ABCMeta") for dec in decorators
        )

        # Parse methods and properties first
        method_elements: list[CodeElement] = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method = self._parse_function(
                    item, module_path, file_path, parent_class=node.name
                )
                if method:
                    method_elements.append(method)

            elif isinstance(item, ast.AsyncFunctionDef):
                method = self._parse_function(
                    item, module_path, file_path, parent_class=node.name, is_async=True
                )
                if method:
                    method_elements.append(method)

        # Create class element with methods
        class_element = CodeElement(
            name=node.name,
            element_type=CodeElementType.CLASS,
            lineno=node.lineno,
            end_lineno=node.end_lineno,
            source_code=ast.unparse(node),
            docstring=ast.get_docstring(node),
            file_path=file_path,
            module_path=module_path,
            is_public=not node.name.startswith("_"),
            is_abstract=is_abstract,
            base_classes=base_classes,
            attributes=attributes,
            decorators=decorators,
        )

        # Populate the _methods field
        class_element._methods = method_elements

        elements.append(class_element)
        # Methods are accessible via class_element.methods property
        # Don't add them to the flat elements list to maintain clean separation

        return elements

    def _parse_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        module_path: str,
        file_path: str,
        parent_class: str | None = None,
        is_async: bool = False,
    ) -> CodeElement | None:
        """Parse a function or method definition.

        Args:
            node: AST FunctionDef or AsyncFunctionDef node
            module_path: Dotted module path
            file_path: Source file path
            parent_class: Parent class name if this is a method
            is_async: Whether function is async

        Returns:
            CodeElement representing the function/method
        """
        # Extract parameters
        parameters = self._parse_parameters(node.args)

        # Extract return type
        return_info = self._parse_return(node, is_async)

        # Extract decorators
        decorators = [self._parse_decorator(dec) for dec in node.decorator_list]

        # Determine method type
        is_property = any(dec.name == "property" for dec in decorators)
        is_classmethod = any(dec.name == "classmethod" for dec in decorators)
        is_staticmethod = any(dec.name == "staticmethod" for dec in decorators)
        is_abstract = any(dec.name == "abstractmethod" for dec in decorators)

        # Extract exceptions
        raises = self._extract_exceptions(node)

        # Determine element type
        if parent_class:
            if is_property:
                element_type = CodeElementType.PROPERTY
            else:
                element_type = CodeElementType.METHOD
        else:
            element_type = CodeElementType.FUNCTION

        return CodeElement(
            name=node.name,
            element_type=element_type,
            lineno=node.lineno,
            end_lineno=node.end_lineno,
            source_code=ast.unparse(node),
            docstring=ast.get_docstring(node),
            file_path=file_path,
            module_path=module_path,
            parent_class=parent_class,
            is_public=not node.name.startswith("_"),
            is_async=is_async,
            is_property=is_property,
            is_classmethod=is_classmethod,
            is_staticmethod=is_staticmethod,
            is_abstract=is_abstract,
            parameters=parameters,
            return_info=return_info,
            raises=raises,
            decorators=decorators,
        )

    def _parse_parameters(self, args: ast.arguments) -> list[ParameterInfo]:
        """Parse function parameters from arguments node.

        Args:
            args: AST arguments node

        Returns:
            List of ParameterInfo objects
        """
        parameters: list[ParameterInfo] = []

        # Regular arguments
        defaults_offset = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            default_value = None
            is_required = True

            if i >= defaults_offset:
                default_idx = i - defaults_offset
                if default_idx < len(args.defaults):
                    default_value = ast.unparse(args.defaults[default_idx])
                    is_required = False

            type_hint = ast.unparse(arg.annotation) if arg.annotation else None

            parameters.append(
                ParameterInfo(
                    name=arg.arg,
                    type_hint=type_hint,
                    default_value=default_value,
                    is_required=is_required,
                )
            )

        # *args
        if args.vararg:
            type_hint = (
                ast.unparse(args.vararg.annotation) if args.vararg.annotation else None
            )
            parameters.append(
                ParameterInfo(
                    name=args.vararg.arg,
                    type_hint=type_hint,
                    is_required=False,
                    is_variadic=True,
                )
            )

        # Keyword-only arguments
        kw_defaults_map = {
            kw.arg: default
            for kw, default in zip(args.kwonlyargs, args.kw_defaults)
            if default is not None
        }

        for kw_arg in args.kwonlyargs:
            default_value = None
            is_required = True

            if kw_arg.arg in kw_defaults_map:
                default_value = ast.unparse(kw_defaults_map[kw_arg.arg])
                is_required = False

            type_hint = ast.unparse(kw_arg.annotation) if kw_arg.annotation else None

            parameters.append(
                ParameterInfo(
                    name=kw_arg.arg,
                    type_hint=type_hint,
                    default_value=default_value,
                    is_required=is_required,
                )
            )

        # **kwargs
        if args.kwarg:
            type_hint = (
                ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else None
            )
            parameters.append(
                ParameterInfo(
                    name=args.kwarg.arg,
                    type_hint=type_hint,
                    is_required=False,
                    is_keyword=True,
                )
            )

        return parameters

    def _parse_return(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> ReturnInfo | None:
        """Parse return type information.

        Args:
            node: Function definition node
            is_async: Whether function is async

        Returns:
            ReturnInfo if function has return annotation or returns value
        """
        type_hint = None
        if node.returns:
            type_hint = ast.unparse(node.returns)

        # Check if generator
        is_generator = any(
            isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(node)
        )

        # Only create ReturnInfo if we have meaningful information
        if type_hint or is_generator or is_async:
            return ReturnInfo(
                type_hint=type_hint,
                is_generator=is_generator,
                is_async=is_async,
            )

        return None

    def _parse_decorator(self, node: ast.expr) -> DecoratorInfo:
        """Parse a decorator node.

        Args:
            node: Decorator expression node

        Returns:
            DecoratorInfo object
        """
        if isinstance(node, ast.Name):
            return DecoratorInfo(name=node.id)

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = ast.unparse(node.func)
            else:
                name = ast.unparse(node.func)

            arguments = [ast.unparse(arg) for arg in node.args]
            return DecoratorInfo(name=name, arguments=arguments)

        else:
            return DecoratorInfo(name=ast.unparse(node))

    def _extract_exceptions(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[ExceptionInfo]:
        """Extract exceptions that can be raised by a function.

        Args:
            node: Function definition node

        Returns:
            List of ExceptionInfo objects
        """
        exceptions: list[ExceptionInfo] = []
        exception_types: set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc:
                # Extract exception type
                exc_type = None
                if isinstance(child.exc, ast.Call):
                    if isinstance(child.exc.func, ast.Name):
                        exc_type = child.exc.func.id
                    elif isinstance(child.exc.func, ast.Attribute):
                        exc_type = ast.unparse(child.exc.func)
                elif isinstance(child.exc, ast.Name):
                    exc_type = child.exc.id

                if exc_type and exc_type not in exception_types:
                    exception_types.add(exc_type)
                    exceptions.append(ExceptionInfo(exception_type=exc_type))

        return exceptions

    def _get_module_path(self, file_path: Path) -> str:
        """Convert file path to Python module path.

        Args:
            file_path: Absolute path to Python file

        Returns:
            Dotted module path (e.g., 'package.module')
        """
        # Try to find src/ or project root
        parts = file_path.parts

        # Look for common project structure markers
        markers = ("src", "lib", "python")
        start_idx = 0

        for i, part in enumerate(parts):
            if part in markers:
                start_idx = i + 1
                break

        # Build module path
        module_parts = list(parts[start_idx:])

        # Remove .py extension from last part
        if module_parts and module_parts[-1].endswith(".py"):
            module_parts[-1] = module_parts[-1][:-3]

        # Remove __init__ if present
        if module_parts and module_parts[-1] == "__init__":
            module_parts.pop()

        return ".".join(module_parts) if module_parts else file_path.stem


def parse_file(
    file_path: str | Path,
    encoding: str = "utf-8",
    extract_private: bool = False,
) -> ParseResult:
    """Convenience function to parse a Python file.

    Args:
        file_path: Path to Python file
        encoding: File encoding
        extract_private: Whether to extract private elements

    Returns:
        ParseResult with extracted code elements
    """
    parser = PythonParser(encoding=encoding, extract_private=extract_private)
    return parser.parse_file(file_path)
