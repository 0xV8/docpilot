"""Configuration management for docpilot.

This module handles loading, validating, and managing configuration from
multiple sources (CLI args, config files, environment variables).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from docpilot.core.models import DocstringStyle
from docpilot.llm.base import LLMProvider


class DocpilotConfig(BaseSettings):
    """Main configuration for docpilot.

    Configuration is loaded in this order (later sources override earlier):
    1. Default values
    2. Config file (pyproject.toml or docpilot.toml)
    3. Environment variables (DOCPILOT_*)
    4. CLI arguments

    Attributes:
        style: Docstring style to use
        overwrite: Whether to overwrite existing docstrings
        include_private: Include private elements (leading underscore)
        analyze_code: Perform code analysis for enhanced metadata
        calculate_complexity: Calculate cyclomatic complexity
        infer_types: Attempt type inference for untyped code
        detect_patterns: Detect common code patterns
        include_examples: Include usage examples in docstrings
        max_line_length: Maximum line length for docstrings
        file_pattern: Glob pattern for finding Python files
        exclude_patterns: Patterns to exclude from processing
        llm_provider: LLM provider to use
        llm_model: LLM model name
        llm_api_key: API key for LLM provider
        llm_base_url: Base URL for LLM API
        llm_temperature: Sampling temperature
        llm_max_tokens: Maximum tokens in response
        llm_timeout: Request timeout in seconds
        project_name: Project name for context
        project_description: Project description for context
        verbose: Enable verbose logging
        quiet: Suppress all non-error output
        log_level: Logging level
        log_format: Log format (json or console)
    """

    model_config = SettingsConfigDict(
        env_prefix="DOCPILOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Docstring settings
    style: DocstringStyle = Field(
        default=DocstringStyle.GOOGLE,
        description="Docstring style to use",
    )
    overwrite: bool = Field(
        default=False,
        description="Overwrite existing docstrings",
    )
    include_private: bool = Field(
        default=False,
        description="Include private elements",
    )

    # Analysis settings
    analyze_code: bool = Field(
        default=True,
        description="Perform code analysis",
    )
    calculate_complexity: bool = Field(
        default=True,
        description="Calculate complexity metrics",
    )
    infer_types: bool = Field(
        default=True,
        description="Infer types from usage",
    )
    detect_patterns: bool = Field(
        default=True,
        description="Detect code patterns",
    )

    # Generation settings
    include_examples: bool = Field(
        default=True,
        description="Include usage examples",
    )
    max_line_length: int = Field(
        default=88,
        ge=40,
        le=200,
        description="Maximum line length",
    )

    # File processing
    file_pattern: str = Field(
        default="**/*.py",
        description="File pattern for discovery",
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/test_*.py",
            "**/*_test.py",
            "**/tests/**",
            "**/__pycache__/**",
            "**/.*/**",
        ],
        description="Patterns to exclude",
    )

    # LLM settings
    llm_provider: LLMProvider = Field(
        default=LLMProvider.OPENAI,
        description="LLM provider",
    )
    llm_model: str = Field(
        default="gpt-3.5-turbo",
        description="LLM model name",
    )
    llm_api_key: str | None = Field(
        default=None,
        description="LLM API key",
    )
    llm_base_url: str | None = Field(
        default=None,
        description="LLM base URL",
    )
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="LLM temperature",
    )
    llm_max_tokens: int = Field(
        default=2000,
        gt=0,
        description="LLM max tokens",
    )
    llm_timeout: int = Field(
        default=30,
        gt=0,
        description="LLM timeout (seconds)",
    )

    # Project context
    project_name: str | None = Field(
        default=None,
        description="Project name",
    )
    project_description: str | None = Field(
        default=None,
        description="Project description",
    )

    # Logging
    verbose: bool = Field(
        default=False,
        description="Verbose output",
    )
    quiet: bool = Field(
        default=False,
        description="Quiet mode",
    )
    log_level: str = Field(
        default="INFO",
        description="Log level",
    )
    log_format: str = Field(
        default="console",
        description="Log format (json or console)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = ["json", "console"]
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"Invalid log format: {v}. Must be one of {valid_formats}")
        return v_lower

    def to_llm_config(self) -> Any:
        """Convert to LLMConfig.

        Returns:
            LLMConfig instance
        """
        from docpilot.llm.base import LLMConfig

        return LLMConfig(
            provider=self.llm_provider,
            model=self.llm_model,
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            temperature=self.llm_temperature,
            max_tokens=self.llm_max_tokens,
            timeout=self.llm_timeout,
        )


def load_config(
    config_path: Path | None = None,
    **overrides: Any,
) -> DocpilotConfig:
    """Load configuration from file and environment.

    Args:
        config_path: Path to config file (searches for default if not provided)
        **overrides: Configuration overrides from CLI

    Returns:
        Loaded configuration

    Raises:
        FileNotFoundError: If specified config file doesn't exist
        ValueError: If config file is invalid
    """
    # Find config file if not specified
    if config_path is None:
        config_path = find_config_file()

    # Load from file if exists
    file_config: dict[str, Any] = {}
    if config_path and config_path.exists():
        file_config = load_config_file(config_path)

    # Merge file config with overrides
    merged_config = {**file_config, **overrides}

    # Remove None values from overrides
    merged_config = {k: v for k, v in merged_config.items() if v is not None}

    # Create config instance
    return DocpilotConfig(**merged_config)


def find_config_file() -> Path | None:
    """Search for a config file in standard locations.

    Searches in this order:
    1. ./docpilot.toml
    2. ./pyproject.toml (with [tool.docpilot] section)
    3. ../.docpilot.toml
    4. ~/.config/docpilot/config.toml

    Returns:
        Path to config file if found, None otherwise
    """
    search_paths = [
        Path.cwd() / "docpilot.toml",
        Path.cwd() / "pyproject.toml",
        Path.cwd().parent / ".docpilot.toml",
        Path.home() / ".config" / "docpilot" / "config.toml",
    ]

    for path in search_paths:
        if path.exists():
            # For pyproject.toml, check if it has docpilot section
            if path.name == "pyproject.toml":
                try:
                    with open(path, "rb") as f:
                        data = tomllib.load(f)
                    if "tool" in data and "docpilot" in data["tool"]:
                        return path
                except Exception:
                    continue
            else:
                return path

    return None


def load_config_file(config_path: Path) -> dict[str, Any]:
    """Load configuration from a TOML file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is invalid TOML
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Extract docpilot section
        if config_path.name == "pyproject.toml":
            config: dict[str, Any] = data.get("tool", {}).get("docpilot", {})
        else:
            config = data.get("docpilot", data)

        return config

    except Exception as e:
        raise ValueError(f"Invalid config file {config_path}: {e}") from e


