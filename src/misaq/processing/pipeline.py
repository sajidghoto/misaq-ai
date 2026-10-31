"""Stage 3: parsed Acts -> processed Acts (status, footnotes, hyphens). Pure, no I/O."""
from __future__ import annotations

import collections
from dataclasses import dataclass

from misaq.domain.enums import ActCode
from misaq.domain.statute import Act

from .dehyphenate import HyphenDecision, build_corpus, dehyphenate_act
from .footnotes import FootnoteReport, attach_footnotes
from .status import classify_act


@dataclass(frozen=True)
class ProcessReport:
    act: ActCode
    status_counts: dict[str, int]
    footnotes: FootnoteReport
    hyphen_decisions: tuple[HyphenDecision, ...]

    def to_dict(self) -> dict:
        c = collections.Counter(d.action for d in self.hyphen_decisions)
        return {"act": self.act.value, "status_counts": self.status_counts,
                "footnotes": self.footnotes.to_dict(),
                "hyphens": {"counts": dict(c), "decisions": [d.to_dict() for d in self.hyphen_decisions]}}


def process_acts(acts: dict[ActCode, Act]) -> dict[ActCode, tuple[Act, ProcessReport]]:
    classified = {code: classify_act(a) for code, a in acts.items()}
    corpus = build_corpus(list(classified.values()))
    out = {}
    for code, act in classified.items():
        status_counts = dict(collections.Counter(s.status.value for s in act.sections))
        act, fn_report = attach_footnotes(act)
        act, hyphens = dehyphenate_act(act, corpus)
        out[code] = (act, ProcessReport(code, status_counts, fn_report, hyphens))
    return out
