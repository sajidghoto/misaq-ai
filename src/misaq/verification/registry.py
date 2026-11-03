"""Read-only registry of the frozen processed statute corpus."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from misaq.domain.enums import SectionStatus
from misaq.domain.statute import Act
from misaq.validation.statutes import check_processed_hashes


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


@dataclass(frozen=True)
class Alias:
    act: str
    name: str
    verified: bool


@dataclass(frozen=True)
class ActRecord:
    code: str
    in_force_sections: frozenset[str]
    repealed_sections: frozenset[str]
    omitted_ranges: tuple[tuple[int, int], ...]
    all_sections: frozenset[str]
    section_text: dict[str, str]


_SOURCE_PDFS = {
    "CA1872": "PK-CA1872_source.pdf",
    "SGA1930": "PK-SGA1930_service.pdf",
    "SRA1877": "PK-SRA1877_Source.pdf",
}


@dataclass(frozen=True)
class CorpusRegistry:
    acts: dict[str, ActRecord]
    aliases: dict[str, Alias]
    unverified_aliases: tuple[str, ...] = ()

    @classmethod
    def from_processed(
        cls, processed_dir: Path, config_path: Path, raw_dir: Path | None = None
    ) -> "CorpusRegistry":
        check_processed_hashes(processed_dir)
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        acts: dict[str, ActRecord] = {}
        for path in sorted(processed_dir.glob("*.json")):
            if "_report" in path.name:
                continue
            act = Act.from_dict(json.loads(path.read_text(encoding="utf-8")))
            acts[act.code.value] = _record(act)
        aliases: dict[str, Alias] = {}
        unverified: list[str] = []
        for entry in config.get("verification", {}).get("aliases", []):
            verified = bool(entry.get("verified", False))
            for name in entry.get("names", []):
                confirmed = verified and _alias_confirmed(str(entry["act"]), str(name), acts, raw_dir)
                alias = Alias(str(entry["act"]), str(name), confirmed)
                aliases[_key(alias.name)] = alias
                if not confirmed:
                    unverified.append(alias.name)
        return cls(acts, aliases, tuple(unverified))

    @classmethod
    def from_acts(cls, acts: Iterable[Act], aliases: Iterable[Alias] = ()) -> "CorpusRegistry":
        alias_map = {_key(alias.name): alias for alias in aliases}
        return cls({act.code.value: _record(act) for act in acts}, alias_map,
                   tuple(alias.name for alias in aliases if not alias.verified))

    def resolve_act(self, value: str) -> Alias | None:
        return self.aliases.get(_key(value))

    def find_section(self, section: str) -> tuple[str, ...]:
        return tuple(code for code, record in self.acts.items() if section in record.all_sections)


def _record(act: Act) -> ActRecord:
    in_force = {section.number for section in act.sections if section.status is SectionStatus.IN_FORCE}
    repealed = {section.number for section in act.sections if section.status is SectionStatus.REPEALED}
    all_sections = {section.number for section in act.sections}
    return ActRecord(act.code.value, frozenset(in_force), frozenset(repealed),
                     tuple((item.first, item.last) for item in act.omitted_ranges),
                     frozenset(all_sections), {section.number: section.text for section in act.sections})


def _alias_confirmed(act_code: str, alias: str, acts: dict[str, ActRecord], raw_dir: Path | None) -> bool:
    if act_code not in acts:
        return False
    if alias.casefold() == act_code.casefold():
        return True
    if raw_dir is None:
        return False
    source_name = _SOURCE_PDFS.get(act_code)
    if source_name is None or not (raw_dir / source_name).is_file():
        return False
    import fitz
    document = fitz.open(raw_dir / source_name)
    title = document[0].get_text("text")
    document.close()
    return _key(alias).replace("the", "", 1) in _key(title)
