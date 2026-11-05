import csv
import json
from pathlib import Path

source = Path(r"C:\Users\HH Traders\Downloads\misaq-query-review-29.csv")
output = Path("data/eval/retrieval/dev.jsonl")

act_map = {
    "CA": "CA1872",
    "SGA": "SGA1930",
}

with source.open(encoding="utf-8-sig", newline="") as file:
    rows = list(csv.DictReader(file))

required_columns = {"id", "query", "gold"}
missing = required_columns - set(rows[0])
if missing:
    raise ValueError(f"Missing CSV columns: {sorted(missing)}")

with output.open("w", encoding="utf-8") as file:
    for row in rows:
        gold_ids = []

        for label in row["gold"].split(";"):
            label = label.strip()
            act, section = label.split()
            gold_ids.append(f"{act_map[act]}:s{section}")

        record = {
            "id": row["id"],
            "query": row["query"],
            "gold": gold_ids,
            "split": "dev",
        }

        file.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Wrote {len(rows)} rows to {output}")