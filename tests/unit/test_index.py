import numpy as np
import pytest

from misaq.domain.chunking import ChunkingSpec
from misaq.domain.embedding import EmbeddingModelSpec
from misaq.embedding.fake import FakeEmbedder
from misaq.indexing.index import FaissIndex
from misaq.validation.index import validate_index

pytestmark = pytest.mark.unit


def test_index_build_save_load_and_validate(tmp_path):
    spec = EmbeddingModelSpec("fake", "rev", 8, 32, True, "", "", "mean", False, 2)
    embedder = FakeEmbedder(spec)
    chunks = []
    from misaq.domain.chunking import Chunk
    for i in range(3):
        chunks.append(Chunk(f"A:s{i}#fixed_size-000", f"A:s{i}", "A", str(i), "T", None, None,
                            f"original {i}", f"embedded {i}", (), (), (0,)))
    index = FaissIndex.build(chunks, embedder, ("hash",), ChunkingSpec("fixed_size", 8, 1, "fake"), 2, 3)
    assert validate_index(index) == []
    index.save(tmp_path, {"chunks_per_second": 1.0})
    loaded = FaissIndex.load(tmp_path)
    assert loaded.meta == index.meta
    assert (tmp_path / "build_report.json").exists()
    assert np.array_equal(loaded.search(loaded.vectors, 1)[1][:, 0], np.arange(3))
