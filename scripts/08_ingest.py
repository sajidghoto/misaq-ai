"""Ingest one public contract without writing document text by default."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from misaq.ingestion import ingest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--show-headings", action="store_true")
    parser.add_argument("--show-text", action="store_true")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()
    if (args.show_text or args.json_out) and not args.public:
        parser.error("--public is required for --show-text and --json-out")
    result = ingest_path(args.file)
    print(json.dumps({
        "paragraph_count": result.report.paragraph_count,
        "clause_count": result.report.clause_count,
        "headings": [clause.heading for clause in result.clauses if clause.heading],
        "warnings": list(result.report.warnings),
    }, ensure_ascii=False))
    if args.show_text:
        for clause in result.clauses:
            print(clause.text)
    if args.json_out:
        args.json_out.write_text(json.dumps([{
            "clause_id": c.clause_id, "text": c.text, "cloud_ok": c.cloud_ok,
            "heading": c.heading, "label": c.label, "path": c.path,
            "source_pages": list(c.source_pages), "kind": c.kind,
            "confidence": c.confidence, "warnings": list(c.warnings),
        } for c in result.clauses], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
