"""Export a draft ingestion annotation sheet; humans must correct every row."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reader-output", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.reader_output.read_text(encoding="utf-8"))
    with args.out.open("w", encoding="utf-8", newline="\n") as stream:
        for index, row in enumerate(rows):
            stream.write(json.dumps({
                "paragraph_index": index, "role": row.get("kind", "unknown"),
                "level": 0, "is_clause_start": False,
            }) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
