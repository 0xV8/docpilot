"""Local LLM provider for docstring generation using Ollama.

This module implements integration with locally-hosted LLMs via Ollama,
allowing docstring generation without external API calls.
"""

from __future__ import annotations

import asyncio
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
    BaseLLMProvider,
    LLMConfig,
    LLMResponse,
)


class LocalProvider(BaseLLMProvider):
    """LLM provider for local models via Ollama.

    Supports any model available in Ollama (Llama 2, Mistral, CodeLlama, etc.).

    Attributes:
        config: LLM configuration
        client: Ollama client (if package available)
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize local LLM provider.

        Args:
            config: LLM configuration with local settings

        Raises:
            ImportError: If ollama package is not installed
        """
        super().__init__(config)

        try:
            import ollama

            self.ollama = ollama
            self.client = ollama.AsyncClient(
                host=config.base_url or "http://localhost:11434"
            )
        except ImportError as e:
            raise ImportError(
                "Ollama package not installed. "
                "Install with: pip install docpilot[ollama]"
            ) from e

        self.logger.info(
            "local_provider_initialized",
            model=config.model,
            base_url=config.base_url or "http://localhost:11434",
        )

    async def generate_docstring(self, context: DocumentationContext) -> str:
        """Generate a docstring using local LLM.

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
        retry=retry_if_exception_type(APIError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a completion using Ollama.

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
                "prompt": prompt,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                    **self.config.additional_params,
                },
                "stream": False,
                **kwargs,
            }

            self.logger.debug("api_request", model=params["model"])

            # Make API call
            response = await self.client.generate(**params)

            # Extract content
            content = response.get("response", "")

            # Calculate total tokens (approximate)
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)
            total_tokens = prompt_tokens + completion_tokens

            # Build response object
            llm_response = LLMResponse(
                content=content.strip(),
                model=response.get("model", self.config.model),
                tokens_used=total_tokens if total_tokens > 0 else None,
                finish_reason="stop" if response.get("done") else None,
                metadata={
                    "total_duration": response.get("total_duration"),
                    "load_duration": response.get("load_duration"),
                    "prompt_eval_duration": response.get("prompt_eval_duration"),
                    "eval_duration": response.get("eval_duration"),
                },
            )

            self.logger.info(
                "completion_success",
                tokens=llm_response.tokens_used,
                duration_ms=response.get("total_duration", 0) // 1_000_000,
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
        error_msg = str(error).lower()

        if "connection" in error_msg or "refused" in error_msg:
            self.logger.error("connection_failed")
            raise APIError(
                "Cannot connect to Ollama. Is it running? Start with: ollama serve",
                provider="local",
                original_error=error,
            )

        elif "not found" in error_msg or "model" in error_msg:
            self.logger.error("model_not_found", model=self.config.model)
            raise APIError(
                f"Model '{self.config.model}' not found. "
                f"Pull it with: ollama pull {self.config.model}",
                provider="local",
                original_error=error,
            )

        else:
            self.logger.error("api_error", error=str(error))
            raise APIError(
                f"Ollama API error: {error}",
                provider="local",
                original_error=error,
            )

    async def test_connection(self) -> bool:
        """Test the connection to Ollama.

        Returns:
            True if connection is successful

        Raises:
            LLMError: If connection fails
        """
        try:
            # Try to list models
            await self.client.list()
            return True
        except Exception as e:
            self.logger.error("connection_test_failed", error=str(e))
            raise APIError(
                "Cannot connect to Ollama. Is it running?",
                provider="local",
                original_error=e,
            ) from e

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models in Ollama.

        Returns:
            List of model information dictionaries

        Raises:
            LLMError: If listing fails
        """
        try:
            response = await self.client.list()
            models = response.get("models", [])

            return [
                {
                    "name": model.get("name"),
                    "size": model.get("size"),
                    "modified_at": model.get("modified_at"),
                }
                for model in models
            ]

        except Exception as e:
            self.logger.error("list_models_failed", error=str(e))
            raise APIError(
                f"Failed to list models: {e}",
                provider="local",
                original_error=e,
            ) from e

    async def pull_model(self, model_name: str | None = None) -> None:
        """Pull a model from Ollama registry.

        Args:
            model_name: Model name to pull (uses config model if not specified)

        Raises:
            LLMError: If pull fails
        """
        model = model_name or self.config.model

        try:
            self.logger.info("pulling_model", model=model)

            # Ollama pull is synchronous, run in thread pool
            import ollama

            await asyncio.get_event_loop().run_in_executor(None, ollama.pull, model)

            self.logger.info("model_pulled", model=model)

        except Exception as e:
            self.logger.error("pull_model_failed", model=model, error=str(e))
            raise APIError(
                f"Failed to pull model {model}: {e}",
                provider="local",
                original_error=e,
            ) from e

    async def estimate_cost(
        self, prompt: str, completion_tokens: int = 500
    ) -> dict[str, float | str]:
        """Estimate the cost of a completion (always $0 for local).

        Args:
            prompt: Input prompt
            completion_tokens: Estimated completion tokens

        Returns:
            Dictionary with cost estimates (all zeros for local)
        """
        prompt_tokens = len(prompt) // 4

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0,
            "currency": "USD",
            "note": "Local models are free to run",
        }


class HTTPLocalProvider(BaseLLMProvider):
    """LLM provider for local models via HTTP API.

    For custom local LLM servers that expose an OpenAI-compatible API.

    Attributes:
        config: LLM configuration
        client: HTTP client for API calls
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize HTTP local provider.

        Args:
            config: LLM configuration with base URL

        Raises:
            ImportError: If httpx package is not installed
            ValueError: If base_url is not provided
        """
        super().__init__(config)

        try:
            import httpx
        except ImportError as e:
            raise ImportError(
                "httpx package not installed. "
                "Install with: pip install docpilot[openai] or pip install docpilot[anthropic]"
            ) from e

        if not config.base_url:
            raise ValueError("base_url is required for HTTP local provider")

        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout,
        )

        self.logger.info(
            "http_local_provider_initialized",
            base_url=config.base_url,
        )

    async def generate_docstring(self, context: DocumentationContext) -> str:
        """Generate a docstring using HTTP local LLM.

        Args:
            context: Documentation context

        Returns:
            Generated docstring content
        """
        prompt = self.build_docstring_prompt(context)
        response = await self.complete(prompt)
        return response.content

    async def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate a completion using HTTP API.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            LLM response

        Raises:
            LLMError: If completion fails
        """
        try:
            # OpenAI-compatible format
            payload = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                **kwargs,
            }

            response = await self.client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            return LLMResponse(
                content=content.strip(),
                model=data.get("model", self.config.model),
                tokens_used=data.get("usage", {}).get("total_tokens"),
                finish_reason=data["choices"][0].get("finish_reason"),
            )

        except Exception as e:
            self.logger.error("http_completion_failed", error=str(e))
            raise APIError(
                f"HTTP API error: {e}",
                provider="http_local",
                original_error=e,
            ) from e

    async def test_connection(self) -> bool:
        """Test the connection to HTTP API.

        Returns:
            True if connection is successful
        """
        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except Exception:
            return False
