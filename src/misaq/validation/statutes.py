"""Data-quality gate for parsed statutes. Fails loudly (DataValidationError)."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from misaq.domain.enums import ActCode
from misaq.domain.errors import DataValidationError
from misaq.domain.ids import number_sort_key
from misaq.domain.statute import ParseReport, ReviewItem


def _norm(x: str) -> str:
    return re.sub(r"[^a-z0-9]", "", x.lower())


def build_report(act, toc, raw_sections, leftover, omitted, review, empty_ok_markers=("epealed",)) -> ParseReport:
    failures: list[str] = []
    tn = [e["number"] for e in toc]
    if len(set(tn)) != len(tn):
        failures.append("duplicate numbers in contents")
    pn = [s["number"] for s in raw_sections]
    if len(set(pn)) != len(pn):
        failures.append("duplicate sections in body")
    if leftover:
        failures.append(f"contents entries never found in body: {leftover}")

    main = [x for x in raw_sections if not x.get("flag")]
    mism: list[tuple[str, ...]] = []
    for e, s in zip(toc, main, strict=False):
        if e["number"] != s["number"]:
            mism.append((e["number"], s["number"]))
            continue
        a, b = _norm(e["title"]), _norm(s["title_body"])
        if a != b and not (a in b or b in a):
            mism.append((e["number"], e["title"][:40], s["title_body"][:40]))

    empty = [s["number"] for s in raw_sections
             if not s["blocks"] and not any(k in s["title_body"] for k in empty_ok_markers)]
    nums = [number_sort_key(n)[0] for n in pn]
    gaps = tuple((a, b) for a, b in zip(nums, nums[1:], strict=False)
                 if b - a > 1 and not any(o[0] <= a + 1 and b - 1 <= o[1] for o in omitted))
    hyph = sum(b["text"].count("-\n") for s in raw_sections for b in s["blocks"])
    return ParseReport(
        act=act, toc_entries=len(toc), parsed_sections=len(raw_sections),
        failures=tuple(failures), title_mismatches=tuple(mism), empty_sections=tuple(empty),
        sequence_gaps_unexplained=gaps,
        accepted_not_in_contents=tuple(s["number"] for s in raw_sections if s.get("flag")),
        hyphen_linebreaks=hyph,
        review_items=tuple(ReviewItem(**r) for r in review))


def require_ok(report: ParseReport) -> None:
    if not report.ok:
        raise DataValidationError(
            f"{report.act.value}: parse validation failed",
            failures=list(report.failures) + [f"unexplained gap {g}" for g in report.sequence_gaps_unexplained])


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_source_hashes(raw_dir: Path) -> None:
    """Every PDF must match data/raw/statutes/SHA256SUMS."""
    sums = raw_dir / "SHA256SUMS"
    if not sums.exists():
        raise DataValidationError(f"missing {sums}")
    bad = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        p = raw_dir / name.strip().lstrip("*")
        if not p.exists() or sha256_file(p) != digest:
            bad.append(name)
    if bad:
        raise DataValidationError("source PDF hash mismatch", failures=bad)


def check_processed_hashes(processed_dir: Path) -> None:
    """Verify raw-byte SHA-256 digests for every processed statute."""
    sums = processed_dir / "SHA256SUMS"
    if not sums.exists():
        raise DataValidationError(f"missing {sums}")

    expected_names = {f"{code.value}.json" for code in ActCode}
    entries: dict[str, str] = {}
    malformed: list[str] = []
    for line_number, line in enumerate(sums.read_text(encoding="utf-8").splitlines(), 1):
        digest, separator, name = line.partition("  ")
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest) or not name:
            malformed.append(f"line {line_number}: expected '<sha256>  <statute>.json'")
            continue
        if name not in expected_names:
            malformed.append(f"line {line_number}: unexpected statute entry {name!r}")
            continue
        if name in entries:
            malformed.append(f"line {line_number}: duplicate statute entry {name!r}")
            continue
        entries[name] = digest

    if malformed:
        raise DataValidationError("invalid processed statute checksum manifest", failures=malformed)

    missing_entries = sorted(expected_names - entries.keys())
    if missing_entries:
        raise DataValidationError(
            "incomplete processed statute checksum manifest",
            failures=[f"missing manifest entry: {name}" for name in missing_entries],
        )

    bad = []
    for name, digest in entries.items():
        p = processed_dir / name
        if not p.exists() or sha256_file(p) != digest:
            bad.append(name)
    if bad:
        raise DataValidationError(
            "processed statute hash mismatch (verify LF line endings and corpus provenance)",
            failures=bad,
        )
