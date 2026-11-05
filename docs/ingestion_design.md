# M1 Ingestion Design

## Scope and pipeline

Accept in-memory bytes for English, selectable-text PDF or DOCX service/freelance
agreements, NDAs, and sale-of-goods agreements. Scanned/image-only documents are
rejected. Stages are: validate extension and byte input; open and decrypt-check;
extract paragraphs and PDF page/layout features; detect headings and numbering;
build a `ContractNode` tree; select bounded analysis units; emit immutable clauses,
provenance, and an `IngestionReport`. No network, LLM, ML model, or disk I/O is
performed by this package.

## Data model

* `Paragraph`: immutable text plus source index, page, style/name, bounding-box
  features, font-size/bold/italic flags, line spacing, indentation, and numbering
  evidence. Text is retained; layout features are deterministic.
* `ContractNode`: immutable node path, optional heading/label, ordered body paragraph
  indexes, child nodes, source pages, and classification confidence/warnings. The
  Step C implementation is in `src/misaq/ingestion/structure/`.
* `IngestionReport`: status, format, counts, warnings, error code/message, and
  coverage/provenance summaries; never contains contract text.
* `IngestionResult`: ordered `Clause` values plus the report. Clause IDs are derived
  from a content hash and node path, never from a filename.

Every body paragraph appears in exactly one node and in source order. No text is
dropped silently. Each analysis unit keeps page and paragraph-index provenance and
must fit the configured reference-tokenizer query limit; over-limit content is
split deterministically, never silently truncated.

## Domain and compatibility

Additive `Clause` fields are optional with defaults: `heading`, `label`, `path`,
`parent_clause_id`, `source_pages`, `kind`, `confidence`, and `warnings`.
Uploaded clauses default to `cloud_ok=False`. Existing `Clause` consumers use
`clause_id` and `text`, so the additions preserve that contract. Existing
`load_clauses` does not yet deserialize these fields and must be updated in the
implementation step. `ContractMeta` currently carries only identity/source/licence;
ingestion provenance belongs on `Clause` and the result report.

## Errors and user-facing messages

All are `MisaqError` subclasses and are recorded per input without stopping a
batch: `UnsupportedFileError` — “Unsupported file type. Upload a PDF or DOCX.”
`EmptyDocumentError` — “The document is empty or contains no selectable text.”
`ScannedDocumentError` — “Scanned or image-only documents are not supported.”
`EncryptedDocumentError` — “The document is encrypted or password-protected.”
`CorruptFileError` — “The document could not be read because it is corrupt.”

## `configs/ingestion.yaml` schema

```yaml
format: {allowed_extensions: [".pdf", ".docx"], language: "en"}
heading_keywords: {agreement: ["agreement", "nda", "terms"], schedule: ["schedule", "annex"]}
classification_keywords:
  obligation: ["shall", "must", "will"]
  prohibition: ["shall not", "may not", "prohibited"]
  definition: ["means", "defined as"]
thresholds:
  min_selectable_chars: 1
  heading_confidence: 0.80
  numbering_confidence: 0.80
  max_query_tokens: 512
  reference_tokenizer: "configs/pipeline.yaml#reference_tokenizer"
```

## Deterministic algorithm

Normalize whitespace only for analysis while retaining original paragraph text.
Detect numbering schemes from repeated labels (decimal, alpha, Roman, and
parenthesized forms), requiring configured evidence and monotonic sibling order.
Classify heading candidates from numbering, style/layout signals, and keywords.
Build hierarchy using numbering depth first, then heading level and indentation;
unattached text becomes an explicit node rather than being discarded. Select
analysis units as leaf/body groups, splitting at paragraph boundaries to satisfy
`max_query_tokens` with the reference tokenizer. Hash normalized unit content plus
node path for the stable ID.

## Privacy

The API accepts bytes and returns memory-resident objects only. No temporary files,
uploaded text in logs/reports, replay cache, network calls, or persistent cache are
allowed. Error messages contain format/status only; diagnostics use counts, hashes,
and indexes, never text. `cloud_ok` remains false until an explicit later policy
decision.

## Evaluation, risks, and limits

Use a document-level dev/test split; keep the held-out test set untouched during
threshold selection. Measure format/error accuracy, paragraph coverage/order,
heading and parent accuracy, clause-boundary precision/recall/F1, unit token-limit
compliance, and privacy leakage checks. Risks include PDF reading-order errors,
ambiguous headings, broken numbering, DOCX style inconsistency, tables/footnotes,
and tokenizer/version drift. English selectable text only; scanned files, images,
handwriting, semantic interpretation, and legal validity are out of scope.
