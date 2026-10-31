import pytest

from misaq.domain.enums import ActCode
from misaq.domain.errors import DataValidationError
from misaq.validation.statutes import build_report, check_processed_hashes, require_ok, sha256_file

pytestmark = pytest.mark.unit


def _raw(number, title="Title"):
    return {"number": number, "title_body": title, "blocks": [{"type": "body", "text": "text"}]}


def test_build_report_rejects_duplicate_contents_numbers():
    report = build_report(
        ActCode.CA1872,
        [{"number": "1", "title": "Title"}, {"number": "1", "title": "Title"}],
        [_raw("1")],
        [],
        [],
        [],
    )

    assert "duplicate numbers in contents" in report.failures


def test_require_ok_reports_unexplained_sequence_gaps():
    report = build_report(
        ActCode.CA1872,
        [{"number": "1", "title": "Title"}, {"number": "3", "title": "Title"}],
        [_raw("1"), _raw("3")],
        [],
        [],
        [],
    )

    with pytest.raises(DataValidationError) as error:
        require_ok(report)

    assert "unexplained gap (1, 3)" in error.value.failures


def test_check_processed_hashes_accepts_crlf_manifest(tmp_path):
    payload = tmp_path / "CA1872.json"
    payload.write_bytes(b"frozen")
    manifest = tmp_path / "SHA256SUMS"
    manifest.write_text(f"{sha256_file(payload)}  CA1872.json\r\n", encoding="utf-8", newline="")

    check_processed_hashes(tmp_path)


def test_check_processed_hashes_rejects_tampered_file(tmp_path):
    payload = tmp_path / "CA1872.json"
    payload.write_bytes(b"frozen")
    (tmp_path / "SHA256SUMS").write_text(
        f"{sha256_file(payload)}  CA1872.json\n",
        encoding="utf-8",
    )
    payload.write_bytes(b"tampered")

    with pytest.raises(DataValidationError) as error:
        check_processed_hashes(tmp_path)

    assert error.value.failures == ["CA1872.json"]
