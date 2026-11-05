# Experiment B Retrieval Protocol

## 1. Dataset and configuration

The retrieval evaluation uses the human-authored development file:

```text
data/eval/retrieval/dev.jsonl
```

The resolved Experiment B configuration is stored in
`configs/experiments/exp_b_retrieval.yaml`. It reports Recall, Precision, and MRR at
`k = 1, 3, 5, 10`, using 10,000 bootstrap resamples and seed `20261031`.

The selection rule is:

- selection tolerance for Recall@5: `0.02`;
- maximum peak RAM: `8 GB`;
- selection chunking mode: `section_aware`;
- reported value: `k = 5`;
- select the smallest model whose development Recall@5 is within the tolerance of
  the best eligible result and whose peak RAM is within the budget.

The test split must not be used for model or configuration selection.

## 2. Step 7: model support

`scripts/03_build_index.py` was extended to accept the four configured models:

```text
bge-small-en-v1.5
bge-base-en-v1.5
bge-large-en-v1.5
all-MiniLM-L6-v2
```

The builder still uses the configured frozen statute corpus, tokenizer, chunking
specification, and index validation.

## 3. Step 8: index-build record

Successful index builds were completed for:

| Model | section_aware | fixed_size |
|---|---:|---:|
| bge-small-en-v1.5 | yes | yes |
| bge-base-en-v1.5 | yes | yes |
| bge-large-en-v1.5 | yes | yes |
| all-MiniLM-L6-v2 | no | yes |

`all-MiniLM-L6-v2` section-aware failed because the shared section-aware chunk
budget can produce 400-token chunks, while this model is configured for a
256-token maximum input length. This incompatibility is recorded rather than
silently changing the chunking configuration.

## 4. Step 9: development retrieval runs

Run one command for each successful combination:

```powershell
python scripts\05_run_exp_b.py --model bge-small-en-v1.5 --chunking section_aware --split dev
python scripts\05_run_exp_b.py --model bge-small-en-v1.5 --chunking fixed_size --split dev
python scripts\05_run_exp_b.py --model bge-base-en-v1.5 --chunking section_aware --split dev
python scripts\05_run_exp_b.py --model bge-base-en-v1.5 --chunking fixed_size --split dev
python scripts\05_run_exp_b.py --model bge-large-en-v1.5 --chunking section_aware --split dev
python scripts\05_run_exp_b.py --model bge-large-en-v1.5 --chunking fixed_size --split dev
python scripts\05_run_exp_b.py --model all-MiniLM-L6-v2 --chunking fixed_size --split dev
```

Each run writes `summary.json` below `runs/`. Record the following from every
summary:

| Model | Chunking | Recall@5 | Recall@5 CI | Precision@5 | MRR | Peak RAM (bytes) |
|---|---|---:|---|---:|---:|---:|
| bge-small-en-v1.5 | section_aware | 0.6897 | 0.5172–0.8621 | 0.1517 | 0.5391 | 103401 |
| bge-small-en-v1.5 | fixed_size | 0.6897 | 0.5172–0.8621 | 0.1517 | 0.5443 | 105925 |
| bge-base-en-v1.5 | section_aware | 0.6897 | 0.5172–0.8448 | 0.1586 | 0.6585 | 106745 |
| bge-base-en-v1.5 | fixed_size | 0.6552 | 0.4828–0.8103 | 0.1517 | 0.6093 | 103135 |
| bge-large-en-v1.5 | section_aware | 0.7414 | 0.5690–0.8966 | 0.1655 | 0.6368 | 158530 |
| bge-large-en-v1.5 | fixed_size | 0.7414 | 0.5690–0.8966 | 0.1655 | 0.6069 | 158489 |
| all-MiniLM-L6-v2 | fixed_size | 0.6207 | 0.4483–0.7931 | 0.1448 | 0.4569 | 105599 |

## 5. Step 10: development selection

After all development summaries are available:

1. Find the highest eligible Recall@5.
2. Exclude runs above 8 GB peak RAM.
3. Keep models within `0.02` of the best eligible Recall@5.
4. Choose the smallest remaining model.
5. Use `section_aware` as the selection chunking mode.
6. Report the confidence interval and explain that 29 queries produce wide
   intervals, so small differences may not be meaningful.

The best eligible section-aware result is `bge-large-en-v1.5` with Recall@5
`0.7414`. The smaller section-aware models score `0.6897`, which is more than
the `0.02` tolerance below the best result. Therefore the rule selects:

Selected model: **bge-large-en-v1.5**
Selected chunking: section_aware
Selected Recall@5: **0.7414**
Recall@5 confidence interval: **0.5690–0.8966**
Peak RAM: **158530 bytes** (approximately 0.15 MiB as reported by the run)

No test result may be used to change this rule or selection.

## 6. Final test run record

The completed test run used `bge-base-en-v1.5` with `section_aware`, 29 queries,
and completed with no errors or missing items. It is recorded as a separate
test run because the pre-written selection rule selects `bge-large-en-v1.5`.
It must not be presented as the final test result for the selected model.

| Metric | Test result | 95% bootstrap CI |
|---|---:|---|
| Recall@1 | 0.1379 | 0.0345–0.2759 |
| Recall@3 | 0.3448 | 0.1724–0.5172 |
| Recall@5 | 0.4138 | 0.2414–0.5862 |
| Recall@10 | 0.5862 | 0.4138–0.7586 |
| Precision@1 | 0.1379 | 0.0345–0.2759 |
| Precision@3 | 0.1149 | 0.0575–0.1724 |
| Precision@5 | 0.0828 | 0.0483–0.1172 |
| Precision@10 | 0.0586 | 0.0414–0.0759 |
| MRR | 0.2610 | 0.1453–0.3883 |

Test status was complete: 29 of 29 items completed, zero errors, and zero
missing items. Median latency was 143.38 ms and p95 latency was 206.56 ms.
The reported peak memory field was 99945 bytes.

To obtain a final test result for the selected configuration, run the protected
test split once with `bge-large-en-v1.5` and `section_aware` after committing
this documentation and ensuring a clean Git tree.
