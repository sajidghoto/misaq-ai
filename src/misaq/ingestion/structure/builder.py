from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from misaq.contracts import Paragraph


@dataclass(frozen=True)
class ContractNode:
    path: str
    label: str | None
    heading: str | None
    body_indexes: tuple[int, ...]
    children: tuple["ContractNode", ...]
    kind: str
    confidence: float
    warnings: tuple[str, ...] = ()
    source_pages: tuple[int, ...] = ()
    analysis_candidate: bool = False
    scheme: str | None = None

    @property
    def low_confidence(self) -> bool:
        return self.confidence < 1.0


@dataclass(frozen=True)
class StructureConfig:
    heading_keywords: Mapping[str, tuple[str, ...]]
    classification_keywords: Mapping[str, tuple[str, ...]]
    false_label_starts: tuple[str, ...]
    heading_max_words: int
    heading_max_chars: int
    min_sequence_confidence: float
    heading_confidence: float
    numbering_confidence: float
    layout_agreement_weight: float
    sequence_agreement_weight: float


@dataclass
class _MutableNode:
    path: str
    label: str | None
    heading: str | None
    kind: str
    confidence: float
    warnings: list[str]
    body_indexes: list[int]
    children: list["_MutableNode"]
    scheme: str | None


@dataclass(frozen=True)
class _Label:
    raw: str
    value: tuple[int, ...]
    schemes: tuple[str, ...]
    rest: str


_NUMBER = r"\d+"
_MARKER = r"(?:\([A-Za-zivxlcdmIVXLCDM]+\)|[A-Za-zivxlcdmIVXLCDM]+\))"
_LABEL_RE = re.compile(
    rf"^(?P<label>(?:{_NUMBER}(?:\.\d+)*(?:{_MARKER})*|{_MARKER}|"
    rf"(?:Article|Section|Clause|Schedule|Annexure|Appendix|Exhibit)\s+\d+))"
    rf"(?P<sep>\s+|[.:]\s+)(?P<rest>.+)$",
    re.IGNORECASE,
)
_RUN_IN_RE = re.compile(r"^(?P<head>[A-Z][A-Za-z][A-Za-z &/-]{1,70})\.\s+(?P<rest>.+)$")
_SCHEME_WORDS = {
    "article": "article",
    "section": "section",
    "clause": "clause",
    "schedule": "schedule",
    "annexure": "annexure",
    "appendix": "appendix",
    "exhibit": "exhibit",
}


def load_structure_config(path: Path | str | None = None) -> StructureConfig:
    config_path = Path(path) if path else Path(__file__).resolve().parents[4] / "configs" / "ingestion.yaml"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    thresholds = data["thresholds"]
    structure = data["structure"]
    return StructureConfig(
        heading_keywords={key: tuple(value) for key, value in data["heading_keywords"].items()},
        classification_keywords={key: tuple(value) for key, value in data["classification_keywords"].items()},
        false_label_starts=tuple(structure["false_label_starts"]),
        heading_max_words=int(structure["heading_max_words"]),
        heading_max_chars=int(structure["heading_max_chars"]),
        min_sequence_confidence=float(structure["min_sequence_confidence"]),
        heading_confidence=float(thresholds["heading_confidence"]),
        numbering_confidence=float(thresholds["numbering_confidence"]),
        layout_agreement_weight=float(structure["layout_agreement_weight"]),
        sequence_agreement_weight=float(structure["sequence_agreement_weight"]),
    )


