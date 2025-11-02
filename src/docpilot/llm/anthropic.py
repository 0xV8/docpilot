"""Anthropic Claude provider for docstring generation.

This module implements LLM integration with Anthropic's Claude models
for generating high-quality docstrings.
"""

from __future__ import annotations

from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from docpilot.core.models import DocumentationContext
from docpilot.llm.base import (
    APIError,
    AuthenticationError,
    BaseLLMProvider,
    LLMConfig,
    LLMError,
    LLMResponse,
    RateLimitError,
    TokenLimitError,
)


class AnthropicProvider(BaseLLMProvider):
    """LLM provider for Anthropic Claude models.

    Supports Claude 3 family (Opus, Sonnet, Haiku) and Claude 2.

    Attributes:
        config: LLM configuration
        client: Anthropic async client
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize Anthropic provider.

        Args:
            config: LLM configuration with Anthropic settings

        Raises:
            ImportError: If anthropic package is not installed
            ValueError: If API key is not provided
        """
        super().__init__(config)

        try:
            from anthropic import AsyncAnthropic  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError(
                "Anthropic package not installed. "
                "Install with: pip install docpilot[llm]"
            ) from e

        if not config.api_key:
            raise ValueError("Anthropic API key is required")

        # Initialize client
        self.client = AsyncAnthropic(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,  # We handle retries ourselves
        )

        self.logger.info("anthropic_provider_initialized", model=config.model)

    async def generate_docstring(self, context: DocumentationContext) -> str:
        """Generate a docstring using Claude.

        Args:
            context: Documentation context

        Returns:
            Generated docstring content

        Raises:
            LLMError: If generation fails
        """
        prompt = self.build_docstring_prompt(context)

        self.logger.debug(
            "generating_docstring",
            element=context.element.name,
            style=context.style.value,
        )

        try:
            response = await self.complete(prompt)

            if not self.validate_response(response.content, context.element):
                self.logger.warning(
                    "invalid_response",
                    element=context.element.name,
                )

            return response.content

        except Exception as e:
            self.logger.error(
                "generation_failed",
                element=context.element.name,
                error=str(e),
            )
            raise

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a completion using Anthropic API.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters for the API call

        Returns:
            LLM response

        Raises:
            LLMError: If completion fails
        """
        try:
            # Prepare parameters
            params = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": [{"role": "user", "content": prompt}],
                **self.config.additional_params,
                **kwargs,
            }

            # Add system prompt if Claude 3+
            if "claude-3" in self.config.model or "claude-4" in self.config.model:
                params["system"] = (
                    "You are an expert Python developer specializing in "
                    "writing clear, comprehensive documentation."
                )

            self.logger.debug("api_request", model=params["model"])

            # Make API call
            response = await self.client.messages.create(**params)

            # Extract content
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            # Build response object
            llm_response = LLMResponse(
                content=content.strip(),
                model=response.model,
                tokens_used=(
                    response.usage.input_tokens + response.usage.output_tokens
                    if response.usage
                    else None
                ),
                finish_reason=response.stop_reason,
                metadata={
                    "id": response.id,
                    "input_tokens": (
                        response.usage.input_tokens if response.usage else None
                    ),
                    "output_tokens": (
                        response.usage.output_tokens if response.usage else None
                    ),
                },
            )

            self.logger.info(
                "completion_success",
                tokens=llm_response.tokens_used,
                finish_reason=llm_response.finish_reason,
            )

            return llm_response

        except Exception as e:
            return await self._handle_error(e)

    async def _handle_error(self, error: Exception) -> LLMResponse:
        """Handle API errors and convert to appropriate exceptions.

        Args:
            error: Original exception

        Returns:
            Never returns, always raises

        Raises:
            LLMError: Appropriate LLM error based on the original error
        """
        try:
            from anthropic import (
                APIError as AnthropicAPIError,
            )
            from anthropic import (
                AuthenticationError as AnthropicAuthError,
            )
            from anthropic import (
                BadRequestError,
            )
            from anthropic import (
                RateLimitError as AnthropicRateLimitError,
            )
        except ImportError:
            raise LLMError(
                f"Anthropic API error: {error}",
                provider="anthropic",
                original_error=error,
            ) from error

        if isinstance(error, AnthropicRateLimitError):
            self.logger.warning("rate_limit_exceeded")
            raise RateLimitError(
                "Anthropic rate limit exceeded. Please try again later.",
                provider="anthropic",
                original_error=error,
            )

        elif isinstance(error, AnthropicAuthError):
            self.logger.error("authentication_failed")
            raise AuthenticationError(
                "Anthropic authentication failed. Check your API key.",
                provider="anthropic",
                original_error=error,
            )

        elif isinstance(error, BadRequestError):
            error_msg = str(error)
            if "prompt is too long" in error_msg.lower():
                self.logger.error("token_limit_exceeded")
                raise TokenLimitError(
                    "Token limit exceeded. Try reducing input size.",
                    provider="anthropic",
                    original_error=error,
                )
            else:
                raise APIError(
                    f"Anthropic API error: {error}",
                    provider="anthropic",
                    original_error=error,
                )

        elif isinstance(error, AnthropicAPIError):
            self.logger.error("api_error", error=str(error))
            raise APIError(
                f"Anthropic API error: {error}",
                provider="anthropic",
                original_error=error,
            )

        else:
            self.logger.error("unexpected_error", error=str(error))
            raise LLMError(
                f"Unexpected error: {error}",
                provider="anthropic",
                original_error=error,
            )

    async def test_connection(self) -> bool:
        """Test the connection to Anthropic API.

        Returns:
            True if connection is successful

        Raises:
            LLMError: If connection fails
        """
        try:
            response = await self.complete("Hello, please respond with 'OK'.")
            return bool(response.content)
        except Exception as e:
            self.logger.error("connection_test_failed", error=str(e))
            raise

    async def estimate_cost(
        self, prompt: str, completion_tokens: int = 500
    ) -> dict[str, float | str]:
        """Estimate the cost of a completion.

        Args:
            prompt: Input prompt
            completion_tokens: Estimated completion tokens

        Returns:
            Dictionary with cost estimates
        """
        # Approximate token count
        prompt_tokens = len(prompt) // 4

        # Pricing per 1M tokens (as of 2024, adjust as needed)
        pricing = {
            "claude-3-opus": {"input": 15.00, "output": 75.00},
            "claude-3-sonnet": {"input": 3.00, "output": 15.00},
            "claude-3-haiku": {"input": 0.25, "output": 1.25},
            "claude-2": {"input": 8.00, "output": 24.00},
        }

        # Get pricing for model
        model_key = self.config.model
        for key in pricing:
            if key in model_key:
                model_pricing = pricing[key]
                break
        else:
            # Default to Haiku pricing
            model_pricing = pricing["claude-3-haiku"]

        input_cost = (prompt_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * model_pricing["output"]
        total_cost = input_cost + output_cost

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "currency": "USD",
        }
