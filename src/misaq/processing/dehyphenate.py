"""Stage 3c: repair words split by a hyphen at the end of a printed line.

"res-\\npectively" must become "respectively", but "non-\\nperformance" must stay hyphenated.
The decision uses the statutes themselves as evidence: how often does the joined form and the
hyphenated form appear elsewhere, unbroken? Conflicting or missing evidence is reported as
'ambiguous' and the hyphen is kept (the safe choice: it preserves what was printed).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from misaq.domain.statute import Act, Block, Section

_BREAK = re.compile(r"([A-Za-z]+)-\n([a-z][A-Za-z]*)")
_MASK = "\x00"


@dataclass(frozen=True)
class HyphenDecision:
    section_id: str
    left: str
    right: str
    action: str            # "join" | "keep" | "ambiguous"
    joined_count: int
    hyphenated_count: int

    def to_dict(self) -> dict:
        return dict(vars(self))


def build_corpus(acts: list[Act]) -> str:
    """All statute text, with broken hyphens masked so they never count as evidence."""
    parts = [b.text for a in acts for s in a.sections for b in s.blocks]
    return _BREAK.sub(lambda m: m.group(1) + _MASK + m.group(2), "\n".join(parts)).replace("\n", " ").lower()


def decide(left: str, right: str, corpus: str) -> tuple[str, int, int]:
    joined = len(re.findall(rf"\b{re.escape((left + right).lower())}\b", corpus))
    hyph = len(re.findall(rf"\b{re.escape(left.lower())}-{re.escape(right.lower())}\b", corpus))
    if joined > 0 and hyph == 0:
        return "join", joined, hyph
    if hyph > 0 and joined == 0:
        return "keep", joined, hyph
    return "ambiguous", joined, hyph


def dehyphenate_text(text: str, corpus: str, section_id: str = "") -> tuple[str, list[HyphenDecision]]:
    decisions: list[HyphenDecision] = []

    def repl(m: re.Match) -> str:
        left, right = m.group(1), m.group(2)
        action, j, h = decide(left, right, corpus)
        decisions.append(HyphenDecision(section_id, left, right, action, j, h))
        return left + right if action == "join" else f"{left}-{right}"

    return _BREAK.sub(repl, text), decisions


def dehyphenate_act(act: Act, corpus: str) -> tuple[Act, tuple[HyphenDecision, ...]]:
    all_decisions: list[HyphenDecision] = []
    sections = []
    for s in act.sections:
        blocks = []
        for b in s.blocks:
            text, d = dehyphenate_text(b.text, corpus, s.id)
            all_decisions.extend(d)
            blocks.append(Block(b.type, text))
        sections.append(replace(s, blocks=tuple(blocks)) if isinstance(s, Section) else s)
    return replace(act, sections=tuple(sections)), tuple(all_decisions)
