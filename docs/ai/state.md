Updated: 2026-11-01 — Step 6d aligned retrieval with the proposal: dense FAISS only and four active embedding candidates.
Decision: Qwen3-Embedding, bge-m3, and nomic were considered but remain out of scope; selection uses parameter_count and requires team-set Recall@5 tolerance and RAM budget.
Validation: Step 6d ruff, mypy, and full pytest pass (168 tests); protected data untouched and no weights downloaded. Rule: every finished step appends its exact commands to docs/reproducibility.md.
