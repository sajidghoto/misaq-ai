from misaq.experiments.fingerprint import environment_fingerprint


def test_environment_ram_bytes_is_an_integer():
    assert isinstance(environment_fingerprint()["ram_bytes"], int)
