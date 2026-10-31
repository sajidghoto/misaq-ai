"""Data-quality gate for processed statutes. Fails loudly (DataValidationError)."""
from __future__ import annotations

import re

from misaq.domain.enums import SectionStatus
from misaq.domain.errors import DataValidationError
from misaq.domain.statute import Act
from misaq.parsing.pdf_lines import DATE_STAMP_RE, OMISSION_RE

_BROKEN_HYPHEN = re.compile(r"[A-Za-z]-\n[a-z]")
_RULE_LINE = re.compile(r"^_{3,}$")


def validate_processed(act: Act, unresolved: tuple = ()) -> list[str]:
    """Returns the list of failures (empty = pass)."""
    fails: list[str] = []
    for s in act.sections:
        if s.status is SectionStatus.IN_FORCE and not s.blocks:
            fails.append(f"{s.id}: in-force section has no text")
        for b in s.blocks:
            for line in b.text.split("\n"):
                ln = line.strip()
                if OMISSION_RE.match(ln) or DATE_STAMP_RE.match(ln) or _RULE_LINE.match(ln):
                    fails.append(f"{s.id}: artefact line in text: {ln!r}")
            if _BROKEN_HYPHEN.search(b.text):
                fails.append(f"{s.id}: line-end hyphen left in text")
            if re.search(r"^(CHAPTER|PART)\s+[IVXL]+\b", b.text, re.M):
                fails.append(f"{s.id}: chapter/part heading inside section text")
    fails += [f"unresolved footnote marker {u}" for u in unresolved]
    return fails


def require_processed_ok(act: Act, unresolved: tuple = ()) -> None:
    fails = validate_processed(act, unresolved)
    if fails:
        raise DataValidationError(f"{act.code.value}: processed-data validation failed", failures=fails)
