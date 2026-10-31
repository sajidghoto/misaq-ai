import json

import pytest

from misaq.domain.enums import ActCode, BlockType, SectionStatus
from misaq.domain.errors import DataValidationError
from misaq.domain.statute import Act, Block, Section
from misaq.validation.eval_data import validate_eval_jsonl


def _act() -> Act:
    section = Section(
        ActCode.CA1872, "1", "Title", "Title", None, None, SectionStatus.IN_FORCE,
        (1,), (Block(BlockType.BODY, "text"),),
    )
    return Act(ActCode.CA1872, "source", "hash", (section,))


def _write(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_eval_schema_accepts_valid_rows(tmp_path):
    path = tmp_path / "eval.jsonl"
    _write(path, [{
        "id": "q1", "query": "What is a contract?", "gold": ["CA1872:s1"], "split": "dev",
        "related": ["q2"], "query_type": "definition", "source": "human",
        "annotators": ["a1"], "adjudicated": False, "notes": "optional",
    }])
    assert validate_eval_jsonl(path, (_act(),)) == 1


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        ({"id": "q1", "query": "", "gold": ["CA1872:s1"], "split": "dev"}, "non-empty query text"),
        ({"id": "q1", "query": "x", "gold": [], "split": "dev"}, "non-empty gold list"),
        ({"id": "q1", "query": "x", "gold": ["CA1872:9"], "split": "dev"}, "gold section id does not exist"),
    ],
)
def test_eval_schema_reports_exact_failure(tmp_path, row, reason):
    path = tmp_path / "eval.jsonl"
    _write(path, [row])
    with pytest.raises(DataValidationError, match=reason):
        validate_eval_jsonl(path, (_act(),))


def test_eval_schema_rejects_split_overlap_by_normalized_text(tmp_path):
    path = tmp_path / "eval.jsonl"
    _write(path, [
        {"id": "q1", "query": "Same question", "gold": ["CA1872:s1"], "split": "dev"},
        {"id": "q2", "query": " same   question ", "gold": ["CA1872:s1"], "split": "test"},
    ])
    with pytest.raises(DataValidationError, match="normalized query text overlaps"):
        validate_eval_jsonl(path, (_act(),))
