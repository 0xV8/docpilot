"""Unit tests for configuration loading and precedence."""

import os
from pathlib import Path
from typing import Any

import pytest

from docpilot.core.models import DocstringStyle
from docpilot.llm.base import LLMProvider
from docpilot.utils.config import (
    DocpilotConfig,
    find_config_file,
    load_config,
    load_config_file,
)


class TestConfigFileLoading:
    """Test configuration file loading."""

    @pytest.fixture
    def temp_config_file(self, tmp_path: Path) -> Path:
        """Create a temporary config file."""
        config_file = tmp_path / "docpilot.toml"
        config_content = """
[docpilot]
style = "numpy"
overwrite = true
include_private = true
llm_provider = "anthropic"
llm_model = "claude-3-haiku"
llm_temperature = 0.5
max_line_length = 100
"""
        config_file.write_text(config_content)
        return config_file

    @pytest.fixture
    def temp_pyproject_file(self, tmp_path: Path) -> Path:
        """Create a temporary pyproject.toml file."""
        config_file = tmp_path / "pyproject.toml"
        config_content = """
[tool.docpilot]
style = "sphinx"
overwrite = false
llm_provider = "openai"
llm_model = "gpt-4"
"""
        config_file.write_text(config_content)
        return config_file

    def test_load_config_from_docpilot_toml(self, temp_config_file: Path) -> None:
        """Test loading config from docpilot.toml."""
        config_data = load_config_file(temp_config_file)

        assert config_data["style"] == "numpy"
        assert config_data["overwrite"] is True
        assert config_data["include_private"] is True
        assert config_data["llm_provider"] == "anthropic"
        assert config_data["llm_model"] == "claude-3-haiku"
        assert config_data["llm_temperature"] == 0.5
        assert config_data["max_line_length"] == 100

    def test_load_config_from_pyproject_toml(self, temp_pyproject_file: Path) -> None:
        """Test loading config from pyproject.toml."""
        config_data = load_config_file(temp_pyproject_file)

        assert config_data["style"] == "sphinx"
        assert config_data["overwrite"] is False
        assert config_data["llm_provider"] == "openai"
        assert config_data["llm_model"] == "gpt-4"

    def test_load_config_file_not_found(self) -> None:
        """Test loading config from non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_config_file(Path("/nonexistent/config.toml"))

    def test_load_config_invalid_toml(self, tmp_path: Path) -> None:
        """Test loading invalid TOML file."""
        invalid_file = tmp_path / "invalid.toml"
        invalid_file.write_text("this is not valid TOML [[[")

        with pytest.raises(ValueError, match="Invalid config file"):
            load_config_file(invalid_file)

    def test_find_config_file_docpilot_toml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test finding docpilot.toml in current directory."""
        config_file = tmp_path / "docpilot.toml"
        config_file.write_text("[docpilot]\nstyle = 'google'")

        monkeypatch.chdir(tmp_path)
        found = find_config_file()

        assert found == config_file

    def test_find_config_file_pyproject_toml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test finding pyproject.toml with [tool.docpilot] section."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text("[tool.docpilot]\nstyle = 'google'")

        monkeypatch.chdir(tmp_path)
        found = find_config_file()

        assert found == config_file

    def test_find_config_file_pyproject_without_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that pyproject.toml without [tool.docpilot] is not found."""
        config_file = tmp_path / "pyproject.toml"
        config_file.write_text("[tool.other]\nkey = 'value'")

        monkeypatch.chdir(tmp_path)
        found = find_config_file()

        assert found is None

    def test_find_config_file_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when no config file exists."""
        monkeypatch.chdir(tmp_path)
        found = find_config_file()

        assert found is None


