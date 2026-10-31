import pytest

from misaq.domain.embedding import EmbeddingModelSpec
from misaq.embedding.sentence_transformer import SentenceTransformerEmbedder

pytestmark = pytest.mark.unit


class FakeTokenizer:
    def encode(self, text: str, **kwargs: object) -> list[int]:
        return list(range(len(text.split())))


class FakeModel:
    tokenizer = FakeTokenizer()

    def encode(self, *args: object, **kwargs: object) -> list[list[float]]:
        raise AssertionError("model.encode must not run after an overflow")


def test_model_prefix_overflow_fails_before_embedding():
    embedder = SentenceTransformerEmbedder.__new__(SentenceTransformerEmbedder)
    embedder.spec = EmbeddingModelSpec("fake", "rev", 2, 3, True, "query prefix ", "", "mean", False, 1)
    embedder.model = FakeModel()

    with pytest.raises(ValueError, match="max_seq_length"):
        embedder.encode_queries(["one two"])
