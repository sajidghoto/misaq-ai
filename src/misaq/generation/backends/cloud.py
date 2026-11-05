"""Google Gemini cloud backend with explicit no-tools and call controls."""
from __future__ import annotations

import os
import time
from collections import deque
from typing import Any

from .base import (
    AuthError,
    BackendResponse,
    ContentFilterError,
    GenerationParams,
    RateLimitError,
    TimeoutError,
)


class CloudBackend:
    def __init__(
        self, api_key_env: str, requests_per_minute: int, max_calls: int,
        *, client: Any = None, sleep: Any = time.sleep, max_retries: int = 3,
    ):
        if requests_per_minute <= 0 or max_calls < 0:
            raise ValueError("requests_per_minute must be positive and max_calls non-negative")
        self.requests_per_minute = requests_per_minute
        self.max_calls = max_calls
        self._calls = 0
        self._times: deque[float] = deque()
        self._sleep = sleep
        self._max_retries = max_retries
        if client is None:
            api_key = os.environ.get(api_key_env)
            if not api_key:
                raise AuthError(f"missing API key environment variable: {api_key_env}")
            try:
                from google import genai
            except ImportError as error:
                raise RuntimeError("cloud backend requires the optional google-genai package") from error
            client = genai.Client(api_key=api_key)
        self.client = client

    def _limit(self) -> None:
        if self._calls >= self.max_calls:
            raise RateLimitError("configured max_calls exceeded")
        now = time.monotonic()
        while self._times and now - self._times[0] >= 60:
            self._times.popleft()
        if len(self._times) >= self.requests_per_minute:
            wait = 60 - (now - self._times[0])
            self._sleep(max(0.0, wait))
            self._limit()
            return
        self._times.append(time.monotonic())
        self._calls += 1

    def _generate_once(self, prompt: str, params: GenerationParams) -> BackendResponse:
        try:
            from google.genai import types
            if params.structured:
                config = types.GenerateContentConfig(
                    temperature=params.temperature,
                    top_p=params.top_p,
                    max_output_tokens=params.max_output_tokens,
                    seed=params.seed,
                    tools=[],
                    response_mime_type="application/json",
                    response_schema={
                        "type": "OBJECT",
                        "properties": {
                            "claims": {"type": "ARRAY", "items": {"type": "OBJECT"}},
                            "no_supported_provision": {"type": "BOOLEAN"},
                        },
                        "required": ["claims", "no_supported_provision"],
                    },
                )
            else:
                config = types.GenerateContentConfig(
                    temperature=params.temperature,
                    top_p=params.top_p,
                    max_output_tokens=params.max_output_tokens,
                    seed=params.seed,
                    tools=[],
                )
            response = self.client.models.generate_content(
                model=params.model, contents=prompt,
                config=config,
            )
            text = str(getattr(response, "text", "") or "")
            usage = getattr(response, "usage_metadata", None)
            metadata: dict[str, object] = {}
            model_version = getattr(response, "model_version", None)
            if model_version is not None:
                metadata["model_version"] = str(model_version)
            if usage is not None:
                for key, attribute in (
                    ("prompt_tokens", "prompt_token_count"),
                    ("output_tokens", "candidates_token_count"),
                ):
                    value = getattr(usage, attribute, None)
                    if value is not None:
                        metadata[key] = value
            return BackendResponse(text, metadata)
        except Exception as error:
            name = type(error).__name__.casefold()
            message = str(error).casefold()
            if "auth" in name or "permission" in message or "api key" in message:
                raise AuthError("cloud authentication failed") from error
            if "timeout" in name or "deadline" in message:
                raise TimeoutError("cloud request timed out") from error
            if "rate" in name or "429" in message or "resourceexhausted" in name:
                raise RateLimitError("cloud rate limit") from error
            if "safety" in name or "blocked" in message or "filter" in message:
                raise ContentFilterError("cloud content filter") from error
            raise

    def generate(self, prompt: str, params: GenerationParams) -> BackendResponse:
        self._limit()
        for attempt in range(self._max_retries + 1):
            try:
                return self._generate_once(prompt, params)
            except (RateLimitError, TimeoutError):
                if attempt >= self._max_retries:
                    raise
                self._sleep(min(60.0, 2 ** attempt))
        raise RuntimeError("unreachable generation retry state")
