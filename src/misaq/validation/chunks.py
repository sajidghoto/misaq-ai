"""Chunk integrity checks."""
from __future__ import annotations

from misaq.domain.chunking import Chunk


def validate_chunks(chunks: list[Chunk], token_counts: list[int], max_tokens: int,
                    expected_section_ids: set[str]) -> list[str]:
    failures: list[str] = []
    ids = [chunk.id for chunk in chunks]
    if len(ids) != len(set(ids)):
        failures.append("chunk ids are not unique")
    if len(token_counts) != len(chunks):
        failures.append("token count length does not match chunk count")
    for chunk, count in zip(chunks, token_counts, strict=False):
        if count > max_tokens:
            failures.append(f"{chunk.id}: exceeds token budget")
        if chunk.section_id not in expected_section_ids:
            failures.append(f"{chunk.id}: unknown section")
    seen = {chunk.section_id for chunk in chunks}
    missing = expected_section_ids - seen
    if missing:
        failures.append(f"sections without chunks: {sorted(missing)}")
    for chunk in chunks:
        if chunk.section_id != chunk.id.split("#", 1)[0]:
            failures.append(f"{chunk.id}: id section mismatch")
    return failures
