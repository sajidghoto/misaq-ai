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
