"""File-backed prompt assembly for the fixed S1-S4 protocol."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from misaq.domain.generation import Clause

PROMPT_DIR = Path(__file__).with_name("prompts")


def prompt_hashes() -> dict[str, str]:
    return {
        path.stem: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(PROMPT_DIR.glob("*.txt"))
    }


def _sections(sections: Iterable[dict[str, str]]) -> str:
    return "\n\n".join(f"[{item['id']}] {item['act']}\n{item['text']}" for item in sections)


def assemble_prompt(
    system: str, clause: Clause, *, retrieved: Iterable[dict[str, str]] = (),
    oracle: Iterable[dict[str, str]] = (),
) -> str:
    if system not in {"S1", "S2", "S3", "S4"}:
        raise ValueError(f"unknown system: {system}")
    template = (PROMPT_DIR / {
        "S1": "s1_plain.txt", "S2": "s2_structured.txt",
        "S3": "s3_s4_grounded.txt", "S4": "s3_s4_grounded.txt",
    }[system]).read_text(encoding="utf-8")
    prompt = template.replace("{{CLAUSE}}", clause.text)
    if system == "S3":
        return prompt.replace("{{SECTIONS}}", _sections(retrieved))
    if system == "S4":
        values = tuple(oracle)
        evidence = _sections(values) if values else "No in-scope provision was identified for this clause."
        return prompt.replace("{{SECTIONS}}", evidence)
    return prompt.replace("{{SECTIONS}}", "")


def parse_structured(text: str) -> dict[str, object]:
    import json

    value = json.loads(text)
    if not isinstance(value, dict) or not isinstance(value.get("claims"), list) \
            or not isinstance(value.get("no_supported_provision"), bool):
        raise ValueError("structured output does not match the required schema")
    for claim in value["claims"]:
        if not isinstance(claim, dict) or not all(isinstance(claim.get(key), str) for key in ("issue", "explanation")) \
                or not isinstance(claim.get("citations"), list) \
                or not all(isinstance(item, str) for item in claim["citations"]):
            raise ValueError("invalid claim in structured output")
    return value
