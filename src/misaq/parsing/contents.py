"""Stage 2a: read the printed CONTENTS. This is the ground truth for which sections exist."""
from __future__ import annotations

import re

from .pdf_lines import CHAP_RE, SEC_RE, is_noise, norm_num, page_lines

WRAP_X1 = 480   # a title line reaching past this x (pt) is assumed to wrap onto the next line


def parse_contents(doc, upto: int) -> tuple[list[dict], list[tuple[int, int]]]:
    """Returns (entries, omitted_ranges). Entry keys: number, title, chapter, extra."""
    entries: list[dict] = []
    omitted: list[tuple[int, int]] = []
    chapter, cur = None, None
    for pn in range(upto):
        for r in page_lines(doc[pn]):
            if is_noise(r):
                continue
            t = r["text"]
            m = re.match(r"^(\d+)\s+to\s+(\d+)\.\s*\[?(Omitted|Repealed)", t)
            if m:
                omitted.append((int(m.group(1)), int(m.group(2))))
                cur = None
                continue
            c = CHAP_RE.match(t)
            if c and r["x0"] > 100 or (c and not re.match(r"^\d", t)):
                chapter = f"{c.group(1)} {c.group(2)}"
                cur = None
                continue
            m = SEC_RE.match(t)
            if m and r["x0"] < 130:
                cur = dict(number=norm_num(m), title=m.group(4).strip(), chapter=chapter,
                           extra=[], _open=True, _x1=r["x1"])
                entries.append(cur)
                continue
            if cur and r["x0"] >= 100 and not r["italic"] and not r["bold"]:
                # First line after the number is the title. A later line continues the title
                # only if the previous title line ran to the right margin; otherwise it is a
                # marginal sub-heading printed under the entry (kept in `extra`).
                if not cur["title"]:
                    cur["title"], cur["_x1"] = t, r["x1"]
                elif cur["_open"] and cur["_x1"] > WRAP_X1:
                    cur["title"] += " " + t
                    cur["_x1"] = r["x1"]
                else:
                    cur["_open"] = False
                    cur["extra"].append(t)
    for e in entries:
        e.pop("_open", None)
        e.pop("_x1", None)
    return entries, omitted
