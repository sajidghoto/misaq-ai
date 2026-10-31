import pytest

from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.errors import DataValidationError
from misaq.domain.statute import Act, Block, Section
from misaq.validation.processed import require_processed_ok, validate_processed

pytestmark = pytest.mark.unit


def _act(text, status=SectionStatus.IN_FORCE, blocks=True):
    s = Section(act=ActCode.CA1872, number="5", title="t", title_in_body="t", chapter=None, subheading=None,
                status=status, pages=(1,), blocks=(Block(BlockType.BODY, text),) if blocks else ())
    return Act(ActCode.CA1872, "f", "0" * 64, (s,))


def test_clean_text_passes():
    assert validate_processed(_act("A contract is an agreement.")) == []


@pytest.mark.parametrize("bad,why", [
    ("text\n[*\n*]", "artefact"), ("text\nDate: 12-02-2025", "artefact"), ("text\n_____", "artefact"),
    ("a res-\npectively", "hyphen"), ("text\nCHAPTER IV", "chapter"),
])
def test_artefacts_are_caught(bad, why):
    fails = validate_processed(_act(bad))
    assert fails and why in fails[0]


def test_in_force_section_without_text_fails_but_repealed_may_be_empty():
    assert validate_processed(_act("", blocks=False))
    assert validate_processed(_act("", status=SectionStatus.REPEALED, blocks=False)) == []


def test_unresolved_footnote_markers_fail():
    with pytest.raises(DataValidationError) as e:
        require_processed_ok(_act("fine"), unresolved=(("CA1872:s5", 3, "1"),))
    assert "unresolved" in e.value.failures[0]
