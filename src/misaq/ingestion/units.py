"""Deterministic, bounded analysis-unit selection."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from misaq.contracts import Paragraph
from misaq.ingestion.structure import ContractNode


@dataclass(frozen=True)
class AnalysisUnit:
    text: str
    heading: str | None
    label: str | None
    path: str
    parent_path: str | None
    source_indexes: tuple[int, ...]
    source_pages: tuple[int, ...]
    kind: str
    confidence: float
    warnings: tuple[str, ...] = ()

    @property
    def unit_id(self) -> str:
        digest = hashlib.sha256(f"{self.path}\n{self.text}".encode("utf-8")).hexdigest()[:16]
        return f"{self.path.replace('.', '-')}-{digest}"


def _render(node: ContractNode, paragraphs: Sequence[Paragraph], indexes: Sequence[int]) -> str:
    heading = " ".join(x for x in (node.label, node.heading) if x)
    body = " ".join(paragraphs[index].text.strip() for index in indexes if paragraphs[index].text.strip())
    return " ".join(x for x in (heading, body) if x).strip()


def _indexes(node: ContractNode, paragraphs: Sequence[Paragraph]) -> tuple[int, ...]:
    indexes = set(node.body_indexes)
    for child in node.children:
        indexes.update(_indexes(child, paragraphs))
    return tuple(sorted(indexes))


def _make(node: ContractNode, paragraphs: Sequence[Paragraph], indexes: Sequence[int],
          parent_path: str | None, warning: str | None = None) -> AnalysisUnit:
    extra = (warning,) if warning else ()
    warnings = tuple(dict.fromkeys((*node.warnings, *extra)))
    return AnalysisUnit(
        _render(node, paragraphs, indexes), node.heading, node.label, node.path, parent_path,
        tuple(indexes), node.source_pages, node.kind, node.confidence, warnings,
    )


def _count(text: str, tokenizer: Callable[[str], Sequence[int]] | None) -> int:
    return len(tokenizer(text)) if tokenizer else len(re.findall(r"\S+", text))


def _split_node(node: ContractNode, paragraphs: Sequence[Paragraph], max_tokens: int,
                tokenizer: Callable[[str], Sequence[int]] | None) -> list[AnalysisUnit]:
    indexes = _indexes(node, paragraphs)
    whole = _make(node, paragraphs, indexes, None)
    if _count(whole.text, tokenizer) <= max_tokens:
        return [whole]
    parts: list[AnalysisUnit] = []
    children = list(node.children)
    if children:
        for child in children:
            parts.extend(_split_child(child, node, paragraphs, max_tokens, tokenizer))
    else:
        current: list[int] = []
        for index in indexes:
            candidate = [*current, index]
            if current and _count(_render(node, paragraphs, candidate), tokenizer) > max_tokens:
                parts.append(_make(node, paragraphs, current, None))
                current = [index]
            else:
                current = candidate
        if current:
            parts.append(_make(node, paragraphs, current, None))
    if not parts:
        return [_make(node, paragraphs, indexes, None, "Unit could not be split below max_unit_tokens.")]
    result: list[AnalysisUnit] = []
    for part in parts:
        if _count(part.text, tokenizer) > max_tokens:
            result.append(_make(node, paragraphs, part.source_indexes, None,
                                "Unit could not be split below max_unit_tokens."))
        else:
            result.append(part)
    return result


def _split_child(node: ContractNode, parent: ContractNode, paragraphs: Sequence[Paragraph],
                 max_tokens: int, tokenizer: Callable[[str], Sequence[int]] | None) -> list[AnalysisUnit]:
    indexes = _indexes(node, paragraphs)
    unit = _make(node, paragraphs, indexes, parent.path)
    if _count(unit.text, tokenizer) <= max_tokens:
        return [unit]
    return _split_node(node, paragraphs, max_tokens, tokenizer)


def select_units(root: ContractNode, paragraphs: Sequence[Paragraph], max_tokens: int = 400,
                 tiny_tokens: int = 40,
                 tokenizer: Callable[[str], Sequence[int]] | None = None) -> list[AnalysisUnit]:
    if max_tokens <= 0:
        raise ValueError("max_unit_tokens must be positive")
    units: list[AnalysisUnit] = []
    for node in root.children:
        if node.analysis_candidate:
            units.extend(_split_node(node, paragraphs, max_tokens, tokenizer))
    if not units:
        units = [_make(root, paragraphs, _indexes(root, paragraphs), None)]
    merged: list[AnalysisUnit] = []
    for unit in units:
        if merged and _count(unit.text, tokenizer) < tiny_tokens:
            previous = merged[-1]
            indexes = tuple(sorted(set(previous.source_indexes + unit.source_indexes)))
            merged[-1] = _make(
                ContractNode(previous.path, previous.label, previous.heading, indexes, (), previous.kind,
                             previous.confidence, previous.warnings, previous.source_pages, True, None),
                paragraphs, indexes, previous.parent_path,
            )
        else:
            merged.append(unit)
    return merged
