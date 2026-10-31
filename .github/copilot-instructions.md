# Misaq AI rules
RAG system: analyses contract clauses against frozen statutes and verifies every statute citation. Correctness and reproducibility first.

Start: read `docs/ai/state.md`. Open other docs only when the task needs them. End: update `state.md` in 3 lines.

## Architecture
`domain` <- feature packages <- `scripts`/`app`. `domain/` imports nothing from the project and does no I/O. `scripts/` and `app/` hold no logic. Changing a `domain/` schema: ask first.

## Never modify without approval
`data/processed/statutes/`, `data/eval/**`, `SHA256SUMS`, finished `runs/`, `src/misaq/contracts/`, `tests/golden/fixtures/`.

## Research integrity
- Citation verdicts are named enums, never bools. `OUT_OF_CORPUS` is not "fabricated".
- Support judgement is manual. Failed items are recorded with `status="error"`, never dropped.
- Never tune on `test.jsonl`. Never invent data, section numbers or metrics. Take values from `configs/`.

## Code
Typed, `ruff` and `mypy` clean. No bare `except`; use specific `MisaqError` subclasses. Retry only rate-limit and timeout. Build stages fail loudly. No new dependency without asking.

## Tokens
Read file ranges, not whole files. Never print JSONL, indexes or PDFs. Minimal diffs. Run the narrowest test first. Short replies. Never claim a test passed unless you ran it.
