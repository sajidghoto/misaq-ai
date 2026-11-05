# Project state

- Steps 1–4: implemented and validated in the repository.
- Step 5: verification registry and reproducibility controls are implemented; approved corpus remains frozen.
- Step 6: dense retrieval and Experiment B scaffolding exist; evaluation data does not exist yet.
- Step 7: Experiment C scaffolding and dry-run path exist; owner-run cloud validation remains pending.
- Scope: dense-FAISS-only retrieval, as defined by the proposal; no sparse or hybrid path.
- `selection.recall_at_5_tolerance`: null.
- `selection.max_peak_ram_bytes`: null.
- M1 is not built.
- M5 scoring tools are not built.
- M6 interface is not built.
- `experimental_protocol.md` is not built.
- No evaluation JSONL exists under `data/eval/` yet.

## Session log
2026-11-03
Housekeeping completed for deterministic verification, index selection, registry mapping, and retrieval demo.
Protected data was not modified; validation commands were run after the changes.

2026-11-05
M1 ingestion design and schema compatibility review completed; no ingestion code written.
Protected contract, processed-data, evaluation, and run artifacts were not modified.

2026-11-05
M1 Step B readers, normalization, synthetic tests, and limits documentation implemented.
Full pytest and ruff passed; full mypy retains 22 pre-existing cloud backend errors.

2026-11-05
M1 Step C structure detection, sequence-aware clause trees, synthetic/property tests, and docs implemented.
Full pytest and ruff passed; full mypy retains 22 pre-existing cloud backend errors.

2026-11-05
M1 Step C final verification completed: Ruff passed and pytest reported 206 passed.
Full mypy retains the same 22 cloud-backend typing errors; google-genai is installed.

2026-11-05
M1 Step C completion tests added for labels, classifications, warnings, fallbacks, and coverage order.
Full Ruff passed; pytest reported 211 passed; full mypy retains 22 pre-existing cloud-backend errors.

2026-11-05
Cloud backend generation config now uses explicit google-genai constructor keywords for mypy-safe typing.
Targeted mypy, Ruff, and generation tests passed; full mypy is blocked by a pre-existing syntax error in ingestion/units.py.

2026-11-05
M1 Step D ingestion units, memory-only public API, thin CLIs, evaluation metrics/validator, and synthetic tests implemented.
Protected data and evaluation labels were not modified; full validation remains pending.

2026-11-05
Experiment B readiness review found the configured eval path and model CLI are incomplete.
The supplied 29-row CSV is dev-only and requires approved JSONL conversion plus a separate test split.

2026-11-05
Extended the index-builder model CLI to accept all four configured embedding models.
The default remains bge-small-en-v1.5; protected data and artifacts were not modified.

2026-11-05
Index build review found seven completed model/chunking combinations and one expected MiniLM section-aware failure.
MiniLM's 256-token limit conflicts with the shared 400-token section-aware chunk budget; no settings were changed.

2026-11-05
Experiment B protocol documentation was added for model support, index-build evidence, dev runs, and selection.
Metric and final-selection fields remain pending until the development summaries are reviewed.

2026-11-05
Fixed the Experiment B test hash guard to compare the stored digest with DataFingerprint.sha256.
Focused Experiment B tests passed (7) and Ruff passed; final test rerun remains pending after commit.

2026-11-05
Experiment B dev summaries were documented; the pre-written rule selects bge-large section-aware at Recall@5 0.7414.
The completed bge-base section-aware test run is documented separately and is not the selected-model final result.

2026-11-05
Experiment B selected-model final test completed for bge-large section-aware: 29/29 items, zero errors, zero missing.
Final Recall@5 was 0.6552 with 95% bootstrap CI 0.4828–0.8276; results were documented without retuning.
