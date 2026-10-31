"""Deterministic chunkers driven by an injected reference tokenizer."""
from __future__ import annotations

import re
from typing import Any, Protocol

from misaq.domain.chunking import Chunk, ChunkingSpec
from misaq.domain.enums import SectionStatus
from misaq.domain.ids import chunk_id
from misaq.domain.statute import Act, Section


class Tokenizer(Protocol):
    def encode(self, text: str, **kwargs: Any) -> list[int]:
        ...

    def decode(self, tokens: list[int], **kwargs: Any) -> str:
        ...


def _header(section: Section) -> str:
    parts = [x for x in (section.chapter, section.subheading, f"Section {section.number}: {section.title}") if x]
    return " | ".join(parts)


def _make_chunk(section: Section, spec: ChunkingSpec, tokenizer: Tokenizer, index: int,
                tokens: list[int], block_ids: tuple[int, ...]) -> Chunk:
    original = re.sub(r"\s+", " ", tokenizer.decode(tokens, skip_special_tokens=True)).strip()
    header = _header(section) if spec.header_prefix else ""
    embedded = f"{header}\n{original}" if header else original
    return Chunk(
        id=chunk_id(section.id, spec.strategy, index), section_id=section.id,
        act=section.act.value, number=section.number, title=section.title,
        chapter=section.chapter, subheading=section.subheading,
        original_text=original, embedded_text=embedded,
        hierarchy=tuple(x for x in (section.chapter, section.subheading, section.title) if x),
        provenance=section.pages, source_block_ids=block_ids,
        footnotes=tuple(f.to_dict() for f in section.footnotes),
    )


def _fit_tokens(section: Section, spec: ChunkingSpec, tokenizer: Tokenizer,
                tokens: list[int], block_ids: tuple[int, ...]) -> list[tuple[list[int], tuple[int, ...]]]:
    original = re.sub(r"\s+", " ", tokenizer.decode(tokens, skip_special_tokens=True)).strip()
    header = _header(section) if spec.header_prefix else ""
    embedded = f"{header}\n{original}" if header else original
    if len(tokenizer.encode(embedded)) <= spec.max_tokens or len(tokens) <= 1:
        if len(tokenizer.encode(embedded)) > spec.max_tokens:
            raise ValueError(f"{section.id}: tokenizer cannot represent a valid chunk within budget")
        return [(tokens, block_ids)]
    midpoint = len(tokens) // 2
    return (_fit_tokens(section, spec, tokenizer, tokens[:midpoint], block_ids)
            + _fit_tokens(section, spec, tokenizer, tokens[midpoint:], block_ids))


def _block_tokens(section: Section, tokenizer: Tokenizer) -> list[tuple[list[int], int]]:
    return [(tokenizer.encode(block.text), i) for i, block in enumerate(section.blocks)]


def _embedded_token_count(section: Section, tokenizer: Tokenizer, tokens: list[int],
                          spec: ChunkingSpec) -> int:
    original = re.sub(r"\s+", " ", tokenizer.decode(tokens, skip_special_tokens=True)).strip()
    header = _header(section) if spec.header_prefix else ""
    embedded = f"{header}\n{original}" if header else original
    return len(tokenizer.encode(embedded, add_special_tokens=True))


def _section_aware(
    section: Section, spec: ChunkingSpec, tokenizer: Tokenizer,
) -> list[tuple[list[int], tuple[int, ...]]]:
    result: list[tuple[list[int], tuple[int, ...]]] = []
    current: list[int] = []
    current_blocks: list[int] = []
    for tokens, block_id in _block_tokens(section, tokenizer):
        if current and _embedded_token_count(section, tokenizer, current + tokens, spec) > spec.max_tokens:
            result.append((current, tuple(current_blocks)))
            current = []
            current_blocks = []
        while tokens and _embedded_token_count(section, tokenizer, current + tokens, spec) > spec.max_tokens:
            low, high = 1, len(tokens)
            best = 0
            while low <= high:
                midpoint = (low + high) // 2
                candidate = current + tokens[:midpoint]
                if _embedded_token_count(section, tokenizer, candidate, spec) <= spec.max_tokens:
                    best = midpoint
                    low = midpoint + 1
                else:
                    high = midpoint - 1
            if best == 0:
                raise ValueError(f"{section.id}: token cannot fit within chunk budget")
            result.append((current + tokens[:best], tuple(current_blocks + [block_id])))
            tokens = tokens[best:]
            current = []
            current_blocks = []
        if tokens:
            current.extend(tokens)
            current_blocks.append(block_id)
    if current:
        result.append((current, tuple(current_blocks)))
    return result


def _fixed_size(section: Section, spec: ChunkingSpec, tokenizer: Tokenizer) -> list[tuple[list[int], tuple[int, ...]]]:
    blocks = _block_tokens(section, tokenizer)
    tokens = [token for block, _ in blocks for token in block]
    owners = [block_id for block, block_id in blocks for _ in block]
    budget = spec.max_tokens
    if spec.header_prefix:
        budget -= len(tokenizer.encode(_header(section)))
    if budget <= 0:
        raise ValueError(f"{section.id}: header exceeds chunk token budget")
    result: list[tuple[list[int], tuple[int, ...]]] = []
    step = budget - spec.overlap_tokens
    for start in range(0, len(tokens), step):
        end = min(start + budget, len(tokens))
        if start >= end:
            break
        result.append((tokens[start:end], tuple(sorted(set(owners[start:end])))))
        if end == len(tokens):
            break
    return result


def chunk_act(act: Act, spec: ChunkingSpec, tokenizer: Tokenizer) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in act.sections:
        if section.status is not SectionStatus.IN_FORCE:
            continue
        parts = (_section_aware if spec.strategy == "section_aware" else _fixed_size)(section, spec, tokenizer)
        fitted = [part for tokens, block_ids in parts for part in
                  _fit_tokens(section, spec, tokenizer, tokens, block_ids)]
        for index, (tokens, block_ids) in enumerate(fitted):
            chunks.append(_make_chunk(section, spec, tokenizer, index, tokens, block_ids))
    return chunks
