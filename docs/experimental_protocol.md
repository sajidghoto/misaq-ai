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

| Model | Chunking | Recall@5 | Recall@5 CI | Precision@5 | MRR | Peak RAM |
|---|---|---:|---|---:|---:|---:|
| bge-small-en-v1.5 | section_aware | pending | pending | pending | pending | pending |
| bge-small-en-v1.5 | fixed_size | pending | pending | pending | pending | pending |
| bge-base-en-v1.5 | section_aware | pending | pending | pending | pending | pending |
| bge-base-en-v1.5 | fixed_size | pending | pending | pending | pending | pending |
| bge-large-en-v1.5 | section_aware | pending | pending | pending | pending | pending |
| bge-large-en-v1.5 | fixed_size | pending | pending | pending | pending | pending |
| all-MiniLM-L6-v2 | fixed_size | pending | pending | pending | pending | pending |

## 5. Step 10: development selection

After all development summaries are available:

1. Find the highest eligible Recall@5.
2. Exclude runs above 8 GB peak RAM.
3. Keep models within `0.02` of the best eligible Recall@5.
4. Choose the smallest remaining model.
5. Use `section_aware` as the selection chunking mode.
6. Report the confidence interval and explain that 29 queries produce wide
   intervals, so small differences may not be meaningful.

Selected model: bge-base-en-v1.5
Selected chunking: section_aware
Selected Recall@5: 0.690
Recall@5 confidence interval: approximately 0.50–0.86 (95% bootstrap CI)
Peak RAM: 106745

No test result may be used to change this rule or selection.
