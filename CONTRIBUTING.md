# Contributing to docpilot

Thank you for your interest in contributing to docpilot! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and professional in all interactions.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git

### Development Setup

1. Fork and clone the repository:
```bash
git clone https://github.com/yourusername/docpilot.git
cd docpilot
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

## Development Workflow

### Making Changes

1. Create a feature branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes following our coding standards

3. Run tests:
```bash
pytest
```

4. Run type checking:
```bash
mypy src/docpilot
```

5. Run linting:
```bash
ruff check .
black --check .
```

### Coding Standards

- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for all public APIs
- Keep functions focused and small
- Write tests for new features

### Commit Messages

Follow conventional commits format:

```
type(scope): subject

body

footer
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions or changes
- `chore`: Build process or tooling changes

Example:
```
feat(parser): add support for async function parsing

- Extract async function definitions
- Handle async context managers
- Add tests for async parsing

Closes #123
```

### Pull Requests

1. Update documentation if needed
2. Add tests for new features
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Submit PR with clear description

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/test_parser.py

# Run tests matching pattern
pytest -k "test_async"
```

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)

Example:
```python
def test_parse_function_with_type_hints():
    # Arrange
    code = "def foo(x: int) -> str: pass"

    # Act
    result = parse_code(code)

    # Assert
    assert len(result.functions) == 1
    assert result.functions[0].name == "foo"
```

## Documentation

### Docstring Style

Use Google-style docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """Brief description of function.

    More detailed explanation if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param2 is negative.

    Examples:
        >>> example_function("test", 5)
        True
    """
```

## Release Process

Maintainers will handle releases following semantic versioning:

- MAJOR: Breaking changes
- MINOR: New features (backwards compatible)
- PATCH: Bug fixes

## Questions?

- Open an issue for bugs or feature requests
- Join our discussions for questions
- Check existing issues before creating new ones

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
