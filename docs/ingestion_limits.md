# Ingestion limits

M1 Step B readers accept selectable-text PDF and DOCX bytes in memory. They do
not perform network access, model inference, temporary-file I/O, OCR, or legal
interpretation.

PDF reading uses PyMuPDF spans and deterministic geometry. Repeated text in
top and bottom margin bands is treated as header/footer noise, columns are
read left-to-right, and line-level hyphenation is joined. Table support depends
on the installed PyMuPDF `find_tables` API; when it is unavailable, table text
is flattened and a warning is returned. Complex reading order, floating objects,
footnotes, and scanned/image-only documents are not guaranteed and scanned
documents are rejected.

DOCX reading follows body XML order, including tables. Automatic numbering is
reported from `numbering.xml` for decimal, alphabetic, Roman, and bullet
formats, including nested levels and restarts. Headers, footers, comments, and
text boxes are ignored with a warning when present. Tracked changes use final
text: insertions are kept, deletions are dropped, and a warning is returned.

M1 Step C detects decimal, alphabetic, Roman, named, and mixed labels, including
sequence-aware nesting and deterministic paths. It also recognizes styled and
all-caps headings, run-in headings, recitals, definitions, operative clauses,
signature blocks, schedules, annexures, and boilerplate. Every input paragraph
is retained in exactly one node; ambiguous transitions, gaps, restarts, and
low-confidence unnumbered segmentation are reported as warnings.

Structure detection does not infer legal meaning, repair malformed numbering,
interpret tables as clauses, or guarantee correct hierarchy when layout and
numbering disagree. Keyword classification is English-only and configured in
`configs/ingestion.yaml`; operative-clause candidates are the default analysis
surface. Heading confidence and numbering confidence are signals, not legal
validity judgements.

Normalization is Unicode NFKC plus deterministic quote, bullet, ligature,
soft-hyphen, and whitespace handling. The reader version and code/config
fingerprint must be stored with later annotations.
