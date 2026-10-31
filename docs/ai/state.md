Updated: 2026-10-31 — Step 4 done; algorithm version 2, exact section-aware budgeting, CLI, and no-truncation validation verified.
Step 4 decisions: English-only exact FAISS flat inner-product search on normalized CPU vectors; protected data unchanged; Qwen query_prefix remains unverified.
Evidence: indexes a9c430c672eaac3a/e8bd74b651abb2f9 (section/fixed), 357/427 chunks; repeated FAISS hashes match; ruff/mypy pass; full pytest 122 passed; `make` unavailable on Windows, equivalent `pytest -m "not slow"` passed.
