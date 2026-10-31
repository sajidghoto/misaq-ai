import pytest

from misaq.domain.chunking import Chunk, ChunkingSpec
from misaq.domain.embedding import EmbeddingModelSpec
from misaq.domain.index import IndexMeta

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def test_step4_contracts_roundtrip():
    chunking = ChunkingSpec("section_aware", 400, 0, "BAAI/bge-small-en-v1.5")
    model = EmbeddingModelSpec("x", "r", 3, 10, True, "q", "d", "mean", False, 2)
    chunk = Chunk("CA1872:s10#section_aware-000", "CA1872:s10", "CA1872", "10", "Title",
                  "CHAPTER I", None, "original", "header original", ("CHAPTER I", "Title"),
                  (14,), (0,), ({"page": 14, "marker": "1", "text": "note"},))
    meta = IndexMeta("abc", "faiss", ("h",), chunking, model, 1, 2, 3)
    assert Chunk.from_dict(chunk.to_dict()) == chunk
    assert ChunkingSpec.from_dict(chunking.to_dict()) == chunking
    assert EmbeddingModelSpec.from_dict(model.to_dict()) == model
    assert IndexMeta.from_dict(meta.to_dict()) == meta


def test_step4_contracts_reject_non_cpu_and_invalid_limits():
    with pytest.raises(ValueError):
        EmbeddingModelSpec("x", "r", 3, 10, True, "", "", "mean", False, 1, "cuda")
    with pytest.raises(ValueError):
        ChunkingSpec("fixed_size", 10, 10, "tok")
