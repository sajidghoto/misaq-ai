"""Extract section-only citations from text or structured citation fields."""
from __future__ import annotations

import re
from dataclasses import replace

from misaq.domain.citation import Citation

_CITATION = re.compile(
    r"\b(?P<marker>s\.?|ss\.?|secs?\.?|sections?)\s*"
    r"(?P<refs>\d+[A-Za-z]?(?:\s*(?:-|–|and|,|&)\s*\d+[A-Za-z]?)*"
    r"(?:\s*\(\s*[^)]*\))?)"
    r"(?P<of>\s+of\s+(?P<act>[^,.;\n]+(?:,\s*\d{4})?))?",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?P<number>\d+[A-Za-z]?)(?:\s*\((?P<subsection>[^)]*)\))?")


def _parts(value: str, cap: int) -> list[tuple[str, str | None]] | None:
    tokens = re.findall(r"\d+[A-Za-z]?(?:\s*\([^)]*\))?", value)
    if not tokens:
        return None
    if "-" in value or "–" in value:
        bounds = [_NUMBER.fullmatch(token.strip()) for token in tokens]
        if len(bounds) != 2 or bounds[0] is None or bounds[1] is None:
            return None
        first_match = re.match(r"\d+", bounds[0].group("number"))
        last_match = re.match(r"\d+", bounds[1].group("number"))
        if first_match is None or last_match is None:
            return None
        first, last = int(first_match.group()), int(last_match.group())
        if last < first or last - first + 1 > cap:
            return [("__RANGE_OVER_CAP__", None)]
        return [(str(number), None) for number in range(first, last + 1)]
    result: list[tuple[str, str | None]] = []
    for token in tokens:
        match = _NUMBER.fullmatch(token.strip())
        if match is None:
            return None
        result.append((match.group("number"), match.group("subsection")))
    return result


def extract_citations(value: str | Citation, range_cap: int = 50) -> tuple[Citation, ...]:
    """Extract only section references; non-section legal references are ignored."""
    if range_cap <= 0:
        raise ValueError("range_cap must be positive")
    if isinstance(value, Citation):
        parts = _parts(value.section or "", range_cap)
        if parts is None:
            return (replace(value, reason_code="SECTION_INVALID"),)
        return tuple(replace(value, section=section, subsection=subsection,
                             reason_code="RANGE_OVER_CAP" if section == "__RANGE_OVER_CAP__" else None)
                     for section, subsection in parts)
    citations: list[Citation] = []
    for item_id, match in enumerate(_CITATION.finditer(value), 1):
        parts = _parts(match.group("refs"), range_cap)
        if parts is None:
            continue
        for offset, (section, subsection) in enumerate(parts, 1):
            citations.append(Citation(
                f"citation-{item_id}-{offset}", match.group(0), match.group("act"),
                section, subsection, "S1", (),
                "RANGE_OVER_CAP" if section == "__RANGE_OVER_CAP__" else None))
    return tuple(citations)
