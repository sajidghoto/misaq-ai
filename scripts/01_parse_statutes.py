"""Stage 1: parse the three statute PDFs, validate structure, write data/interim/02_parsed."""
import json
import sys
from pathlib import Path

from misaq.domain.enums import ActCode
from misaq.domain.errors import MisaqError
from misaq.parsing.pipeline import parse_act
from misaq.validation.statutes import check_source_hashes, require_ok

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data/raw/statutes", ROOT / "data/interim/02_parsed"
FILES = {ActCode.CA1872: "PK-CA1872_source.pdf", ActCode.SGA1930: "PK-SGA1930_service.pdf",
         ActCode.SRA1877: "PK-SRA1877_Source.pdf"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        check_source_hashes(RAW)
        for code, name in FILES.items():
            act, report = parse_act(RAW / name, code)
            (OUT / f"{code}.report.json").write_text(
                json.dumps(report.to_dict(), indent=1, ensure_ascii=False),
                encoding="utf-8"
            )
            require_ok(report)
            (OUT / f"{code}.json").write_text(
                json.dumps(act.to_dict(), indent=1, ensure_ascii=False),
                encoding="utf-8"
            )
            print(f"{code}: {report.parsed_sections}/{report.toc_entries} sections, ok")
    except MisaqError as e:
        print(f"FAILED: {e}\n  " + "\n  ".join(getattr(e, "failures", [])), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
