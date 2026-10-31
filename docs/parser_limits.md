# Parser and processing limits

Structure is validated against the printed CONTENTS (parse gate) and text artefacts are checked by the
processing gate. Text *correctness* against the PDF is still verified only by golden fixtures and a manual
10% spot-check.

## Fixed in step 3
- Chapter/part titles and group headings no longer leak into section text; SRA group headings are captured
  as `subheading`; SRA `chapter` now includes its PART ("PART II, CHAPTER I").
- Omission marks (`[* *]`), `Date: dd-mm-yyyy` stamps, document-id stamps and `_____` separators are removed.
- "CHAPTER VIII ... Omitted" notices (SRA) are skipped, not appended to s.44.
- Footnotes: whole entries (marker + full text), attached only to the section that cites the marker.
  Footnotes no section cites are kept as `Act.notes` (title-block notes, notes on omitted material).
- Line-end hyphens: 14 joined, 4 kept (subject-matter, non-performance, one-quarter, two-thirds), decided from
  corpus evidence; any ambiguous case keeps the hyphen and is listed in the process report.

## Still open
1. **Illustrations** run from the "Illustrations" label to the next section heading. Body text printed after
   a section's illustrations would be mislabelled as illustration. The step-3 audit found no case, but the
   check is heuristic (no indentation data is kept).
2. **Source typos handled by rule**: a superscript `l`/`I` is read as footnote marker `1` (several cases in CA
   and SRA); "Viod Agreements" is kept as printed.
3. **Contents-title wrap rule** uses a right-margin threshold (`WRAP_X1 = 480` pt). Verified on CA s.25, s.27,
   s.73 and SGA s.22. Re-check if another Act is added.
4. **Source defects kept as printed**: CA s.141 is missing from CONTENTS (accepted, flagged
   `not_in_contents`); 4 CA and 2 SGA titles differ between CONTENTS and body.
5. **Omitted ranges** (CA 76-123 and 239-266, SRA 45-51) are stored on the Act, not as sections.
6. **Line breaks inside blocks are kept** as `\n`. The chunker must normalise whitespace before embedding.
7. Footnotes whose marker sits on a skipped structural line (e.g. an omission mark) cannot be tied to a
   section; they are stored as `Act.notes`.
