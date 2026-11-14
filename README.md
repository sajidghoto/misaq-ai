# Misaq AI

Misaq AI is a research prototype for statute-grounded contract-clause analysis.
It retrieves relevant provisions from a frozen corpus of Pakistani statutes, generates
structured clause analysis, and verifies statute citations against that corpus.

The project prioritizes correctness, reproducibility, and traceable research artifacts.
It is not a substitute for legal advice and its verification results are relative to the
frozen corpus used by the experiment.

## What the system does

```text
Frozen statute corpus
        |
        v
Parse and process statutes
        |
        v
Create section-aware chunks
        |
        v
Embed chunks and build FAISS indexes
        |
        v
Retrieve relevant statutory sections
        |
        v
Generate clause analysis (S1-S4)
        |
        v
Extract and verify statute citations
        |
        v
Evaluate and analyse experiment results
```

## Repository map

```text
configs/       Pipeline, model, backend, and experiment configuration
data/raw/      Source statute files
data/interim/  Parse and processing reports
data/processed Frozen processed statute records and hashes
data/index/    Built retrieval indexes
data/eval/     Human-authored evaluation data
docs/          Architecture, data, parser, and reproducibility documentation
runs/          Experiment outputs and manifests
scripts/       Command-line pipeline and experiment entry points
src/misaq/     Application packages
tests/         Unit, contract, integration, and golden tests
```

Read [`docs/architecture.md`](docs/architecture.md) for the system design and package
responsibilities. Read [`docs/reproducibility.md`](docs/reproducibility.md) for the
operational runbook.

## Requirements

- Windows PowerShell or an equivalent Python environment
- Python 3.10 or newer
- Internet access when downloading embedding models
- An API key only for real cloud-generation runs

## Installation

From the repository root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,embed]"
```

For the optional cloud generation backend:

```powershell
python -m pip install -e ".[cloud]"
```

## Clone and line-ending policy

Clone the repository normally; no local `core.autocrlf` setting is required:

```powershell
git clone https://github.com/sajidghoto/misaq-ai.git
cd misaq-ai
```

On checkout, `.gitattributes` keeps processed statute JSON and checksum-controlled
evaluation JSONL files as LF. Source PDFs are treated as binary. This matters because the
manifests contain SHA-256 digests of the files' raw bytes, not normalized JSON semantics;
the expected hashes therefore remain identical on Windows, Linux, and macOS. A pre-existing
checkout is not rewritten retroactively when the policy is added; validate a fresh clone
to apply the policy without manually editing protected inputs.

## First validation

Confirm that the frozen processed statutes have not changed:

```powershell
python -c "from pathlib import Path; from misaq.validation.statutes import check_processed_hashes; check_processed_hashes(Path('data/processed/statutes')); print('processed statute hashes: OK')"
```

The checker verifies every statute listed by `ActCode` against the raw-byte digests in
`data/processed/statutes/SHA256SUMS`. Do not edit the manifest to make a mismatch pass.
Check the file's line endings and review the content diff against the trusted revision.
If the legal content genuinely changed, stop and follow the project's approval and
provenance process before changing the frozen corpus or its hashes.

Run the non-slow test suite:

```powershell
python -m pytest -q -m "not slow"
```

Run lint and type checks:

```powershell
python -m ruff check src tests scripts
python -m mypy src tests scripts
```

## Building indexes

Indexes are generated locally; only `index_meta.json` and `build_report.json` are tracked.
Run the following reproduction steps in order from the repository root:

1. `python scripts\03_build_index.py --model bge-small-en-v1.5 --chunking fixed_size`
   Expected `index_id`: `e8bd74b651abb2f9`.
2. `python scripts\03_build_index.py --model bge-small-en-v1.5 --chunking section_aware`
   Expected `index_id`: `a9c430c672eaac3a`.
3. `python scripts\03_build_index.py --model bge-base-en-v1.5 --chunking fixed_size`
   Expected `index_id`: `9e5afae9a3dac0ba`.
4. `python scripts\03_build_index.py --model bge-base-en-v1.5 --chunking section_aware`
   Expected `index_id`: `6de409c1f5c1273c`.
5. `python scripts\03_build_index.py --model bge-large-en-v1.5 --chunking fixed_size`
   Expected `index_id`: `d60113fbca586acc`.
6. `python scripts\03_build_index.py --model bge-large-en-v1.5 --chunking section_aware`
   Expected `index_id`: `b3034f148b0d5021`.
7. `python scripts\03_build_index.py --model all-MiniLM-L6-v2 --chunking fixed_size`
   Expected `index_id`: `37be8681be8ffd64`.

A matching ID after rebuilding confirms the same configuration. The
`all-MiniLM-L6-v2` + `section_aware` combination is not buildable because its 256-token
limit is below the section-aware chunking budget.

Rebuilt vectors may differ numerically across machines, even when the `index_id` matches.
After rebuilding the indexes, run Experiment B:

```powershell
python scripts\05_run_exp_b.py `
  --model bge-small-en-v1.5 `
  --chunking section_aware `
  --split dev
```

Index builds write files below `data/index`; vector payloads are local artifacts.

## Running Experiment B

Experiment B evaluates dense retrieval on the configured human-authored evaluation data:

```powershell
python scripts\05_run_exp_b.py `
  --model bge-small-en-v1.5 `
  --chunking section_aware `
  --split dev
```

Each run writes a timestamped directory under `runs/` containing a manifest, resolved
configuration, append-only item results, and a summary.

The test split is protected and requires a clean Git tree, verified processed-statute
hashes, a listed evaluation-data hash, and the explicit `--final` flag:

```powershell
python scripts\05_run_exp_b.py `
  --model bge-small-en-v1.5 `
  --chunking section_aware `
  --split test `
  --final
```

Do not tune implementation or configuration choices on the test split.

## Running Experiment C

Perform a network-free dry run first:

```powershell
python scripts\06_run_exp_c.py --system all --backend cloud --split pilot --dry-run
```

To make the one-request cloud smoke test, configure `MISAQ_GEMINI_API_KEY` in the
process environment or in an uncommitted repository-root `.env` file:

```powershell
$env:MISAQ_GEMINI_API_KEY = "your-key"
python scripts\06_run_exp_c.py --smoke
```

Never commit API keys or `.env` files. The real cloud run is owner-controlled because
model availability, SDK behavior, cost, and quota must be confirmed before execution.

## Important research rules

- Treat processed statutes and evaluation labels as controlled research inputs.
- Do not edit or regenerate protected data without explicit approval.
- Do not tune on `test.jsonl`.
- Never drop failed experiment items; record them with an error status.
- Citation verdicts are named outcomes. `OUT_OF_CORPUS` does not mean fabricated.
- Interpret verification relative to the frozen corpus, not as a claim about all current law.

## Current status

The implementation includes the parsing, processing, indexing, retrieval, generation,
verification, validation, and experiment-manifest foundations. The remaining research
work includes completing the verification/scoring/analysis runbook, finalizing evaluation
data documentation, confirming model-selection thresholds, and validating the real cloud
model run.

## Further reading

- [`docs/architecture.md`](docs/architecture.md) — system design and package boundaries
- [`docs/reproducibility.md`](docs/reproducibility.md) — commands and experiment procedure
- [`docs/data_dictionary.md`](docs/data_dictionary.md) — artifact schemas and meanings
- [`docs/parser_limits.md`](docs/parser_limits.md) — parser behavior and known limitations
- [`data/eval/DATACARD.md`](data/eval/DATACARD.md) — evaluation-data provenance
