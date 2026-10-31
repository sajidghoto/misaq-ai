"""Stage 3b: attach each footnote only to the section(s) that cite its marker.

Parsing gives every section all footnotes printed on its pages (marker + full text) and the
list of markers the section itself prints. Markers restart on every PDF page, so a footnote
belongs to a section when (page, marker) is in that section's footnote_refs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from misaq.domain.statute import Act, Footnote


@dataclass(frozen=True)
class FootnoteReport:
    attached: int                                        # footnote attachments made (a note cited twice counts twice)
    sections_with_notes: int
    orphans: tuple[Footnote, ...]                        # printed, no section cites it: stored as Act.notes
    unresolved: tuple[tuple[str, int, str], ...]         # (section_id, page, marker) cited, never printed

    def to_dict(self) -> dict:
        return {"attached": self.attached, "sections_with_notes": self.sections_with_notes,
                "orphans": [o.to_dict() for o in self.orphans],
                "unresolved": [list(u) for u in self.unresolved]}


def attach_footnotes(act: Act) -> tuple[Act, FootnoteReport]:
    pool: dict[tuple[int, str, str], Footnote] = {}
    for s in act.sections:
        for fn in s.footnotes:
            pool.setdefault((fn.page, fn.marker, fn.text), fn)
    by_ref: dict[tuple[int, str], list[Footnote]] = {}
    for fn in pool.values():
        by_ref.setdefault((fn.page, fn.marker), []).append(fn)

    claimed: set[tuple[int, str]] = set()
    unresolved: list[tuple[str, int, str]] = []
    new_sections = []
    attached = 0
    for s in act.sections:
        notes: list[Footnote] = []
        for ref in dict.fromkeys(s.footnote_refs):          # a marker cited twice attaches once
            key = (ref.page, ref.marker)
            if key in by_ref:
                claimed.add(key)
                notes.extend(by_ref[key])
            else:
                unresolved.append((s.id, ref.page, ref.marker))
        attached += len(notes)
        new_sections.append(replace(s, footnotes=tuple(notes)))
    orphans = tuple(fn for key, fns in by_ref.items() if key not in claimed for fn in fns)
    report = FootnoteReport(attached, sum(1 for s in new_sections if s.footnotes), orphans, tuple(unresolved))
    return replace(act, sections=tuple(new_sections), notes=orphans), report
