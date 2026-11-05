from __future__ import annotations

import hashlib
import inspect
import re
import unicodedata

from misaq.contracts import Paragraph

READER_VERSION = "m1-step-b-1"
_CONFIG = "unicode-nfkc|quotes|bullets|ligatures|soft-hyphens|whitespace"


def _text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\u00ad", "")
    for source, replacement in {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2022": "-", "\u2043": "-", "\u2219": "-", "\uf0b7": "-",
    }.items():
        value = value.replace(source, replacement)
    value = re.sub(r"[ \t\r\n\f\v]+", " ", value)
    return value.strip()


def normalise(paragraphs: list[Paragraph]) -> list[Paragraph]:
    result: list[Paragraph] = []
    for paragraph in paragraphs:
        source = paragraph.source_indexes or (paragraph.index,)
        result.append(Paragraph(
            paragraph.index, _text(paragraph.text), paragraph.page, paragraph.font_size,
            paragraph.bold_ratio, paragraph.caps_ratio, paragraph.left_indent,
            paragraph.style_name, _text(paragraph.list_label_text), paragraph.in_table,
            paragraph.is_heading_style, source,
        ))
    return result


def reader_fingerprint() -> str:
    source = inspect.getsource(_text) + inspect.getsource(normalise) + READER_VERSION + _CONFIG
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