def create_default_config(output_path: Path) -> None:
    """Create a default configuration file.

    Args:
        output_path: Where to write the config file

    Raises:
        FileExistsError: If file already exists
    """
    if output_path.exists():
        raise FileExistsError(f"Config file already exists: {output_path}")

    default_config = """# docpilot configuration

[docpilot]
# Docstring style: google, numpy, sphinx, or auto
style = "google"

# Overwrite existing docstrings
overwrite = false

# Include private elements (with leading underscore)
include_private = false

# Code analysis options
analyze_code = true
calculate_complexity = true
infer_types = true
detect_patterns = true

# Generation options
include_examples = true
max_line_length = 88

# File patterns
file_pattern = "**/*.py"
exclude_patterns = [
    "**/test_*.py",
    "**/*_test.py",
    "**/tests/**",
    "**/__pycache__/**",
    "**/.*/**",
]

# LLM settings
llm_provider = "openai"
llm_model = "gpt-3.5-turbo"
# llm_api_key = "your-api-key-here"  # Or use DOCPILOT_LLM_API_KEY env var
llm_temperature = 0.7
llm_max_tokens = 2000
llm_timeout = 30

# Project context (optional)
# project_name = "My Project"
# project_description = "A brief description"

# Logging
verbose = false
quiet = false
log_level = "INFO"
log_format = "console"
"""

    output_path.write_text(default_config)


def get_api_key(provider: LLMProvider) -> str | None:
    """Get API key from environment variables.

    Args:
        provider: LLM provider

    Returns:
        API key if found in environment
    """
    env_vars = {
        LLMProvider.OPENAI: ["OPENAI_API_KEY", "DOCPILOT_LLM_API_KEY"],
        LLMProvider.ANTHROPIC: ["ANTHROPIC_API_KEY", "DOCPILOT_LLM_API_KEY"],
        LLMProvider.LOCAL: [],  # No API key needed
        LLMProvider.MOCK: [],  # No API key needed
    }

    for env_var in env_vars.get(provider, []):
        api_key = os.getenv(env_var)
        if api_key:
            return api_key

    return None
