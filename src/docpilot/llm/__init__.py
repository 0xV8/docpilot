"""LLM integration layer for AI-powered docstring generation."""

from docpilot.llm.base import (
    BaseLLMProvider,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    LLMError,
    RateLimitError,
    APIError,
    AuthenticationError,
    TokenLimitError,
    create_provider,
)
from docpilot.llm.openai import OpenAIProvider
from docpilot.llm.anthropic import AnthropicProvider
from docpilot.llm.local import LocalProvider, HTTPLocalProvider

__all__ = [
    "BaseLLMProvider",
    "LLMConfig",
    "LLMProvider",
    "LLMResponse",
    "LLMError",
    "RateLimitError",
    "APIError",
    "AuthenticationError",
    "TokenLimitError",
    "create_provider",
    "OpenAIProvider",
    "AnthropicProvider",
    "LocalProvider",
    "HTTPLocalProvider",
]
