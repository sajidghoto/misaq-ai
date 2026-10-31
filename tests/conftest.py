import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/statutes"
FILES = {"CA1872": "PK-CA1872_source.pdf", "SGA1930": "PK-SGA1930_service.pdf",
         "SRA1877": "PK-SRA1877_Source.pdf"}


@pytest.fixture(scope="session")
def pipeline():
    """Run parse + process on the real PDFs once per session: {code: (act, parse_report, process_report)}."""
    if not all((RAW / f).exists() for f in FILES.values()):
        pytest.skip("statute PDFs not in data/raw/statutes")
    from misaq.domain.enums import ActCode
    from misaq.parsing.pipeline import parse_act
    from misaq.processing.pipeline import process_acts
    raw, reports = {}, {}
    for code, name in FILES.items():
        act, report = parse_act(RAW / name, ActCode(code))
        raw[ActCode(code)], reports[code] = act, report
    return {c.value: (act, reports[c.value], prep) for c, (act, prep) in process_acts(raw).items()}


@pytest.fixture(scope="session")
def parsed(pipeline):
    """{code: (processed act, parse report)}"""
    return {c: (a, pr) for c, (a, pr, _) in pipeline.items()}


@pytest.fixture(scope="session")
def golden():
    return json.loads((Path(__file__).parent / "golden/fixtures/sections.json").read_text(encoding="utf-8"))
