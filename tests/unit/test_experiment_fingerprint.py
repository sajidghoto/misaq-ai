import hashlib
import subprocess
from pathlib import Path

from misaq.experiments.fingerprint import canonical_json, config_sha256, git_info, sha256_file


def test_file_hashes_binary_bytes(tmp_path: Path):
    path = tmp_path / "input.bin"
    path.write_bytes(b"\x00\r\n\xff")
    fingerprint = sha256_file(path)
    assert fingerprint.sha256 == hashlib.sha256(b"\x00\r\n\xff").hexdigest()
    assert fingerprint.bytes == 4


def test_config_hash_ignores_yaml_key_order_and_line_endings(tmp_path: Path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    first.write_bytes(b"b: 2\r\na: 1.5\r\n")
    second.write_bytes(b"a: 1.5\nb: 2\n")
    assert config_sha256(first) == config_sha256(second)
    assert canonical_json({"b": 2, "a": 1.5}) == '{"a":1.5,"b":2}'


def test_git_info_records_unavailable():
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("git")

    assert git_info(runner=unavailable) == {
        "available": False, "commit": None, "branch": None, "dirty": None}


def test_git_info_uses_injected_runner():
    outputs = [subprocess.CompletedProcess([], 0, "abc\n", ""),
               subprocess.CompletedProcess([], 0, "main\n", ""),
               subprocess.CompletedProcess([], 0, " M file\n", "")]

    def runner(*args, **kwargs):
        return outputs.pop(0)

    assert git_info(runner=runner)["dirty"] is True
