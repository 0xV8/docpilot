"""Configuration management for docpilot.

This module handles loading, validating, and managing configuration from
multiple sources (CLI args, config files, environment variables).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import structlog
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from docpilot.core.models import DocstringStyle
from docpilot.llm.base import LLMProvider

logger = structlog.get_logger(__name__)


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

    @field_validator("style", mode="before")
    @classmethod
    def validate_style(cls, v: Any) -> DocstringStyle:
        """Validate and convert docstring style (case-insensitive)."""
        if isinstance(v, DocstringStyle):
            return v
        if isinstance(v, str):
            # Convert to lowercase for case-insensitive matching
            v_lower = v.lower()
            for style in DocstringStyle:
                if style.value == v_lower:
                    return style
            raise ValueError(f"Invalid docstring style: {v}")
        return v

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

    @field_validator("llm_provider", mode="before")
    @classmethod
    def validate_llm_provider(cls, v: Any) -> LLMProvider:
        """Validate and convert LLM provider (case-insensitive)."""
        if isinstance(v, LLMProvider):
            return v
        if isinstance(v, str):
            # Convert to lowercase for case-insensitive matching
            v_lower = v.lower()
            for provider in LLMProvider:
                if provider.value == v_lower:
                    return provider
            raise ValueError(f"Invalid LLM provider: {v}")
        return v
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
        if config_path:
            logger.debug("config_file_found", path=str(config_path))
        else:
            logger.debug("no_config_file_found", message="Using defaults and environment variables")

    # Load from file if exists
    file_config: dict[str, Any] = {}
    if config_path and config_path.exists():
        logger.info("loading_config", path=str(config_path))
        file_config = load_config_file(config_path)
        logger.debug(
            "config_loaded",
            keys=list(file_config.keys()),
            llm_provider=file_config.get("llm_provider"),
            llm_model=file_config.get("llm_model"),
        )

    # Log CLI overrides
    if overrides:
        logger.debug(
            "cli_overrides",
            keys=list(overrides.keys()),
            llm_provider=overrides.get("llm_provider"),
            llm_model=overrides.get("llm_model"),
        )

    # Remove None values from CLI overrides - they shouldn't override anything
    filtered_overrides = {k: v for k, v in overrides.items() if v is not None}

    # Build config with proper precedence: CLI > env > file > defaults
    # We need to carefully merge config sources while respecting precedence

    # Step 1: Start with file config as base
    base_config = file_config.copy() if file_config else {}

    # Step 2: Override file config with values from environment
    # We do this by checking which env vars are set and removing those keys from base_config
    # so that BaseSettings will read them from environment instead
    if file_config:
        for key in list(base_config.keys()):
            env_var = f"DOCPILOT_{key.upper()}"
            if env_var in os.environ:
                # Env var exists, remove from base config so env takes precedence
                del base_config[key]

    # Step 3: Apply CLI overrides (they should override both file and env)
    final_config = {**base_config, **filtered_overrides}

    if filtered_overrides:
        logger.debug(
            "applying_cli_overrides",
            keys=list(filtered_overrides.keys()),
            llm_provider=filtered_overrides.get("llm_provider"),
            llm_model=filtered_overrides.get("llm_model"),
        )

    # Create config instance with merged values
    # The values we pass here will override environment variables
    config = DocpilotConfig(**final_config)

    # Log final configuration settings
    logger.info(
        "config_initialized",
        provider=config.llm_provider.value,
        model=config.llm_model,
        style=config.style.value,
        overwrite=config.overwrite,
        include_private=config.include_private,
        analyze_code=config.analyze_code,
    )

    return config


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

    logger.debug("searching_config_files", paths=[str(p) for p in search_paths])

    for path in search_paths:
        if path.exists():
            # For pyproject.toml, check if it has docpilot section
            if path.name == "pyproject.toml":
                try:
                    with open(path, "rb") as f:
                        data = tomllib.load(f)
                    if "tool" in data and "docpilot" in data["tool"]:
                        logger.debug("config_found_in_pyproject", path=str(path))
                        return path
                except Exception as e:
                    logger.debug("pyproject_read_failed", path=str(path), error=str(e))
                    continue
            else:
                logger.debug("config_found", path=str(path))
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
        logger.error("config_file_not_found", path=str(config_path))
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        logger.debug("reading_config_file", path=str(config_path))
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Extract docpilot section
        if config_path.name == "pyproject.toml":
            config: dict[str, Any] = data.get("tool", {}).get("docpilot", {})
            logger.debug("config_extracted_from_pyproject", settings_count=len(config))
        else:
            config = data.get("docpilot", data)
            logger.debug("config_extracted", settings_count=len(config))

        return config

    except Exception as e:
        logger.error("config_parse_failed", path=str(config_path), error=str(e))
        raise ValueError(f"Invalid config file {config_path}: {e}") from e


def create_default_config(output_path: Path) -> None:
    """Create a default configuration file.

    Args:
        output_path: Where to write the config file

    Raises:
        FileExistsError: If file already exists
    """
    if output_path.exists():
        logger.error("config_already_exists", path=str(output_path))
        raise FileExistsError(f"Config file already exists: {output_path}")

    logger.info("creating_default_config", path=str(output_path))
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
    logger.info("default_config_created", path=str(output_path))


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

    logger.debug("checking_api_key", provider=provider.value)

    for env_var in env_vars.get(provider, []):
        api_key = os.getenv(env_var)
        if api_key:
            logger.debug("api_key_found", env_var=env_var, provider=provider.value)
            return api_key

    if env_vars.get(provider):
        logger.debug("api_key_not_found", provider=provider.value, checked_vars=env_vars.get(provider, []))

    return None
