import dataclasses

import pytest

from misaq.domain.enums import ActCode, BlockType, CitationVerdict, SectionStatus, SystemId
from misaq.domain.errors import AuthError, BackendError, DataValidationError, MisaqError, RateLimitError
from misaq.domain.manifest import DataFingerprint, RunManifest, StageRecord
from misaq.domain.statute import Act, Block, Footnote, FootnoteRef, OmittedRange, Section

pytestmark = pytest.mark.contract


def make_section(**kw):
    base = dict(act=ActCode.CA1872, number="19A", title="T", title_in_body="T", chapter="CHAPTER II",
                subheading=None, status=SectionStatus.IN_FORCE, pages=(18,),
                blocks=(Block(BlockType.BODY, "x"), Block(BlockType.ILLUSTRATION, "(a) y")),
                footnotes=(Footnote(18, "Ins. by x", "1"),), flags=("not_in_contents",),
                footnote_refs=(FootnoteRef(18, "1"),))
    base.update(kw)
    return Section(**base)


def test_section_roundtrip():
    s = make_section()
    assert Section.from_dict(s.to_dict()) == s
    assert s.id == "CA1872:s19A"


def test_act_roundtrip():
    a = Act(ActCode.SRA1877, "f.pdf", "a" * 64, (make_section(act=ActCode.SRA1877),),
            (OmittedRange(45, 51),), notes=(Footnote(5, "Act-level note", "1"),))
    assert Act.from_dict(a.to_dict()) == a


def test_section_is_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        make_section().title = "other"


def test_section_rejects_unnormalized_number():
    with pytest.raises(ValueError):
        make_section(number="27 (A)")


def test_section_requires_a_page():
    with pytest.raises(ValueError):
        make_section(pages=())


def test_act_rejects_duplicate_ids():
    with pytest.raises(ValueError):
        Act(ActCode.CA1872, "f", "0" * 64, (make_section(), make_section()))


def test_from_dict_rejects_wrong_id():
    d = make_section().to_dict()
    d["id"] = "CA1872:s20"
    with pytest.raises(ValueError):
        Section.from_dict(d)


def test_section_json_keys_are_stable():
    assert set(make_section().to_dict()) == {
        "id", "act", "number", "title", "title_in_body", "chapter", "subheading", "status",
        "pages", "blocks", "footnotes", "flags", "footnote_refs"}


def test_enum_values_are_frozen():
    # These strings appear in saved data and run logs. Changing them breaks old runs.
    assert [m.value for m in SectionStatus] == ["unknown", "in_force", "repealed", "omitted"]
    assert [m.value for m in SystemId] == ["S1", "S2", "S3", "S4"]
    assert "out_of_corpus" in [m.value for m in CitationVerdict]


def test_error_hierarchy():
    assert issubclass(RateLimitError, BackendError) and RateLimitError.retryable
    assert not AuthError.retryable
    assert issubclass(DataValidationError, MisaqError)
    assert DataValidationError("x", ["a"]).failures == ["a"]


def test_manifest_serialises():
    m = RunManifest(run_id="r1", kind="parse", created_at="2026-10-30T10:00:00Z", git_commit=None,
                    git_dirty=None, config_hash="h",
                    data=(DataFingerprint("a.pdf", "0" * 64, 10),),
                    stages=(StageRecord("parse", "ok", "t0", "t1", {"sections": 3}),))
    d = m.to_dict()
    assert d["data"][0]["sha256"] == "0" * 64 and d["stages"][0]["counts"] == {"sections": 3}
    assert set(d) >= {"run_id", "kind", "git", "config_hash", "data", "stages", "manifest_version"}


def test_old_section_json_without_new_fields_still_loads():
    d = make_section().to_dict()
    del d["footnote_refs"]
    d["footnotes"] = [{"page": 18, "text": "Ins. by x"}]          # footnote without marker
    s = Section.from_dict(d)
    assert s.footnote_refs == () and s.footnotes[0].marker == ""


def test_act_json_keys_are_stable():
    a = Act(ActCode.CA1872, "f", "0" * 64, (make_section(),))
    assert set(a.to_dict()) == {"schema_version", "code", "source_file", "source_sha256",
                                "omitted_ranges", "notes", "sections"}
