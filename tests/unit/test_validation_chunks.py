import pytest

from misaq.domain.chunking import Chunk
from misaq.validation.chunks import validate_chunks

pytestmark = pytest.mark.unit


def test_validate_chunks_checks_budget_coverage_and_ids():
    chunk = Chunk("A:s1#section_aware-000", "A:s1", "A", "1", "T", None, None,
                  "x", "x", (), (), (0,))
    assert validate_chunks([chunk], [2], 2, {"A:s1"}) == []
    assert validate_chunks([chunk, chunk], [2, 2], 2, {"A:s1"}) == ["chunk ids are not unique"]
