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
