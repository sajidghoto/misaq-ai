"""Stage 1: PDF -> typed text lines. Knows fonts and positions, knows nothing about law."""
from __future__ import annotations

import collections
import re

from misaq.domain.errors import ParsingError

NUM = r"(\d+)\s*(?:\(\s*([A-Z])\s*\))?([A-Z])?"       # 27 (A) / 27A / 16A / 5
SEC_RE = re.compile(r"^\[?\s*" + NUM + r"\s*\.\s*(.*)$")
CHAP_RE = re.compile(r"^(CHAPTER|PART)\s+([IVXL]+)\b\s*(.*)$")
FOOTER_RE = re.compile(r"^Page\s+\d+\s+of\s+\d+$")
MARKER_RE = re.compile(r"\d{1,3}|\*{1,3}")                                # a real footnote marker
DOC_ID_RE = re.compile(r"^\d{5,}$")                                       # "6528929" document id stamp
DATE_STAMP_RE = re.compile(r"^Date:\s*\d{1,2}-\d{1,2}-\d{4}$")          # "Date: 12-02-2025" page stamp
OMISSION_RE = re.compile(r"^[\[\]*\s]+$")                                 # "[*", "*]", "* * * *"
WATERMARK = {"THE PAKISTAN CODE", "THE", "PAKISTAN", "CODE"}


def marker_of(text: str) -> str | None:
    """Footnote marker text, or None if the span is not a marker (e.g. a separator rule).
    The source PDFs print some markers as a superscript letter l / I instead of 1: read as '1'."""
    t = text.strip()
    if MARKER_RE.fullmatch(t):
        return t
    return "1" if t in ("l", "I") else None


def norm_num(m: re.Match) -> str:
    return m.group(1) + (m.group(2) or m.group(3) or "")


def page_lines(page) -> list[dict]:
    """Lines of one page: text, x0, x1, y0, size, bold, italic, spans, markers (footnote markers)."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip() != "" or s["text"]]
            if not spans:
                continue
            mx = max(s["size"] for s in spans)

            def is_marker(s, mx=mx):
                tx = s["text"].strip()
                return bool(s["flags"] & 1) or (
                    tx != "" and re.fullmatch(r"[\d*]{1,3}", tx) and s["size"] < mx - 2)

            keep = [s for s in spans if not is_marker(s)]
            sup = [s for s in spans if is_marker(s)]
            while keep and keep[0]["text"].strip() in ("[", ""):   # amendment bracket
                keep = keep[1:]
            text = re.sub(r"\s*_{3,}\s*$", "", "".join(s["text"] for s in keep).strip())   # chapter separator rule
            if not text:
                continue
            first = keep[0]
            out.append(dict(
                text=text, x0=line["bbox"][0], x1=line["bbox"][2], y0=line["bbox"][1], size=first["size"],
                bold=bool(first["flags"] & 16), italic=bool(first["flags"] & 2),
                spans=keep,
                markers=[m for m in (marker_of(s["text"]) for s in sup) if m]))
    out.sort(key=lambda r: (round(r["y0"]), r["x0"]))
    return out


def is_noise(r: dict) -> bool:
    t = r["text"]
    return (bool(FOOTER_RE.match(t)) or bool(DATE_STAMP_RE.match(t)) or t.upper() in WATERMARK
            or bool(DOC_ID_RE.match(t)) or bool(OMISSION_RE.match(t)) or re.fullmatch(r"_+|[\s_*]+", t) is not None)


def body_start_page(doc) -> int:
    for i, p in enumerate(doc):
        tx = p.get_text()
        if "hereby enacted" in tx or "Preamble" in tx:
            return i
    raise ParsingError("body start page not found (no 'hereby enacted' / 'Preamble')")


def body_text_size(lines: list[dict]) -> float:
    """Most common font size on a page = body text. Smaller lines are footnotes."""
    sizes = collections.Counter(round(r["size"], 1) for r in lines)
    return sizes.most_common(1)[0][0]
