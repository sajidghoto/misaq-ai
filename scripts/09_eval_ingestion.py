"""Validate and score ingestion annotations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from misaq.evaluation.ingestion_eval import evaluate_contract, load_gold
from misaq.experiments.fingerprint import git_info, sha256_file
from misaq.ingestion.readers import reader_fingerprint


def guard_test_split(root: Path, gold_path: Path, final: bool) -> None:
    if not final:
        raise RuntimeError("test split requires --final")
    if git_info(root)["dirty"] is not False:
        raise RuntimeError("test split requires a clean git tree")
    sums = root / "data" / "eval" / "SHA256SUMS"
    if not sums.exists():
        raise RuntimeError("test split gold file hash is not listed in data/eval/SHA256SUMS")
    listed = {
        line.split(maxsplit=1)[0]
        for line in sums.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if sha256_file(gold_path).sha256 not in listed:
        raise RuntimeError("test split gold file hash is not listed in data/eval/SHA256SUMS")
    _, manifest = load_gold(gold_path)
    if manifest.get("reader_fingerprint") != reader_fingerprint():
        raise RuntimeError("test split reader fingerprint does not match gold manifest")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predicted", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    rows, _ = load_gold(args.gold)
    if args.split == "test":
        guard_test_split(Path.cwd(), args.gold, args.final)
    if args.predicted:
        predicted = [
            json.loads(line)
            for line in args.predicted.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        print(json.dumps(evaluate_contract(predicted, rows), indent=2))
    else:
        print(json.dumps({"validated_rows": len(rows), "split": args.split}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
