"""OpenAI GPT provider for docstring generation.

This module implements LLM integration with OpenAI's GPT models
(GPT-4, GPT-3.5, etc.) for generating high-quality docstrings.
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


class OpenAIProvider(BaseLLMProvider):
    """LLM provider for OpenAI GPT models.

    Supports GPT-4, GPT-3.5-turbo, and other OpenAI chat models.

    Attributes:
        config: LLM configuration
        client: OpenAI async client
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize OpenAI provider.

        Args:
            config: LLM configuration with OpenAI settings

        Raises:
            ImportError: If openai package is not installed
            ValueError: If API key is not provided
        """
        super().__init__(config)

        try:
            from openai import AsyncOpenAI  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError(
                "OpenAI package not installed. "
                "Install with: pip install docpilot[llm]"
            ) from e

        if not config.api_key:
            raise ValueError("OpenAI API key is required")

        # Initialize client
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
            max_retries=0,  # We handle retries ourselves
        )

        self.logger.info("openai_provider_initialized", model=config.model)

    async def generate_docstring(self, context: DocumentationContext) -> str:
        """Generate a docstring using OpenAI GPT.

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
        """Generate a completion using OpenAI API.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters for the API call

        Returns:
            LLM response

        Raises:
            LLMError: If completion fails
        """
        try:
            # Prepare messages
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert Python developer specializing in documentation.",
                },
                {"role": "user", "content": prompt},
            ]

            # Merge kwargs with config
            params = {
                "model": self.config.model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                **self.config.additional_params,
                **kwargs,
            }

            self.logger.debug("api_request", model=params["model"])

            # Make API call
            response = await self.client.chat.completions.create(**params)

            # Extract content
            content = response.choices[0].message.content or ""

            # Build response object
            llm_response = LLMResponse(
                content=content.strip(),
                model=response.model,
                tokens_used=response.usage.total_tokens if response.usage else None,
                finish_reason=response.choices[0].finish_reason,
                metadata={
                    "id": response.id,
                    "created": response.created,
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
            from openai import (
                APIError as OpenAIAPIError,
            )
            from openai import (
                AuthenticationError as OpenAIAuthError,
            )
            from openai import (
                BadRequestError,
            )
            from openai import (
                RateLimitError as OpenAIRateLimitError,
            )
        except ImportError:
            raise LLMError(
                f"OpenAI API error: {error}",
                provider="openai",
                original_error=error,
            ) from None

        if isinstance(error, OpenAIRateLimitError):
            self.logger.warning("rate_limit_exceeded")
            raise RateLimitError(
                "OpenAI rate limit exceeded. Please try again later.",
                provider="openai",
                original_error=error,
            )

        elif isinstance(error, OpenAIAuthError):
            self.logger.error("authentication_failed")
            raise AuthenticationError(
                "OpenAI authentication failed. Check your API key.",
                provider="openai",
                original_error=error,
            )

        elif isinstance(error, BadRequestError):
            error_msg = str(error)
            if "maximum context length" in error_msg.lower():
                self.logger.error("token_limit_exceeded")
                raise TokenLimitError(
                    "Token limit exceeded. Try reducing input size.",
                    provider="openai",
                    original_error=error,
                )
            else:
                raise APIError(
                    f"OpenAI API error: {error}",
                    provider="openai",
                    original_error=error,
                )

        elif isinstance(error, OpenAIAPIError):
            self.logger.error("api_error", error=str(error))
            raise APIError(
                f"OpenAI API error: {error}",
                provider="openai",
                original_error=error,
            )

        else:
            self.logger.error("unexpected_error", error=str(error))
            raise LLMError(
                f"Unexpected error: {error}",
                provider="openai",
                original_error=error,
            )

    async def test_connection(self) -> bool:
        """Test the connection to OpenAI API.

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
        # Approximate token count (4 chars ≈ 1 token)
        prompt_tokens = len(prompt) // 4

        # Pricing per 1k tokens (as of 2024, adjust as needed)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        }

        # Get pricing for model
        model_key = self.config.model
        for key in pricing:
            if key in model_key:
                model_pricing = pricing[key]
                break
        else:
            # Default to GPT-3.5 pricing
            model_pricing = pricing["gpt-3.5-turbo"]

        input_cost = (prompt_tokens / 1000) * model_pricing["input"]
        output_cost = (completion_tokens / 1000) * model_pricing["output"]
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
