"""Stage 3a: classify each section as in_force / repealed / omitted from what the PDF prints."""
from __future__ import annotations

import re
from dataclasses import replace

from misaq.domain.enums import SectionStatus
from misaq.domain.statute import Act, Section

_REPEALED_TITLE = re.compile(r"^\W*(Repealed|Omitted)\W*$", re.I)
_REPEALED_TEXT = re.compile(r"^\W*(\[?Repeal[^\]]*\]?\s*)?(Rep\.|Repealed|Omitted)\b", re.I)


def classify(section: Section, act: Act) -> SectionStatus:
    m = _REPEALED_TITLE.match(section.title.strip())
    if m:
        return SectionStatus.OMITTED if m.group(1).lower() == "omitted" else SectionStatus.REPEALED
    first = section.blocks[0].text.strip() if section.blocks else ""
    if _REPEALED_TEXT.match(first) and len(section.text) < 200:
        return SectionStatus.OMITTED if re.search(r"\bOmitted\b", first, re.I) else SectionStatus.REPEALED
    if act.is_omitted(section.number):
        return SectionStatus.OMITTED
    return SectionStatus.IN_FORCE


def classify_act(act: Act) -> Act:
    return replace(act, sections=tuple(replace(s, status=classify(s, act)) for s in act.sections))
