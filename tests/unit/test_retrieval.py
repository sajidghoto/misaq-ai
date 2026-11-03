import pytest

from misaq.domain.chunking import Chunk, ChunkingSpec
from misaq.domain.embedding import EmbeddingModelSpec
from misaq.domain.retrieval import Query
from misaq.embedding.fake import FakeEmbedder
from misaq.indexing.index import FaissIndex
from misaq.retrieval.metrics import mean_reciprocal_rank, precision_at_k, recall_at_k
from misaq.retrieval.retriever import DenseRetriever


def _index() -> FaissIndex:
    spec = EmbeddingModelSpec("fake", "rev", 4, 32, True, "", "", "mean", False, 2)
    embedder = FakeEmbedder(spec)
    chunks = [
        Chunk("A:1#0", "A:1", "A", "1", "One", None, None, "one", "one", (), (), (0,)),
        Chunk("A:1#1", "A:1", "A", "1", "One", None, None, "one more", "one more", (), (), (1,)),
        Chunk("A:2#0", "A:2", "A", "2", "Two", None, None, "two", "two", (), (), (2,)),
    ]
    return FaissIndex.build(chunks, embedder, ("hash",), ChunkingSpec("fixed_size", 8, 1, "fake"), 0, 0)


def test_dense_retriever_collapses_chunks_to_sections():
    index = _index()
    retriever = DenseRetriever(index, FakeEmbedder(index.meta.model), top_n=3, top_k=2)

    result = retriever.retrieve(Query("q1", "one"))

    assert result.query.id == "q1"
    assert len(result.hits) == 2
    assert len({hit.section_id for hit in result.hits}) == 2
    assert result.hits[0].score >= result.hits[1].score


def test_metrics_deduplicate_retrieved_sections_and_raise_for_empty_gold():
    assert precision_at_k(["s1", "s1", "s2"], {"s1", "s2"}, 3) == pytest.approx(2 / 3)
    assert precision_at_k(["s1"], {"s1"}, 3) == pytest.approx(1 / 3)
    assert recall_at_k(["s1", "s1", "s2"], {"s1", "s2"}, 3) == 1.0
    assert mean_reciprocal_rank(["s3", "s1", "s1"], {"s1"}) == pytest.approx(0.5)
    with pytest.raises(ValueError, match="gold set cannot be empty"):
        recall_at_k([], set(), 1)


def test_query_encoder_receives_query_text():
    class RecordingEmbedder(FakeEmbedder):
        def encode_queries(self, texts):
            self.seen = list(texts)
            return super().encode_queries(texts)

    embedder = RecordingEmbedder(_index().meta.model)
    DenseRetriever(_index(), embedder).retrieve(Query("q", "contract text"))
    assert embedder.seen == ["contract text"]


def test_top_n_controls_chunks_retrieved_before_collapse():
    class RecordingIndex:
        chunks = _index().chunks

        def search(self, queries, k):
            self.k = k
            return _index().search(queries, k)

    index = RecordingIndex()
    DenseRetriever(index, FakeEmbedder(_index().meta.model), top_n=2).retrieve(Query("q", "one"))
    assert index.k == 2


def test_retrieve_demo_prints_top_sections(capsys):
    import importlib.util
    from pathlib import Path

    script = Path(__file__).parents[2] / "scripts" / "07_retrieve_demo.py"
    spec = importlib.util.spec_from_file_location("retrieve_demo", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.print_results(
        DenseRetriever(_index(), FakeEmbedder(_index().meta.model), top_n=3, top_k=1),
        "one",
        1,
    )
    output = capsys.readouterr().out
    assert "Act: A | Section: 1 | Title: One | Score:" in output
    assert output.count("\n") == 1
