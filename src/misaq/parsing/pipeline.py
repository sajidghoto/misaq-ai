"""Stage 2: PDF -> Act (status UNKNOWN) + ParseReport."""
from __future__ import annotations

from pathlib import Path

import pymupdf

from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.statute import Act, Block, Footnote, FootnoteRef, OmittedRange, ParseReport, Section
from misaq.validation.statutes import build_report, sha256_file

from .body import parse_body
from .contents import parse_contents
from .pdf_lines import body_start_page


def parse_act(pdf_path: Path, code: ActCode) -> tuple[Act, ParseReport]:
    doc = pymupdf.open(str(pdf_path))
    start = body_start_page(doc)
    toc, omitted = parse_contents(doc, start)
    raw, review, leftover = parse_body(doc, start, toc)
    report = build_report(code, toc, raw, leftover, omitted, review)

    toc_by_num = {e["number"]: e for e in toc}
    sections = []
    for s in raw:
        t = toc_by_num.get(s["number"])
        title = t["title"].strip() if t else s["title_body"].rstrip(".")
        sections.append(Section(
            act=code, number=s["number"], title=title, title_in_body=s["title_body"],
            chapter=s["chapter"], subheading=s["subheading"], status=SectionStatus.UNKNOWN,
            pages=tuple(s["pages"]),
            blocks=tuple(Block(BlockType(b["type"]), b["text"]) for b in s["blocks"]),
            footnotes=tuple(Footnote(f["page"], f["text"], f["marker"]) for f in s["footnotes"]),
            footnote_refs=tuple(FootnoteRef(p, m) for p, m in s["refs"]),
            flags=(s["flag"],) if s.get("flag") else ()))
    act = Act(code=code, source_file=pdf_path.name, source_sha256=sha256_file(pdf_path),
              sections=tuple(sections),
              omitted_ranges=tuple(OmittedRange(a, b) for a, b in omitted))
    return act, report