def build_structure(
    paragraphs: list[Paragraph],
    config: StructureConfig | None = None,
    config_path: Path | str | None = None,
) -> ContractNode:
    settings = config or load_structure_config(config_path)
    root = _MutableNode("root", None, None, "document", 1.0, [], [], [], None)
    stack: list[_MutableNode] = [root]
    previous: _Label | None = None
    numbered = False
    for position, paragraph in enumerate(paragraphs):
        text = paragraph.text.strip()
        label = _parse_label(text)
        if label is not None and not _is_false_label(label, settings):
            scheme = _resolve_scheme(label, previous, paragraphs, position)
            parent, confidence, warning = _parent_for_label(stack, label, scheme)
            node = _MutableNode(
                _path_for(parent, label, scheme),
                label.raw,
                _heading_from_label(label),
                _kind(label.rest, settings),
                confidence,
                [warning] if warning else [],
                [paragraph.index],
                [],
                scheme,
            )
            parent.children.append(node)
            stack = stack[: stack.index(parent) + 1] + [node]
            previous = label
            numbered = True
            continue
        heading = _heading(text, paragraph, settings)
        if heading:
            node = _MutableNode(
                _next_heading_path(root),
                None,
                heading,
                _kind(text, settings),
                settings.heading_confidence,
                ["Unnumbered heading; hierarchy is low confidence."],
                [paragraph.index],
                [],
                None,
            )
            root.children.append(node)
            stack = [root, node]
        else:
            stack[-1].body_indexes.append(paragraph.index)
    if not numbered:
        root.warnings.append("No numbering scheme found; heading-and-paragraph segmentation used.")
        root.confidence = settings.heading_confidence
    elif root.body_indexes:
        root.warnings.append("Orphan text found outside the numbered structure.")
    return _freeze(root, paragraphs, settings, numbered)


def _parse_label(text: str) -> _Label | None:
    match = _LABEL_RE.match(text)
    if match is None:
        return None
    raw = match.group("label")
    if raw.isdigit() and not match.group("sep").strip().startswith("."):
        return None
    rest = match.group("rest").strip()
    if not rest:
        return None
    named = re.match(r"^(?P<word>[A-Za-z]+)\s+(?P<number>\d+)$", raw)
    if named:
        return _Label(raw, (int(named.group("number")),), (_SCHEME_WORDS[named.group("word").lower()],), rest)
    tokens = re.findall(r"\d+|[A-Za-zivxlcdmIVXLCDM]+", raw)
    values: list[int] = []
    schemes: list[str] = []
    for token in tokens:
        if token.isdigit():
            values.append(int(token))
            schemes.append("decimal")
        else:
            values.append(_alpha_or_roman_value(token))
            schemes.append("marker")
    return _Label(raw, tuple(values), tuple(schemes), rest)


def _alpha_or_roman_value(token: str) -> int:
    roman = _roman_value(token)
    return roman if roman is not None else ord(token.lower()) - 96


def _roman_value(token: str) -> int | None:
    if not token or any(char.lower() not in "ivxlcdm" for char in token):
        return None
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
    total = 0
    for index, char in enumerate(token.lower()):
        value = values[char]
        total += -value if index + 1 < len(token) and value < values[token[index + 1].lower()] else value
    return total


def _is_false_label(label: _Label, config: StructureConfig) -> bool:
    lowered = label.rest.casefold()
    return any(lowered.startswith(f"{keyword.casefold()} ") for keyword in config.false_label_starts)


def _resolve_scheme(
    label: _Label, previous: _Label | None, paragraphs: Sequence[Paragraph], position: int
) -> str:
    if label.schemes != ("marker",):
        return label.schemes[-1]
    token = label.raw.strip("()").strip(")")
    if previous and previous.schemes[-1] == "marker" and token.lower() in {"i", "ii", "iii", "iv"}:
        previous_token = previous.raw.strip("()").strip(")")
        if previous_token.lower() == "h" or ord(token.lower()[0]) == ord(previous_token.lower()[0]) + 1:
            return "alpha"
    following = _parse_label(paragraphs[position + 1].text.strip()) if position + 1 < len(paragraphs) else None
    if token.lower() in {"i", "ii", "iii", "iv", "v"} and following is not None:
        next_token = following.raw.strip("()").strip(")")
        if next_token.lower() in {"ii", "iii", "iv", "v", "vi"}:
            return "roman"
    return "alpha" if token.lower() in {"a", "b", "c", "d", "e", "f", "g", "h"} else "roman"


