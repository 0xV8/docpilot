"""Base LLM provider interface and utilities.

This module defines the abstract interface that all LLM providers must
implement, along with common utilities for prompt construction and
response handling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

import structlog
from pydantic import BaseModel, ConfigDict, Field

from docpilot.core.models import DocumentationContext, CodeElement, CodeElementType


logger = structlog.get_logger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    MOCK = "mock"


class LLMConfig(BaseModel):
    """Configuration for LLM providers.

    Attributes:
        provider: LLM provider to use
        model: Model name/identifier
        api_key: API key for authentication
        base_url: Base URL for API (for local/custom endpoints)
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        rate_limit_rpm: Rate limit in requests per minute
        additional_params: Provider-specific additional parameters
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2000, gt=0)
    timeout: int = Field(default=30, gt=0)
    max_retries: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, ge=0.0)
    rate_limit_rpm: Optional[int] = Field(default=None, gt=0)
    additional_params: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    """Response from an LLM provider.

    Attributes:
        content: Generated text content
        model: Model that generated the response
        tokens_used: Number of tokens consumed
        finish_reason: Reason for completion (e.g., 'stop', 'length')
        metadata: Additional response metadata
    """

    content: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM provider implementations must inherit from this class
    and implement the required methods.

    Attributes:
        config: LLM configuration
        logger: Structured logger instance
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize the LLM provider.

        Args:
            config: LLM configuration
        """
        self.config = config
        self.logger = logger.bind(
            provider=config.provider.value,
            model=config.model,
        )

    @abstractmethod
    async def generate_docstring(self, context: DocumentationContext) -> str:
        """Generate a docstring for a code element.

        Args:
            context: Documentation context with code element and settings

        Returns:
            Generated docstring content

        Raises:
            LLMError: If generation fails
        """
        pass

    @abstractmethod
    async def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a completion for a prompt.

        Args:
            prompt: Input prompt
            **kwargs: Additional provider-specific parameters

        Returns:
            LLM response

        Raises:
            LLMError: If completion fails
        """
        pass

    def build_docstring_prompt(self, context: DocumentationContext) -> str:
        """Build a prompt for docstring generation.

        Args:
            context: Documentation context

        Returns:
            Formatted prompt for the LLM
        """
        element = context.element
        lines: list[str] = []

        # System context
        lines.append("You are an expert Python developer writing comprehensive docstrings.")
        lines.append(
            f"Generate a {context.style.value}-style docstring for the following code element."
        )
        lines.append("")

        # Project context
        if context.project_name:
            lines.append(f"Project: {context.project_name}")
        if context.project_description:
            lines.append(f"Description: {context.project_description}")
        if context.project_name or context.project_description:
            lines.append("")

        # Code element information
        lines.append(f"Element Type: {element.element_type.value}")
        lines.append(f"Name: {element.name}")

        if element.parent_class:
            lines.append(f"Parent Class: {element.parent_class}")

        lines.append("")
        lines.append("Source Code:")
        lines.append("```python")
        lines.append(element.source_code)
        lines.append("```")
        lines.append("")

        # Metadata
        if element.complexity_score:
            lines.append(f"Complexity Score: {element.complexity_score}")

        if element.metadata.get("patterns"):
            patterns = element.metadata["patterns"]
            lines.append(f"Detected Patterns: {', '.join(patterns)}")

        if element.is_abstract:
            lines.append("Note: This is an abstract element")

        if element.is_async:
            lines.append("Note: This is an async function")

        # Context elements (related code)
        if context.context_elements:
            lines.append("")
            lines.append("Related Code Elements:")
            for ctx_elem in context.context_elements[:3]:  # Limit to 3
                lines.append(f"- {ctx_elem.full_name} ({ctx_elem.element_type.value})")

        lines.append("")

        # Instructions
        lines.append("Requirements:")
        lines.append(f"- Use {context.style.value} docstring style")
        lines.append("- Be concise but comprehensive")
        lines.append("- Include all parameters, returns, and raised exceptions")

        if context.include_examples and element.complexity_score and element.complexity_score > 5:
            lines.append("- Include a usage example")

        if context.include_type_hints and element.parameters:
            lines.append("- Reference type hints in parameter descriptions")

        if context.infer_types:
            lines.append("- Infer types from context if not explicitly typed")

        if context.custom_instructions:
            lines.append(f"- {context.custom_instructions}")

        lines.append("")
        lines.append("Generate only the docstring content (without the triple quotes).")

        return "\n".join(lines)

    def validate_response(self, response: str, element: CodeElement) -> bool:
        """Validate that a generated docstring is reasonable.

        Args:
            response: Generated docstring
            element: Code element being documented

        Returns:
            True if response appears valid
        """
        if not response or not response.strip():
            self.logger.warning("empty_response", element=element.name)
            return False

        # Check minimum length
        if len(response.split()) < 3:
            self.logger.warning(
                "response_too_short",
                element=element.name,
                word_count=len(response.split()),
            )
            return False

        # For functions with parameters, check if they're mentioned
        if element.parameters:
            param_names = {
                p.name for p in element.parameters if p.name not in ("self", "cls")
            }
            mentioned_params = {
                name for name in param_names if name in response.lower()
            }

            # At least half of parameters should be mentioned
            if param_names and len(mentioned_params) < len(param_names) / 2:
                self.logger.warning(
                    "missing_parameters",
                    element=element.name,
                    expected=len(param_names),
                    found=len(mentioned_params),
                )

        return True


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """Initialize LLM error.

        Args:
            message: Error message
            provider: LLM provider name
            original_error: Original exception if this wraps another error
        """
        super().__init__(message)
        self.provider = provider
        self.original_error = original_error


class RateLimitError(LLMError):
    """Exception raised when rate limit is exceeded."""

    pass


class APIError(LLMError):
    """Exception raised for API-related errors."""

    pass


class AuthenticationError(LLMError):
    """Exception raised for authentication failures."""

    pass


class TokenLimitError(LLMError):
    """Exception raised when token limit is exceeded."""

    pass


def create_provider(config: LLMConfig) -> BaseLLMProvider:
    """Factory function to create an LLM provider.

    Args:
        config: LLM configuration

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider is not supported
    """
    from docpilot.core.generator import MockLLMProvider

    if config.provider == LLMProvider.MOCK:
        return MockLLMProvider()  # type: ignore

    elif config.provider == LLMProvider.OPENAI:
        from docpilot.llm.openai import OpenAIProvider

        return OpenAIProvider(config)

    elif config.provider == LLMProvider.ANTHROPIC:
        from docpilot.llm.anthropic import AnthropicProvider

        return AnthropicProvider(config)

    elif config.provider == LLMProvider.LOCAL:
        from docpilot.llm.local import LocalProvider

        return LocalProvider(config)

    else:
        raise ValueError(f"Unsupported provider: {config.provider}")
