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


def _write_processed_fixture(tmp_path, manifest_newline="\n"):
    entries = []
    for code in ActCode:
        name = f"{code.value}.json"
        payload = tmp_path / name
        payload.write_bytes(f'{{"code":"{code.value}"}}\n'.encode("utf-8"))
        entries.append(f"{sha256_file(payload)}  {name}")

    manifest = tmp_path / "SHA256SUMS"
    manifest.write_bytes((manifest_newline.join(entries) + manifest_newline).encode("utf-8"))
    return manifest


def test_check_processed_hashes_accepts_valid_lf_files(tmp_path):
    _write_processed_fixture(tmp_path)

    check_processed_hashes(tmp_path)


def test_check_processed_hashes_accepts_crlf_manifest(tmp_path):
    _write_processed_fixture(tmp_path, manifest_newline="\r\n")

    check_processed_hashes(tmp_path)


def test_check_processed_hashes_rejects_tampered_file(tmp_path):
    _write_processed_fixture(tmp_path)
    payload = tmp_path / "CA1872.json"
    payload.write_bytes(b"tampered")

    with pytest.raises(DataValidationError) as error:
        check_processed_hashes(tmp_path)

    assert error.value.failures == ["CA1872.json"]
    assert "LF line endings and corpus provenance" in str(error.value)


def test_check_processed_hashes_rejects_missing_file(tmp_path):
    _write_processed_fixture(tmp_path)
    missing = tmp_path / "SGA1930.json"
    missing.unlink()

    with pytest.raises(DataValidationError) as error:
        check_processed_hashes(tmp_path)

    assert error.value.failures == ["SGA1930.json"]


@pytest.mark.parametrize(
    "entry",
    [
        "not-a-checksum",
        f"{'0' * 64}  UNKNOWN.json",
        f"{'0' * 64}  CA1872.json\n{'0' * 64}  CA1872.json",
    ],
)
def test_check_processed_hashes_rejects_malformed_or_unexpected_entry(tmp_path, entry):
    manifest = _write_processed_fixture(tmp_path)
    manifest.write_text(entry + "\n", encoding="utf-8")

    with pytest.raises(DataValidationError, match="invalid processed statute checksum manifest"):
        check_processed_hashes(tmp_path)


def test_check_processed_hashes_rejects_incomplete_manifest(tmp_path):
    manifest = _write_processed_fixture(tmp_path)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    manifest.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    with pytest.raises(DataValidationError, match="incomplete processed statute checksum manifest"):
        check_processed_hashes(tmp_path)


def test_check_processed_hashes_rejects_crlf_statute_bytes_without_modifying_inputs(tmp_path):
    _write_processed_fixture(tmp_path)
    payload = tmp_path / "CA1872.json"
    payload.write_bytes(payload.read_bytes().replace(b"\n", b"\r\n"))
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    with pytest.raises(DataValidationError) as error:
        check_processed_hashes(tmp_path)

    after = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    assert error.value.failures == ["CA1872.json"]
    assert after == before
