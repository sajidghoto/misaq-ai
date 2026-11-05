import io
from pathlib import Path

from docx import Document

from misaq.ingestion import IngestionConfig, ingest_bytes


def docx_bytes(*texts: str) -> bytes:
    document = Document()
    for text in texts:
        document.add_paragraph(text)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def test_ingest_bytes_returns_provenance_and_no_disk_output(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = ingest_bytes(docx_bytes("1. The Provider shall perform.", "2. The Client must pay."),
                          "public.docx")
    assert result.clauses
    assert all(not clause.cloud_ok for clause in result.clauses)
    assert all(clause.source_pages == () for clause in result.clauses)
    assert "The Provider" not in str(result.report.to_dict())
    assert list(tmp_path.iterdir()) == []


def test_units_warn_instead_of_truncating_unrepresentable_paragraph():
    result = ingest_bytes(
        docx_bytes("1. The Provider shall " + "word " * 80),
        "public.docx",
        {"analysis_units": {"max_unit_tokens": 3, "tiny_unit_tokens": 1}},
    )
    assert result.clauses
    assert any("could not be split" in warning.lower()
               for clause in result.clauses for warning in clause.warnings)


def test_config_object_is_supported():
    result = ingest_bytes(docx_bytes("1. The Provider shall perform."), "x.docx",
                          IngestionConfig(max_unit_tokens=400))
    assert result.report.clause_count == len(result.clauses)
