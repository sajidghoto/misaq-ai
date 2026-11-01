"""Backend protocol and provider-neutral errors."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class BackendError(RuntimeError):
    """Base class for generation failures."""


class RateLimitError(BackendError):
    pass


class TimeoutError(BackendError):
    pass


class ContentFilterError(BackendError):
    pass


class AuthError(BackendError):
    pass


@dataclass(frozen=True)
class GenerationParams:
    model: str
    temperature: float
    top_p: float
    max_output_tokens: int
    seed: int | None = None
    structured: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model, "temperature": self.temperature, "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens, "seed": self.seed,
            "structured": self.structured,
        }


@dataclass(frozen=True)
class BackendResponse:
    raw_text: str
    metadata: dict[str, object] = field(default_factory=dict)


class GenerationBackend(Protocol):
    def generate(self, prompt: str, params: GenerationParams) -> BackendResponse:
        ...
