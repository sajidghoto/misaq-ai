"""Statute schema. Immutable. ``to_dict``/``from_dict`` define the on-disk JSON contract."""
from __future__ import annotations

from dataclasses import dataclass, field

from .enums import ActCode, BlockType, SectionStatus
from .ids import normalize_number, number_sort_key, section_id

SCHEMA_VERSION = "1.1"


@dataclass(frozen=True)
class Block:
    type: BlockType
    text: str

    def to_dict(self) -> dict:
        return {"type": self.type.value, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(BlockType(d["type"]), d["text"])


@dataclass(frozen=True)
class FootnoteRef:
    """A footnote marker printed in a section's text. Markers restart on every PDF page."""
    page: int
    marker: str

    def to_dict(self) -> dict:
        return {"page": self.page, "marker": self.marker}

    @classmethod
    def from_dict(cls, d: dict) -> "FootnoteRef":
        return cls(int(d["page"]), d["marker"])


@dataclass(frozen=True)
class Footnote:
    page: int           # PDF page the footnote was printed on (1-based)
    text: str
    marker: str = ""    # the number printed before the footnote, e.g. "1"

    def to_dict(self) -> dict:
        return {"page": self.page, "marker": self.marker, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict) -> "Footnote":
        return cls(int(d["page"]), d["text"], d.get("marker", ""))


@dataclass(frozen=True)
class Section:
    act: ActCode
    number: str                       # normalized: "5", "16A"
    title: str                        # title as printed in CONTENTS
    title_in_body: str                # title as printed at the section heading
    chapter: str | None
    subheading: str | None
    status: SectionStatus
    pages: tuple[int, ...]
    blocks: tuple[Block, ...]
    footnotes: tuple[Footnote, ...] = ()
    flags: tuple[str, ...] = ()       # e.g. "not_in_contents"
    footnote_refs: tuple[FootnoteRef, ...] = ()

    def __post_init__(self) -> None:
        if normalize_number(self.number) != self.number:
            raise ValueError(f"section number not normalized: {self.number!r}")
        if not self.pages:
            raise ValueError("a section must have at least one page")

    @property
    def id(self) -> str:
        return section_id(self.act.value, self.number)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "act": self.act.value, "number": self.number,
            "title": self.title, "title_in_body": self.title_in_body,
            "chapter": self.chapter, "subheading": self.subheading,
            "status": self.status.value, "pages": list(self.pages),
            "blocks": [b.to_dict() for b in self.blocks],
            "footnotes": [f.to_dict() for f in self.footnotes],
            "flags": list(self.flags),
            "footnote_refs": [r.to_dict() for r in self.footnote_refs],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Section":
        s = cls(
            act=ActCode(d["act"]), number=d["number"], title=d["title"],
            title_in_body=d["title_in_body"], chapter=d.get("chapter"),
            subheading=d.get("subheading"), status=SectionStatus(d["status"]),
            pages=tuple(d["pages"]), blocks=tuple(Block.from_dict(b) for b in d["blocks"]),
            footnotes=tuple(Footnote.from_dict(f) for f in d.get("footnotes", [])),
            flags=tuple(d.get("flags", [])),
            footnote_refs=tuple(FootnoteRef.from_dict(r) for r in d.get("footnote_refs", [])),
        )
        if d.get("id") not in (None, s.id):
            raise ValueError(f"id {d.get('id')!r} does not match {s.id!r}")
        return s


@dataclass(frozen=True)
class OmittedRange:
    """A run of section numbers the Act prints as omitted/repealed (e.g. SRA 45-51)."""
    first: int
    last: int

    def contains(self, number: str) -> bool:
        return self.first <= number_sort_key(number)[0] <= self.last


@dataclass(frozen=True)
class Act:
    code: ActCode
    source_file: str
    source_sha256: str
    sections: tuple[Section, ...]
    omitted_ranges: tuple[OmittedRange, ...] = ()
    notes: tuple[Footnote, ...] = ()      # footnotes no section cites: Act-level or on omitted material
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        ids = [s.id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate section ids in Act")

    def get(self, number: str) -> Section | None:
        want = normalize_number(number)
        return next((s for s in self.sections if s.number == want), None)

    def is_omitted(self, number: str) -> bool:
        return any(r.contains(number) for r in self.omitted_ranges)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version, "code": self.code.value,
            "source_file": self.source_file, "source_sha256": self.source_sha256,
            "omitted_ranges": [[r.first, r.last] for r in self.omitted_ranges],
            "notes": [n.to_dict() for n in self.notes],
            "sections": [s.to_dict() for s in self.sections],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Act":
        return cls(
            code=ActCode(d["code"]), source_file=d["source_file"],
            source_sha256=d["source_sha256"],
            sections=tuple(Section.from_dict(s) for s in d["sections"]),
            omitted_ranges=tuple(OmittedRange(a, b) for a, b in d.get("omitted_ranges", [])),
            notes=tuple(Footnote.from_dict(n) for n in d.get("notes", [])),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
        )


@dataclass(frozen=True)
class ReviewItem:
    page: int
    line: str
    reason: str


@dataclass(frozen=True)
class ParseReport:
    act: ActCode
    toc_entries: int
    parsed_sections: int
    failures: tuple[str, ...] = ()
    title_mismatches: tuple[tuple[str, ...], ...] = ()
    empty_sections: tuple[str, ...] = ()
    sequence_gaps_unexplained: tuple[tuple[int, int], ...] = ()
    accepted_not_in_contents: tuple[str, ...] = ()
    hyphen_linebreaks: int = 0
    review_items: tuple[ReviewItem, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.failures and not self.sequence_gaps_unexplained

    def to_dict(self) -> dict:
        return {
            "act": self.act.value, "ok": self.ok, "toc_entries": self.toc_entries,
            "parsed_sections": self.parsed_sections, "failures": list(self.failures),
            "title_mismatches": [list(m) for m in self.title_mismatches],
            "empty_sections": list(self.empty_sections),
            "sequence_gaps_unexplained": [list(g) for g in self.sequence_gaps_unexplained],
            "accepted_not_in_contents": list(self.accepted_not_in_contents),
            "hyphen_linebreaks": self.hyphen_linebreaks,
            "review_items": [vars(r) for r in self.review_items],
        }
