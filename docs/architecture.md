# Misaq AI Architecture

## 1. Purpose

Misaq AI is a research prototype for analysing contract clauses against a frozen
collection of statute records. Its central requirement is traceability:

1. statute text must be tied to source artifacts;
2. retrieval results must identify source sections;
3. generated claims must retain their citations;
4. citations must be checked against the frozen corpus; and
5. experiment outputs must record inputs, configuration, code state, and failures.

The system supports research experiments. It does not provide legal advice, and a
successful citation check means only that the citation matches the frozen corpus and
its configured rules.

## 2. System flow

```text
data/raw/statutes/
        |
        |  scripts/01_parse_statutes.py
        v
data/interim/02_parsed/
        |
        |  scripts/02_process_statutes.py
        v
data/processed/statutes/
        |
        |  chunking + embedding
        |  scripts/03_build_index.py
        v
data/index/
        |
        |  DenseRetriever
        v
retrieved section IDs
        |
        |  GenerationPipeline
        v
structured claims and citations
        |
        |  citation extraction + verification
        v
verification records and experiment outputs
        |
        |  evaluation and statistical summaries
        v
runs/<run_id>/
```

The processed statute records are the boundary between corpus preparation and
experimentation. Once approved and hashed, they are treated as frozen inputs.

## 3. Repository layers

### `src/misaq/domain`

Defines the stable data model and domain rules: statutes, sections, chunks, embeddings,
retrieval objects, generation records, and domain errors.

The domain layer must remain independent of project I/O. It should not read files,
call APIs, or depend on application entry points.

### Feature packages

The feature packages implement one stage of the research pipeline:

| Package | Responsibility |
|---|---|
| `parsing` | Extract statute structure and text from source PDFs |
| `processing` | Apply approved normalization, status, footnote, and hyphen rules |
| `chunking` | Create section-scoped retrieval chunks |
| `embedding` | Encode queries and documents with configured models |
| `indexing` | Build, save, load, and validate FAISS indexes |
| `retrieval` | Retrieve chunks and collapse results to section-level results |
| `generation` | Run local or cloud generation with controlled parameters |
| `verification` | Parse citations and classify them against the corpus |
| `evaluation` | Calculate retrieval and experiment statistics |
| `validation` | Validate input data, processed statutes, chunks, and indexes |
| `experiments` | Create manifests, fingerprints, and resumable run artifacts |

### `scripts`

Scripts are thin, reproducible entry points:

- `01_parse_statutes.py` runs source parsing.
- `02_process_statutes.py` creates processed statute records.
- `03_build_index.py` builds retrieval indexes.
- `05_run_exp_b.py` runs retrieval evaluation.
- `06_run_exp_c.py` runs generation experiments and the cloud smoke test.

Business logic belongs in `src/misaq`, not in scripts.

### `app`

This is reserved for application-facing entry points. It should coordinate the system,
not contain domain or experiment logic.

## 4. Data and artifact boundaries

```text
raw       Original source inputs
interim   Rebuildable parse/process outputs and reports
processed Approved normalized statute records
index     Derived retrieval artifacts
eval      Human-authored evaluation inputs
runs      Experiment outputs
```

### Frozen inputs

The following require explicit approval before modification:

- `data/processed/statutes/`
- `data/eval/`
- `tests/golden/fixtures/`
- completed `runs/`

Processed statute hashes are checked through `SHA256SUMS`. Evaluation data is validated
for unique identifiers, valid section IDs, split consistency, and non-empty gold labels.

### Derived artifacts

Indexes and experiment runs can be regenerated, but their manifests must preserve the
configuration, input fingerprints, model identifiers, Git state, environment identity,
and output information needed for comparison.

## 5. Retrieval architecture

The current retrieval path is dense retrieval:

1. approved statute sections are converted to chunks;
2. chunks are encoded with the configured embedding model;
3. vectors are stored in a FAISS index;
4. a query is encoded with the same model;
5. nearest chunks are retrieved;
6. duplicate section IDs are collapsed for section-level metrics.

Two configured chunking strategies are available:

- `section_aware`: section-scoped chunks with a larger token budget;
- `fixed_size`: fixed-size chunks with overlap.

The index metadata records the corpus hashes, model specification, chunking specification,
and counts of indexed, repealed, and omitted content.

## 6. Generation architecture

Experiment C uses a common generation pipeline with interchangeable backends:

- `LocalBackend` supports local execution.
- `CloudBackend` supports the configured Gemini provider.
- `ReplayCache` makes approved generation runs resumable.

The systems are configured as `S1` through `S4`. The exact distinction between systems
is defined by the generation pipeline and experiment configuration; generated records
retain the system name and relevant retrieved or oracle section IDs.

Structured output is expected to contain:

```json
{
  "claims": [
    {
      "issue": "string",
      "explanation": "string",
      "citations": ["string"]
    }
  ],
  "no_supported_provision": false
}
```

Malformed output remains in the run as an error item. It is not silently discarded.

## 7. Citation verification

Citation verification is relative to the frozen processed corpus. It distinguishes
named verdicts such as:

- `VALID`
- `VALID_SECTION_BAD_SUBSECTION`
- `NONEXISTENT_SECTION`
- `WRONG_ACT`
- `REPEALED_OR_OMITTED`
- `OUT_OF_CORPUS`
- `MALFORMED`

`OUT_OF_CORPUS` means that the cited Act is outside this experiment's corpus. It does
not mean that the citation is fabricated. Support judgement remains manual and is not
automated by this prototype.

## 8. Reproducibility model

Every substantive run should be identifiable by:

- resolved configuration;
- input and evaluation fingerprints;
- model names and immutable revisions;
- algorithm versions;
- random seed where applicable;
- Git commit, branch, and dirty state;
- environment package identity;
- per-item outputs and failures;
- summary metrics and confidence intervals.

Experiment output is append-only and resumable where supported. Failed records remain
visible so that a result cannot appear complete by silently omitting difficult items.

The commands for setup, validation, index building, and experiments are maintained in
[`reproducibility.md`](reproducibility.md).

## 9. Contributor rules

When changing the system:

1. Read the relevant package and its tests before editing.
2. Keep domain code pure and typed.
3. Reuse existing domain objects and validators.
4. Do not modify frozen research inputs without approval.
5. Add or update focused tests for behavior changes.
6. Run the narrowest relevant tests, Ruff, and mypy.
7. Preserve failure records and explicit error reporting.
8. Update the relevant documentation when workflow or artifact behavior changes.

## 10. Current boundaries and open work

The architecture is implemented through the retrieval and generation foundations, but
the research workflow is not yet a completely finished publication pipeline. In
particular:

- verification, scoring, and analysis procedures still need to be completed in the
  reproducibility runbook;
- evaluation-data provenance in the data card still needs human-authored completion;
- model-selection tolerance and memory thresholds are not yet configured;
- the real cloud model and provider behavior require owner validation; and
- the cloud backend still has known mypy typing issues.

These are research-completion tasks, not reasons to bypass the existing validation and
artifact controls.
