from misaq.contracts import Paragraph
from misaq.domain.errors import (
    CorruptFileError,
    EmptyDocumentError,
    EncryptedDocumentError,
    ScannedDocumentError,
    UnsupportedFileError,
)

from .docx import read_docx
from .normalise import READER_VERSION, normalise, reader_fingerprint
from .pdf import read_pdf


def read_bytes(data: bytes, filename: str) -> tuple[list[Paragraph], list[str]]:
    """Read a PDF or DOCX from memory, returning paragraphs and non-text warnings."""
    if not data:
        raise UnsupportedFileError("Unsupported file type. Upload a PDF or DOCX.")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    is_pdf = data.startswith(b"%PDF-")
    is_docx = data.startswith(b"PK\x03\x04") and _looks_like_docx(data)
    if suffix not in {"pdf", "docx"}:
        raise UnsupportedFileError("Unsupported file type. Upload a PDF or DOCX.")
    if suffix == "pdf" and is_docx or suffix == "docx" and is_pdf:
        raise UnsupportedFileError("Unsupported file type. Upload a PDF or DOCX.")
    if is_pdf:
        return read_pdf(data)
    if is_docx:
        return read_docx(data)
    if suffix == "pdf":
        return read_pdf(data)
    raise UnsupportedFileError("Unsupported file type. Upload a PDF or DOCX.")


def _looks_like_docx(data: bytes) -> bool:
    return b"word/document.xml" in data


__all__ = [
    "READER_VERSION",
    "normalise",
    "reader_fingerprint",
    "read_bytes",
    "read_docx",
    "read_pdf",
    "CorruptFileError",
    "EmptyDocumentError",
    "EncryptedDocumentError",
    "ScannedDocumentError",
    "UnsupportedFileError",
]
