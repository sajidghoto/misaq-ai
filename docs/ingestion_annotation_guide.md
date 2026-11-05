# Ingestion annotation guide

Create one JSONL row for every paragraph in reader order. Label every row:

* `role`: `heading`, `body`, `list`, `table`, `signature`, `preamble`, or another precise
  description when needed.
* `level`: the observed clause depth, using `0` for document-level text.
* `is_clause_start`: `true` only when the paragraph begins an analysis clause.

Record the contract manifest separately with its contract ID, agreement type, source URL, licence,
file hash, split, and reader fingerprint. A second annotator reviews a documented subset and
disagreements are adjudicated. Tune thresholds only on `dev`; keep `test` untouched until the
final guarded run. The sample is small, so report contract-level bootstrap confidence intervals.