class TestConfigPrecedence:
    """Test configuration precedence: CLI > env > config > defaults."""

    @pytest.fixture
    def config_file(self, tmp_path: Path) -> Path:
        """Create a config file for testing."""
        config_file = tmp_path / "test_config.toml"
        config_content = """
[docpilot]
style = "numpy"
overwrite = true
llm_provider = "anthropic"
llm_model = "claude-3"
llm_temperature = 0.5
verbose = false
"""
        config_file.write_text(config_content)
        return config_file

    def test_default_values_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that defaults are used when no config, env, or CLI args provided."""
        # Clear any environment variables
        monkeypatch.delenv("DOCPILOT_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("DOCPILOT_STYLE", raising=False)

        config = load_config(config_path=None)

        assert config.style == DocstringStyle.GOOGLE  # Default
        assert config.overwrite is False  # Default
        assert config.llm_provider == LLMProvider.OPENAI  # Default
        assert config.llm_model == "gpt-3.5-turbo"  # Default
        assert config.llm_temperature == 0.7  # Default

    def test_config_file_overrides_defaults(self, config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that config file values override defaults."""
        # Clear env vars that might interfere
        monkeypatch.delenv("DOCPILOT_LLM_PROVIDER", raising=False)

        config = load_config(config_path=config_file)

        assert config.style == DocstringStyle.NUMPY  # From file
        assert config.overwrite is True  # From file
        assert config.llm_provider == LLMProvider.ANTHROPIC  # From file
        assert config.llm_model == "claude-3"  # From file
        assert config.llm_temperature == 0.5  # From file

    def test_env_vars_override_config_file(
        self, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that environment variables override config file values."""
        monkeypatch.setenv("DOCPILOT_STYLE", "sphinx")
        monkeypatch.setenv("DOCPILOT_LLM_PROVIDER", "openai")
        monkeypatch.setenv("DOCPILOT_LLM_MODEL", "gpt-4")
        monkeypatch.setenv("DOCPILOT_LLM_TEMPERATURE", "0.9")

        config = load_config(config_path=config_file)

        # Env vars should override config file
        assert config.style == DocstringStyle.SPHINX  # From env
        assert config.llm_provider == LLMProvider.OPENAI  # From env
        assert config.llm_model == "gpt-4"  # From env
        assert config.llm_temperature == 0.9  # From env
        # Config file value should still apply when no env var
        assert config.overwrite is True  # From file

    def test_cli_args_override_env_vars(
        self, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that CLI arguments override environment variables."""
        monkeypatch.setenv("DOCPILOT_STYLE", "sphinx")
        monkeypatch.setenv("DOCPILOT_OVERWRITE", "false")
        monkeypatch.setenv("DOCPILOT_LLM_MODEL", "gpt-4")

        # Simulate CLI arguments as overrides
        config = load_config(
            config_path=config_file,
            style=DocstringStyle.GOOGLE,
            overwrite=False,
            llm_model="custom-model",
        )

        # CLI args should override env vars
        assert config.style == DocstringStyle.GOOGLE  # From CLI
        assert config.overwrite is False  # From CLI
        assert config.llm_model == "custom-model"  # From CLI

    def test_full_precedence_chain(
        self, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test complete precedence: CLI > env > config > defaults."""
        # Set environment variable
        monkeypatch.setenv("DOCPILOT_MAX_LINE_LENGTH", "120")
        monkeypatch.setenv("DOCPILOT_VERBOSE", "true")

        # Load with CLI override
        config = load_config(
            config_path=config_file,
            style=DocstringStyle.GOOGLE,  # CLI override
            verbose=False,  # CLI override
        )

        # Verify precedence
        assert config.style == DocstringStyle.GOOGLE  # CLI
        assert config.verbose is False  # CLI
        assert config.max_line_length == 120  # Env var
        assert config.overwrite is True  # Config file
        assert config.include_private is False  # Default

    def test_cli_none_values_do_not_override(
        self, config_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that None values from CLI don't override config/env."""
        monkeypatch.setenv("DOCPILOT_LLM_MODEL", "env-model")

        # Pass None for llm_model (as CLI would when not specified)
        config = load_config(
            config_path=config_file,
            llm_model=None,
        )

        # Should use env var since CLI passed None
        assert config.llm_model == "env-model"


class TestConfigValidation:
    """Test configuration validation."""

    def test_invalid_log_level(self) -> None:
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            DocpilotConfig(log_level="INVALID")

    def test_valid_log_levels(self) -> None:
        """Test that all valid log levels are accepted."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            config = DocpilotConfig(log_level=level)
            assert config.log_level == level

        # Test case insensitive
        config = DocpilotConfig(log_level="debug")
        assert config.log_level == "DEBUG"

    def test_invalid_log_format(self) -> None:
        """Test that invalid log format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid log format"):
            DocpilotConfig(log_format="xml")

    def test_valid_log_formats(self) -> None:
        """Test that valid log formats are accepted."""
        for fmt in ["json", "console"]:
            config = DocpilotConfig(log_format=fmt)
            assert config.log_format == fmt

        # Test case insensitive
        config = DocpilotConfig(log_format="JSON")
        assert config.log_format == "json"

    def test_temperature_bounds(self) -> None:
        """Test that temperature is validated within bounds."""
        # Valid values
        config = DocpilotConfig(llm_temperature=0.0)
        assert config.llm_temperature == 0.0

        config = DocpilotConfig(llm_temperature=1.0)
        assert config.llm_temperature == 1.0

        config = DocpilotConfig(llm_temperature=0.5)
        assert config.llm_temperature == 0.5

        # Invalid values
        with pytest.raises(ValueError):
            DocpilotConfig(llm_temperature=-0.1)

        with pytest.raises(ValueError):
            DocpilotConfig(llm_temperature=1.1)

    def test_max_line_length_bounds(self) -> None:
        """Test that max_line_length is validated within bounds."""
        # Valid values
        config = DocpilotConfig(max_line_length=40)
        assert config.max_line_length == 40

        config = DocpilotConfig(max_line_length=200)
        assert config.max_line_length == 200

        # Invalid values
        with pytest.raises(ValueError):
            DocpilotConfig(max_line_length=39)

        with pytest.raises(ValueError):
            DocpilotConfig(max_line_length=201)

    def test_positive_values(self) -> None:
        """Test that fields requiring positive values are validated."""
        # Valid values
        config = DocpilotConfig(llm_max_tokens=100, llm_timeout=10)
        assert config.llm_max_tokens == 100
        assert config.llm_timeout == 10

        # Invalid values
        with pytest.raises(ValueError):
            DocpilotConfig(llm_max_tokens=0)

        with pytest.raises(ValueError):
            DocpilotConfig(llm_max_tokens=-1)

        with pytest.raises(ValueError):
            DocpilotConfig(llm_timeout=0)


class TestConfigConversion:
    """Test configuration conversion methods."""

    def test_to_llm_config(self) -> None:
        """Test conversion to LLMConfig."""
        config = DocpilotConfig(
            llm_provider=LLMProvider.OPENAI,
            llm_model="gpt-4",
            llm_api_key="test-key",
            llm_temperature=0.8,
            llm_max_tokens=3000,
            llm_timeout=60,
        )

        llm_config = config.to_llm_config()

        assert llm_config.provider == LLMProvider.OPENAI
        assert llm_config.model == "gpt-4"
        assert llm_config.api_key == "test-key"
        assert llm_config.temperature == 0.8
        assert llm_config.max_tokens == 3000
        assert llm_config.timeout == 60

    def test_to_llm_config_with_base_url(self) -> None:
        """Test LLMConfig conversion with base_url."""
        config = DocpilotConfig(
            llm_provider=LLMProvider.LOCAL,
            llm_model="llama2",
            llm_base_url="http://localhost:11434",
        )

        llm_config = config.to_llm_config()

        assert llm_config.provider == LLMProvider.LOCAL
        assert llm_config.model == "llama2"
        assert llm_config.base_url == "http://localhost:11434"


class TestEnvVarLoading:
    """Test environment variable loading."""

    def test_env_vars_loaded_with_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables with DOCPILOT_ prefix are loaded."""
        monkeypatch.setenv("DOCPILOT_STYLE", "numpy")
        monkeypatch.setenv("DOCPILOT_OVERWRITE", "true")
        monkeypatch.setenv("DOCPILOT_INCLUDE_PRIVATE", "true")
        monkeypatch.setenv("DOCPILOT_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("DOCPILOT_LLM_MODEL", "claude-3-sonnet")

        config = DocpilotConfig()

        assert config.style == DocstringStyle.NUMPY
        assert config.overwrite is True
        assert config.include_private is True
        assert config.llm_provider == LLMProvider.ANTHROPIC
        assert config.llm_model == "claude-3-sonnet"

    def test_env_vars_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables are case insensitive."""
        monkeypatch.setenv("DOCPILOT_STYLE", "NUMPY")
        monkeypatch.setenv("DOCPILOT_LLM_PROVIDER", "OPENAI")

        config = DocpilotConfig()

        assert config.style == DocstringStyle.NUMPY
        assert config.llm_provider == LLMProvider.OPENAI

    def test_dotenv_file_support(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that .env file is loaded if present."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            """DOCPILOT_STYLE=sphinx
DOCPILOT_VERBOSE=true
DOCPILOT_LLM_MODEL=custom-model
"""
        )

        monkeypatch.chdir(tmp_path)

        # Create config which should load .env file
        config = DocpilotConfig(_env_file=str(env_file))

        assert config.style == DocstringStyle.SPHINX
        assert config.verbose is True
        assert config.llm_model == "custom-model"
