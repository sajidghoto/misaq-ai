"""Stable identifiers. A section id is ``<ActCode>:s<number>``, e.g. ``CA1872:s19A``."""
import re

_NUM = re.compile(r"^(\d+)\s*(?:\(\s*([A-Za-z])\s*\))?([A-Za-z])?$")
_SID = re.compile(r"^([A-Z]+\d{4}):s(\d+[A-Z]?)$")


def normalize_number(raw: str) -> str:
    """'27 (A)' -> '27A', '16a' -> '16A', ' 5 ' -> '5'. Raises ValueError otherwise."""
    m = _NUM.match(raw.strip())
    if not m:
        raise ValueError(f"not a section number: {raw!r}")
    return m.group(1) + (m.group(2) or m.group(3) or "").upper()


def number_sort_key(number: str) -> tuple[int, str]:
    m = _NUM.match(number)
    if not m:
        raise ValueError(f"not a section number: {number!r}")
    return int(m.group(1)), (m.group(2) or m.group(3) or "").upper()


def section_id(act: str, number: str) -> str:
    return f"{act}:s{normalize_number(number)}"


def parse_section_id(sid: str) -> tuple[str, str]:
    m = _SID.match(sid)
    if not m:
        raise ValueError(f"not a section id: {sid!r}")
    return m.group(1), m.group(2)


def chunk_id(sid: str, strategy: str, index: int) -> str:
    parse_section_id(sid)
    return f"{sid}#{strategy}-{index:03d}"
