import json

from misaq.domain.manifest import RunManifest


def test_manifest_roundtrip_and_schema_stability():
    manifest = RunManifest("r", "experiment", "t", None, None, "h")
    loaded = RunManifest.from_dict(manifest.to_dict())
    assert loaded == manifest
    assert list(manifest.to_dict()) == [
        "manifest_version", "run_id", "kind", "created_at", "git", "config_hash",
        "data", "params", "models", "seed", "env", "stages", "outputs", "status"]
    assert json.loads(json.dumps(manifest.to_dict())) == manifest.to_dict()
