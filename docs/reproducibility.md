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
Purpose: verify every frozen processed statute against `SHA256SUMS`. Writes files: no.
Deterministic: yes.
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
## Human-made data
The frozen statute PDFs/processed statutes and evaluation labels are human-made inputs and must
not be regenerated or edited by this runbook. No scripts writing to `data/processed` or
`data/eval` were run.
## Experiment B run — NOT IMPLEMENTED YET
## Verification run — NOT IMPLEMENTED YET
## Scoring — NOT IMPLEMENTED YET
## Analysis — NOT IMPLEMENTED YET
