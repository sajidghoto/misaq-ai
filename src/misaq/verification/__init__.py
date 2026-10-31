"""Citation extraction, normalization, and frozen-corpus verification."""

from misaq.verification.extract import extract_citations
from misaq.verification.registry import CorpusRegistry
from misaq.verification.verify import verify_citation

__all__ = ["CorpusRegistry", "extract_citations", "verify_citation"]
