from __future__ import annotations

import collections
import re
from statistics import median
from typing import Any

import fitz

from misaq.contracts import Paragraph
from misaq.domain.errors import (
    CorruptFileError,
    EmptyDocumentError,
    EncryptedDocumentError,
    ScannedDocumentError,
)

_PAGE_RE = re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.I)


def read_pdf(data: bytes) -> tuple[list[Paragraph], list[str]]:
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except (RuntimeError, ValueError, TypeError) as error:
        raise CorruptFileError("The document could not be read because it is corrupt.") from error
    if document.is_encrypted:
        raise EncryptedDocumentError("The document is encrypted or password-protected.")
    raw_pages = [_page_lines(page) for page in document]
    all_text = [line["text"] for page in raw_pages for line in page]
    if not all_text:
        if any(page.get_images(full=True) for page in document):
            raise ScannedDocumentError("Scanned or image-only documents are not supported.")
        raise EmptyDocumentError("The document is empty or contains no selectable text.")
    if any(page.get_images(full=True) and len(" ".join(line["text"] for line in lines)) < 20
           for page, lines in zip(document, raw_pages, strict=False)):
        raise ScannedDocumentError("Scanned or image-only documents are not supported.")
    repeated = _repeated_margin_text(raw_pages)
    result: list[Paragraph] = []
    warnings_out: list[str] = []
    for page_number, lines in enumerate(raw_pages, 1):
        lines = [line for line in lines if _normal_key(line["text"]) not in repeated]
        lines = _order_columns(lines)
        for group in _paragraph_groups(lines):
            text = _join_lines([line["text"] for line in group])
            if not text:
                continue
            result.append(Paragraph(
                len(result), text, page_number, median(line["size"] for line in group),
                _bold_ratio(group), _caps_ratio(text), group[0]["x0"], None, "",
                any(line["in_table"] for line in group), _looks_heading(group, text),
            ))
        if hasattr(document[page_number - 1], "find_tables"):
            try:
                document[page_number - 1].find_tables()
            except (RuntimeError, ValueError):
                warnings_out.append("PDF table detection failed; table text was flattened.")
        else:
            warnings_out.append("PDF table detection is unavailable; table text was flattened.")
    return result, list(dict.fromkeys(warnings_out))


def _page_lines(page: Any) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    table_boxes: list[tuple[float, float, float, float]] = []
    if hasattr(page, "find_tables"):
        try:
            found = page.find_tables()
            table_boxes = [tuple(table.bbox) for table in found.tables]
        except (RuntimeError, ValueError):
            table_boxes = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = [span for span in line.get("spans", []) if span.get("text", "").strip()]
            if not spans:
                continue
            text = "".join(span["text"] for span in spans).strip()
            bbox = line["bbox"]
            lines.append({
                "text": text, "x0": bbox[0], "y0": bbox[1], "y1": bbox[3],
                "size": max(float(span["size"]) for span in spans),
                "bold": sum(len(span["text"]) for span in spans if span["flags"] & 16),
                "chars": sum(len(span["text"]) for span in spans),
                "in_table": any(_intersects(bbox, box) for box in table_boxes),
            })
    return lines


def _intersects(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def _normal_key(text: str) -> str:
    return re.sub(r"\d+", "#", " ".join(text.lower().split()))


def _repeated_margin_text(pages: list[list[dict[str, Any]]]) -> set[str]:
    candidates: list[str] = []
    for lines in pages:
        if lines:
            candidates.extend(_normal_key(line["text"]) for line in lines if line["y0"] < 72 or line["y1"] > 720)
    counts = collections.Counter(candidates)
    return {key for key, count in counts.items() if count > 1 or _PAGE_RE.match(key)}


def _order_columns(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(lines) < 2:
        return lines
    xs = sorted(line["x0"] for line in lines)
    gaps = [(b - a, i) for i, (a, b) in enumerate(zip(xs, xs[1:], strict=False))]
    if not gaps:
        return lines
    gap, index = max(gaps)
    if gap < 120:
        return sorted(lines, key=lambda line: (line["y0"], line["x0"]))
    split = (xs[index] + xs[index + 1]) / 2
    left = sorted((line for line in lines if line["x0"] < split), key=lambda line: line["y0"])
    right = sorted((line for line in lines if line["x0"] >= split), key=lambda line: line["y0"])
    return left + right


def _paragraph_groups(lines: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for line in lines:
        if not groups:
            groups.append([line])
            continue
        previous = groups[-1][-1]
        gap = line["y0"] - previous["y1"]
        if gap <= max(12.0, previous["size"] * 1.5) and abs(line["x0"] - groups[-1][0]["x0"]) <= 18:
            groups[-1].append(line)
        else:
            groups.append([line])
    return groups


def _join_lines(lines: list[str]) -> str:
    result = lines[0]
    for line in lines[1:]:
        if result.endswith("-") and line[:1].islower():
            result = result[:-1] + line
        else:
            result += " " + line
    return result


def _bold_ratio(lines: list[dict[str, Any]]) -> float:
    chars = sum(line["chars"] for line in lines)
    return sum(line["bold"] for line in lines) / chars if chars else 0.0


def _caps_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    return sum(char.isupper() for char in letters) / len(letters) if letters else 0.0


def _looks_heading(lines: list[dict[str, Any]], text: str) -> bool:
    return _bold_ratio(lines) >= 0.5 or _caps_ratio(text) >= 0.75
