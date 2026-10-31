# Step 4 data dictionary

## Sections

Processed statute records are immutable `Section` objects. They retain the Act code, normalized
section number, printed titles, chapter/subheading hierarchy, status, PDF pages, typed source
blocks, footnotes, flags, and footnote references. Only `in_force` sections enter the index.

## Chunks

Each chunk has a stable section-scoped ID, original normalized text, embedded text (optional
hierarchy header plus text), section identity, hierarchy, PDF-page provenance, source block IDs,
and footnote metadata. Chunking is section-aware or fixed-size and always uses the configured
reference tokenizer; sections are never crossed.

## Model specification

`EmbeddingModelSpec` records the Hugging Face model ID and immutable revision, vector dimension,
maximum sequence length, normalization setting, query/document prefixes, pooling, remote-code
setting, CPU batch size, and device. Query and document encoding are separate operations.

## Index metadata

`IndexMeta` records index identity, backend, processed-statute hashes, chunking/model specs, and
counts: indexed chunks, excluded repealed section records, and omitted-range section numbers.
Build throughput, elapsed time, and peak memory are stored separately in `build_report.json`.

## Experiment manifests

`runs/<run_id>/manifest.json` records the run name and time-derived ID, canonical resolved-config
SHA-256, categorized input fingerprints, model identifiers and revisions, parameters, seed, stages
with item/failure counts, output fingerprints, Git commit/branch/dirty/availability, and the
execution environment. Environment package identity is a sorted `name==version` list hash from
`importlib.metadata`, used as the reproducible stand-in for `pip freeze`. The resolved configuration
is stored as UTF-8 `resolved_config.yaml`; manifest writes are atomic and use stable key order.

## Retrieval evaluation JSONL

Each line is one human-authored retrieval query object:

| Field | Type | Requirement |
|---|---|---|
| `id` | string | Required and unique across the complete file. |
| `query` | string | Required and non-empty after trimming whitespace. |
| `gold` | array of strings | Required, non-empty, unique section IDs; every ID must identify an `in_force` frozen-corpus section. |
| `split` | string | Required split name, such as `dev` or `test`. |

Optional fields `related`, `query_type`, `source`, `annotators`, `adjudicated`, and `notes` are
accepted for provenance and analysis metadata. They are ignored by retrieval metrics. Precision@k
divides by `k` even when fewer than `k` unique sections are returned. The configured
`retrieval.top_n` value controls how many chunks are retrieved before section collapse.

Validation rejects duplicate IDs and rejects normalized query text appearing in more than one
split. Normalization trims, collapses whitespace, and applies Unicode case folding. Evaluation
metrics operate on section IDs, not chunk IDs. Duplicate retrieved section IDs count once, and
an empty gold set is an error rather than a skipped query.

## Experiment B outputs

`runs/<run_id>/items.jsonl` is append-only and resumable. Each line contains the query `id`,
`retrieved` section IDs with scores, per-k precision and recall plus MRR in `metrics`,
`latency_ms`, and `status`. Failed queries additionally contain `error_type` and `error`; they
remain recorded and are never dropped.

`runs/<run_id>/summary.json` contains `status`, `metrics_final`, mean `metrics`, percentile
bootstrap `confidence_intervals`, query `counts`, `failures`, latency p50/p95,
`peak_memory_bytes`, and the bootstrap `resamples`, `seed`, and query resampling unit.

## Citation verification

`CitationCheck` records one extracted or structured citation:

| Field | Type | Meaning |
|---|---|---|
| `item_id` | string | Source item identifier. |
| `raw_text` | string | Original citation text. |
| `normalized_id` | string or null | Corpus section ID such as `CA1872:s73`. |
| `act`, `section`, `subsection` | string or null | Normalized citation components. |
| `verdict` | enum | Verification result listed below. |
| `reason_code` | string | Machine-readable explanation. |
| `exists_in` | array of strings | Acts containing the section when the verdict is `WRONG_ACT`. |
| `in_context` | boolean or null | Context membership for S3/S4; null for S1/S2. |
| `subsection_checked` | boolean | Whether explicit subsection markers allowed a reliable check. |

| Verdict | Rule |
|---|---|
| `VALID` | Section is in force in the claimed Act. |
| `VALID_SECTION_BAD_SUBSECTION` | Section is in force but an explicitly checked subsection is absent. |
| `NONEXISTENT_SECTION` | Section is absent from the claimed Act and the corpus. |
| `WRONG_ACT` | Section exists in another corpus Act; `exists_in` is recorded. |
| `REPEALED_OR_OMITTED` | Section is a repealed record or in an Act-level omitted range. |
| `OUT_OF_CORPUS` | Act is not in this frozen corpus; this is never “fabricated”. |
| `MALFORMED` | Citation cannot be parsed or has an unspecified Act. |

### Limits

Verification is relative to the frozen processed corpus, not to real law. `WRONG_ACT` can be a
coincidence caused by overlapping section numbers between Acts. Only section citations are
extracted: Articles, Orders, Rules, and case law are not covered. Range expansion has a configured
cap; over-cap ranges are `MALFORMED`. Support judgement remains manual and is not automated.
