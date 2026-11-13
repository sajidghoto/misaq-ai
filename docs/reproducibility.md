# Reproducibility Runbook
Run from the repository root in Windows PowerShell. Frozen statutes and configuration are
inputs; do not run parse/process scripts unless the protected data policy is changed.
## Environment setup
```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev,embed]"
```
Purpose: install the editable project and declared development/embedding dependencies.
Writes files: yes, the virtual environment. Deterministic: no, dependency ranges are not pinned.
## Processed-hash check
```powershell
.venv\Scripts\python.exe -c "from pathlib import Path; from misaq.validation.statutes import check_processed_hashes; check_processed_hashes(Path('data/processed/statutes')); print('processed statute hashes: OK')"
```
Purpose: verify every frozen processed statute against `SHA256SUMS` using the raw-byte
SHA-256 contract established by `scripts/02_process_statutes.py`. `.gitattributes` forces
LF checkouts for processed JSON and checksum-controlled evaluation JSONL on Windows,
Linux, and macOS; PDFs remain binary. No local `core.autocrlf` setting is required.
Attributes take effect on checkout and do not rewrite an existing worktree retroactively;
use a fresh clone to verify this policy without manually editing protected inputs.
Writes files: no. Deterministic: yes.

If validation fails, inspect the named files and confirm that processed JSON has LF
line endings. Do not rewrite `SHA256SUMS` to bypass a mismatch. A real content change
requires explicit approval and preserved corpus provenance before the corpus or manifest
is updated. The checker rejects malformed, duplicate, unexpected, or incomplete statute
manifest entries.
## Index builds
```powershell
.venv\Scripts\python.exe scripts\03_build_index.py --model bge-small-en-v1.5 --chunking section_aware
.venv\Scripts\python.exe scripts\03_build_index.py --model bge-small-en-v1.5 --chunking fixed_size
```
Purpose: build and self-validate both configured chunking indexes. Writes files: yes, under
`data/index`. Deterministic: index contents are deterministic for the frozen inputs/model;
timing and peak-memory fields in build reports are not.
## Validation
```powershell
.venv\Scripts\python.exe -m pytest -q tests/unit/test_validate_processed.py tests/unit/test_validate_statutes.py tests/unit/test_validation_chunks.py tests/unit/test_index.py
```
Purpose: run focused statute, chunk, and index validation tests. Writes files: pytest cache.
Deterministic: yes for test results.
## Tests
```powershell
.venv\Scripts\python.exe -m pytest -q -m "not slow"
```
Purpose: run the complete non-slow suite. Writes files: pytest cache. Deterministic: yes for
test results.
## Lint and type checks
```powershell
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m mypy src tests scripts
```
Purpose: lint and type-check source, tests, and scripts. Writes files: tool caches. Deterministic:
yes for findings.
## Step 6d alignment validation
```powershell
python -m pytest tests\unit\test_model_selection.py
ruff check src tests scripts
python -m mypy src tests scripts
python -m pytest
```
Purpose: validate proposal-scoped model selection, lint, type safety, and the full test suite.
Writes files: pytest and tool caches. Deterministic: yes for findings and test results.
## Human-made data
The frozen statute PDFs/processed statutes and evaluation labels are human-made inputs and must
not be regenerated or edited by this runbook. No scripts writing to `data/processed` or
`data/eval` were run.
## Experiment B run
```powershell
python scripts\05_run_exp_b.py `
  --model bge-small-en-v1.5 `
  --chunking section_aware `
  --split dev
```
Needs `data/eval/retrieval/dev.jsonl`; not run yet.

## Retrieval demo
```powershell
python scripts\07_retrieve_demo.py `
  --model bge-small-en-v1.5 `
  --chunking section_aware `
  --query "When is acceptance complete?" `
  --k 5
```
The demo prints retrieved sections and writes no files.

## Verification run — NOT IMPLEMENTED YET
## Scoring — NOT IMPLEMENTED YET
## Analysis — NOT IMPLEMENTED YET

## Step 7 Experiment C generation
```powershell
python scripts\06_run_exp_c.py --system all --backend cloud --split pilot --dry-run
python scripts\06_run_exp_c.py --smoke
python -m ruff check src tests scripts
python -m mypy src tests scripts
python -m pytest
```
The dry run and tests use no network. `--smoke` makes exactly one real cloud request and never
reads or writes the experiment replay cache; run it only when the owner has configured the API key.
The script loads `MISAQ_GEMINI_API_KEY` from a repository-root `.env` file when it is not already
set in the process environment; `.env` is not committed.
The real cloud run is **run by owner**. The proposal's `gemini-2.5-flash-lite` model string and
provider SDK behavior are not verified in this environment.

## M1 Step B ingestion validation
```powershell
python -m pytest -q tests\unit\test_ingestion_readers.py
python -m ruff check src tests scripts
python -m mypy src tests scripts
python -m pytest
```
These commands exercise synthetic in-memory PDF/DOCX readers and the full
regression suite. Reader tests must not create files in the repository or
temporary directories and must not log document text.

## M1 Step C structure validation
```powershell
python -m pytest -q tests\unit\test_ingestion_structure.py
python -m ruff check src tests scripts
python -m mypy src tests scripts
python -m pytest
```
These commands validate deterministic structure detection using synthetic
paragraphs only. Structure keywords and thresholds are loaded from
`configs\ingestion.yaml`; held-out evaluation documents are not read.

## M1 Step D ingestion and evaluation

`scripts\08_ingest.py` prints counts, headings, and warnings by default. It writes clause text
only when `--public` is explicitly supplied with `--show-text` or `--json-out`. The future
Streamlit page must call `ingest_bytes` with bytes, bypass the replay cache, and set `cloud_ok`
only after user consent. `scripts\09_eval_ingestion.py` validates gold manifests and requires
`--final`, a clean tree, a listed hash, and a matching reader fingerprint for `test`.
