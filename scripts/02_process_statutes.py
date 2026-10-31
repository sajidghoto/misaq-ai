"""Stage 2: parsed Acts -> processed Acts (status, footnotes, hyphens). Writes the frozen data/processed/statutes."""
import hashlib
import json
import sys
from pathlib import Path

from misaq.domain.enums import ActCode
from misaq.domain.errors import DataValidationError, MisaqError
from misaq.domain.statute import Act
from misaq.processing.pipeline import process_acts
from misaq.validation.processed import require_processed_ok

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/interim/02_parsed"
OUT = ROOT / "data/processed/statutes"            # frozen, committed
REPORTS = ROOT / "data/interim/03_processed"


def main() -> int:
    try:
        acts = {}
        for code in ActCode:
            p = SRC / f"{code}.json"
            if not p.exists():
                raise DataValidationError(f"missing {p}: run scripts/01_parse_statutes.py first")
            acts[code] = Act.from_dict(json.loads(p.read_text(encoding="utf-8")))
        results = process_acts(acts)
        for act, rep in results.values():
            require_processed_ok(act, rep.footnotes.unresolved)          # raises before anything is written
        OUT.mkdir(parents=True, exist_ok=True)
        REPORTS.mkdir(parents=True, exist_ok=True)
        for stale in OUT.glob("*"):
            stale.unlink()
        sums = []
        for code, (act, rep) in results.items():
            body = json.dumps(act.to_dict(), indent=1, ensure_ascii=False)
            body_bytes = body.encode("utf-8")
            (OUT / f"{code}.json").write_bytes(body_bytes)
            sums.append(f"{hashlib.sha256(body_bytes).hexdigest()}  {code}.json")
            report = json.dumps(rep.to_dict(), indent=1, ensure_ascii=False)
            (REPORTS / f"{code}.process_report.json").write_text(report,encoding="utf-8")
            (OUT / f"{code}.parse_report.json").write_text((SRC / f"{code}.report.json").read_text(encoding="utf-8"))
            print(f"{code}: {len(act.sections)} sections, {len(act.notes)} act notes, "
                  f"{rep.footnotes.attached} footnotes attached, "
                  f"{sum(d.action == 'join' for d in rep.hyphen_decisions)} hyphens joined")
        (OUT / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    except MisaqError as e:
        print(f"FAILED: {e}\n  " + "\n  ".join(getattr(e, "failures", [])), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
