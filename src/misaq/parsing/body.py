"""Stage 2b: walk the body and cut it into sections, using CONTENTS order as the guide.

A heading becomes a section only if it is a bold line-start number that is the next
unseen CONTENTS entry. A bold heading that fits the number sequence but is missing from
CONTENTS is accepted with flag 'not_in_contents' and listed for human review.
Anything else is attached to the current section or listed in `review`.

Structural lines (PART / CHAPTER lines, their titles, group headings) are never section text.
Footnotes are collected per page as whole entries (marker + text). Each section records the
markers it cites so processing can attach the right footnote to the right section.
"""
from __future__ import annotations

import collections
import re
from typing import cast

from .pdf_lines import CHAP_RE, NUM, SEC_RE, body_text_size, is_noise, norm_num, page_lines

CENTERED_X0 = 150        # structural headings are centred, so they start right of this x (pt)
HEADING_MAX_LEN = 100
_OMITTED_NOTICE = re.compile(r"Omitted|Repealed")


def _heading_text(r: dict) -> str:
    head = "".join(s["text"] for s in r["spans"] if s["flags"] & 16).strip()
    return re.sub(r"^\[?\s*" + NUM + r"\s*\.\s*", "", head)


def _leading_int(number: str) -> int:
    return int(cast(re.Match[str], re.match(r"\d+", number)).group())


def _new_section(n, head, rest, chapter, subhead, page, marks, flag=None):
    cur = dict(number=n, title_body=head, chapter=chapter, subheading=subhead, pages=[page],
               blocks=[], refs=list(marks), _await_title=(not rest) and not head.endswith("."))
    rest = rest.lstrip(".:—―-_ ").strip()
    if rest:
        cur["blocks"].append(dict(type="body", text=rest))
    if flag:
        cur["flag"] = flag
        cur["_await_title"] = False
    return cur


def parse_body(doc, start: int, toc: list[dict]):
    """Returns (raw_sections, review_items, contents_entries_never_found)."""
    expected = [e["number"] for e in toc]
    pos = 0
    sections: list[dict] = []
    review: list[dict] = []
    part, chapter, subhead, cur, mode = None, "PRELIMINARY", None, None, "body"
    in_notice = False   # inside a multi-line "CHAPTER X. [...] Omitted by ..." notice
    footnotes: dict[int, list[dict]] = collections.defaultdict(list)

    for pn in range(start, len(doc)):
        page = pn + 1
        lines = page_lines(doc[pn])
        body_size = body_text_size(lines) if lines else 12
        for r in lines:
            if is_noise(r):
                continue
            t = r["text"]

            if r["size"] < body_size - 1.5:                           # footnote line
                fl = footnotes[page]
                if not r["markers"] and re.match(r"^[lI][A-Z][a-z]", t):      # marker misprinted as a letter
                    r = {**r, "markers": ["1"]}
                    t = t[1:]
                    review.append(dict(page=page, line=t[:60], reason="footnote marker printed as a letter, read as 1"))
                if r["markers"] or not fl:
                    fl.append(dict(marker=r["markers"][0] if r["markers"] else "", text=t))
                else:
                    fl[-1]["text"] += " " + t                         # wrapped footnote line
                continue

            if in_notice and r["italic"]:
                continue                                              # rest of the omitted-chapter notice
            in_notice = False
            c = CHAP_RE.match(t)
            if c and (_OMITTED_NOTICE.search(t) or (not r["bold"] and r["x0"] > CENTERED_X0)):
                label = f"{c.group(1)} {c.group(2)}"
                if c.group(1) == "PART":
                    part, chapter = label, label
                else:
                    chapter = f"{part}, {label}" if part else label
                subhead, mode = None, "body"
                in_notice = bool(_OMITTED_NOTICE.search(t))
                continue

            if r["italic"] and t.lower().startswith("illustration"):
                if cur:
                    mode = "illustration"
                continue

            if r["x0"] > CENTERED_X0 and r["bold"] and len(t) < HEADING_MAX_LEN and not re.match(r"^\d", t):
                if r["italic"]:
                    subhead = t                                        # group heading
                continue                                               # chapter / part titles

            marks = [(page, m) for m in r["markers"]]
            m = SEC_RE.match(t)
            if m and r["bold"] and pos < len(expected):
                n = norm_num(m)
                rest = "".join(s["text"] for s in r["spans"] if not (s["flags"] & 16)).strip()
                if n == expected[pos]:
                    cur = _new_section(n, _heading_text(r), rest, chapter, subhead, page, marks)
                    sections.append(cur)
                    pos += 1
                    mode = "body"
                    continue
                if (n not in expected and sections and re.match(r"^\d+$", n)
                        and _leading_int(sections[-1]["number"]) < int(m.group(1))
                        <= _leading_int(expected[pos])):
                    cur = _new_section(n, _heading_text(r), rest, chapter, subhead, page, marks,
                                       flag="not_in_contents")
                    sections.append(cur)
                    mode = "body"
                    review.append(dict(page=page, line=t[:80],
                                       reason=f"section {n} accepted: in body, missing from printed contents"))
                    continue
                why = "not in contents" if n not in expected else "out of order"
                review.append(dict(page=page, line=t[:80],
                                   reason=f"bold heading {n} {why} (expected {expected[pos]})"))

            if cur is None:
                continue
            cur["refs"].extend(marks)
            if cur.get("_await_title") and r["bold"] and not SEC_RE.match(t):   # wrapped title
                cur["title_body"] += " " + t.strip()
                cur["_await_title"] = not t.strip().endswith(".")
                continue
            cur["_await_title"] = False
            if page not in cur["pages"]:
                cur["pages"].append(page)
            if re.match(r"^(Explanation|Exception)\b", t):
                mode = "explanation"
            elif re.match(r"^Provided\b", t):
                mode = "proviso"
            elif mode in ("explanation", "proviso") and re.match(r"^\(\d+\)", t):
                mode = "body"
            last = cur["blocks"][-1] if cur["blocks"] else None
            if (last and last["type"] == mode and r["x0"] <= 110 and not re.match(r"^\(", t)
                    and not re.match(r"^(Provided|Explanation|Exception)", t)):
                last["text"] += "\n" + t
            elif last and last["type"] == mode and r["x0"] > 110:
                last["text"] += "\n" + t
            else:
                cur["blocks"].append(dict(type=mode, text=t))

    for s in sections:
        s["footnotes"] = [dict(page=p, **fn) for p in s["pages"] for fn in footnotes.get(p, [])]
        s["refs"] = list(dict.fromkeys(s["refs"]))
        s.pop("_await_title", None)
    return sections, review, expected[pos:]
