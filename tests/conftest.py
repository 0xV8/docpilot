"""Shared pytest fixtures for docpilot tests."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Return the path to the test data directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_python_file(tmp_path_factory) -> Path:
    """Create a sample Python file for testing."""
    tmp_dir = tmp_path_factory.mktemp("samples")
    sample_file = tmp_dir / "sample.py"
    sample_file.write_text(
        """
def example_function(x: int, y: int) -> int:
    '''Add two numbers.'''
    return x + y

class ExampleClass:
    '''Example class for testing.'''

    def method(self) -> None:
        '''Example method.'''
        pass
    """
    )
    return sample_file


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock environment variables for all tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-67890")
    monkeypatch.setenv("DOCPILOT_LLM_PROVIDER", "mock")


@pytest.fixture
def mock_llm_response() -> dict:
    """Provide a mock LLM response."""
    return {
        "docstring": '''"""Example docstring.

    Args:
        x: First number.
        y: Second number.

    Returns:
        Sum of x and y.
    """''',
        "confidence": 0.95,
    }
