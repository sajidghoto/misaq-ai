Updated: 2026-11-01 — Step 7 smoke now bypasses all replay caches, makes one non-retrying cloud call, and reports response metadata only.
Selection tolerance and maximum RAM budget remain null in configs/pipeline.yaml; the proposal-scope decision is dense FAISS only.
Cloud smoke loads the repository-root .env without overriding process variables; missing keys fail as AuthError.
The smoke loader tests pass, and the example uses the configured MISAQ_GEMINI_API_KEY placeholder.