def _parent_for_label(
    stack: list[_MutableNode], label: _Label, scheme: str
) -> tuple[_MutableNode, float, str | None]:
    if len(stack) == 1:
        return stack[0], 1.0, None
    current = stack[-1]
    if current.scheme == scheme and current.label is not None:
        expected = _next_value(current.label, scheme)
        if _label_value(label, scheme) == expected:
            return stack[-2], 1.0, None
        if _label_value(label, scheme) > expected:
            return stack[-2], 0.6, "Numbering gap detected."
        if _label_value(label, scheme) < expected:
            return stack[-2], 0.6, "Numbering restart detected."
    for index in range(len(stack) - 2, -1, -1):
        ancestor = stack[index]
        if ancestor.children and ancestor.children[-1].scheme == scheme:
            expected = _next_value(ancestor.children[-1].label or "", scheme)
            if _label_value(label, scheme) == expected:
                return ancestor, 0.75, "Numbering level closed to an ancestor; sequence transition recorded."
    return current, 0.6, "Ambiguous numbering transition; attached as a deeper level."


def _next_value(label: str, scheme: str) -> int:
    token = re.findall(r"[A-Za-z0-9]+", label)[-1]
    if scheme == "decimal":
        return int(token) + 1
    return ord(token.lower()) - 96 + 1 if scheme == "alpha" else (_roman_value(token) or 0) + 1


def _label_value(label: _Label, scheme: str) -> int:
    token = re.findall(r"[A-Za-z0-9]+", label.raw)[-1]
    if scheme == "decimal":
        return int(token)
    if scheme == "alpha":
        return ord(token.lower()) - 96
    return _roman_value(token) or 0


def _path_for(parent: _MutableNode, label: _Label, scheme: str) -> str:
    if parent.path == "root":
        return label.raw
    return f"{parent.path}{label.raw}" if label.raw.startswith("(") else label.raw


def _heading_from_label(label: _Label) -> str | None:
    return label.rest.split(".", 1)[0].strip() if len(label.rest.split()) <= 12 else None


def _heading(text: str, paragraph: Paragraph, config: StructureConfig) -> str | None:
    if not text or len(text) > config.heading_max_chars or len(text.split()) > config.heading_max_words:
        return None
    if _RUN_IN_RE.match(text):
        return _RUN_IN_RE.match(text).group("head").strip()  # type: ignore[union-attr]
    if text.lower().startswith(("whereas", "recital", "signed by", "schedule ", "annexure ", "appendix ", "exhibit ")):
        return text.rstrip(".:")
    if (
        paragraph.is_heading_style
        or paragraph.bold_ratio >= config.heading_confidence
        or paragraph.caps_ratio >= config.heading_confidence
    ):
        return text.rstrip(".:")
    return None


def _kind(text: str, config: StructureConfig) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in config.classification_keywords.get("title", ())):
        return "title"
    if any(keyword in lowered for keyword in config.classification_keywords.get("signature", ())):
        return "signature_block"
    if any(keyword in lowered for keyword in config.heading_keywords.get("schedule", ())):
        return "schedule"
    if any(lowered.startswith(keyword) for keyword in config.classification_keywords.get("preamble", ())):
        return "preamble"
    if any(keyword in lowered for keyword in config.classification_keywords.get("definition", ())):
        return "definitions"
    if any(keyword in lowered for keyword in config.classification_keywords.get("parties", ())):
        return "parties"
    if any(keyword in lowered for keyword in config.classification_keywords.get("obligation", ())):
        return "operative_clause"
    return "boilerplate"


def _next_heading_path(root: _MutableNode) -> str:
    return f"heading-{len(root.children) + 1}"


def _freeze(
    node: _MutableNode, paragraphs: Sequence[Paragraph], config: StructureConfig, numbered: bool
) -> ContractNode:
    indexes = tuple(node.body_indexes)
    page_values = {paragraphs[index].page for index in indexes}
    pages = tuple(sorted(page for page in page_values if page is not None))
    children = tuple(_freeze(child, paragraphs, config, numbered) for child in node.children)
    kind = node.kind
    if kind == "boilerplate":
        kind = _kind(" ".join(paragraphs[index].text for index in indexes), config)
    confidence = node.confidence
    if not numbered and node.path == "root":
        confidence = config.heading_confidence
    return ContractNode(
        node.path, node.label, node.heading, indexes, children, kind, confidence,
        tuple(dict.fromkeys(node.warnings)), pages, kind == "operative_clause", node.scheme,
    )
