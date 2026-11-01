"""Explicitly unavailable local backend for the feasibility experiment."""
from __future__ import annotations

from .base import BackendResponse, GenerationParams


class LocalBackend:
    def generate(self, prompt: str, params: GenerationParams) -> BackendResponse:
        raise RuntimeError("local feasibility test not run")
