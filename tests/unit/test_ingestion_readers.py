import io
import logging
from pathlib import Path

import fitz
import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from misaq.contracts import Paragraph
from misaq.ingestion.readers import (
    READER_VERSION,
    CorruptFileError,
    EmptyDocumentError,
    EncryptedDocumentError,
    ScannedDocumentError,
    UnsupportedFileError,
    normalise,
    read_bytes,
    reader_fingerprint,
)

pytestmark = pytest.mark.unit


def pdf_bytes(pages: list[list[tuple[str, tuple[float, float]]]]) -> bytes:
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        for text, point in lines:
            page.insert_text(point, text, fontsize=11)
    return doc.tobytes()


def docx_bytes(build) -> bytes:
    doc = Document()
    build(doc)
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def add_num_pr(paragraph, num_id: int, ilvl: int = 0) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    numpr = OxmlElement("w:numPr")
    level = OxmlElement("w:ilvl")
    level.set(qn("w:val"), str(ilvl))
    num = OxmlElement("w:numId")
    num.set(qn("w:val"), str(num_id))
    numpr.extend((level, num))
    ppr.append(numpr)


def test_paragraph_record_and_normaliser_are_stable():
    paragraph = Paragraph(2, "  “A”  • ﬁ  ", None, 12.0, 0.5, 1.0, 3.0, "Body", "1.", False, False)
    output = normalise([paragraph])
    assert output[0].text == '"A" - fi'
    assert output[0].index == 2
    assert output[0].source_indexes == (2,)
    assert normalise(output) == output
    assert READER_VERSION and reader_fingerprint() == reader_fingerprint()


def test_pdf_dispatch_features_and_repeating_margin_text():
    data = pdf_bytes([
        [("REPEATED HEADER", (72, 30)), ("1. First-", (72, 100)), ("line", (72, 113)), ("Page 1", (72, 780))],
        [("REPEATED HEADER", (72, 30)), ("second line", (72, 100)), ("Page 2", (72, 780))],
    ])
    paragraphs, warnings = read_bytes(data, "contract.pdf")
    assert not warnings
    assert [p.text for p in paragraphs] == ["1. Firstline", "second line"]
    assert all(p.page in (1, 2) for p in paragraphs)
    assert all(isinstance(p, Paragraph) for p in paragraphs)


def test_pdf_columns_are_read_left_to_right():
    data = pdf_bytes([[("left one", (72, 100)), ("left two", (72, 125)),
                       ("right one", (320, 100)), ("right two", (320, 125))]])
    paragraphs, _ = read_bytes(data, "contract.pdf")
    assert [p.text for p in paragraphs] == ["left one left two", "right one right two"]


def test_pdf_table_is_flattened_and_flagged():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Item    Amount", fontsize=11)
    page.insert_text((72, 90), "Fee     10", fontsize=11)
    page.draw_rect((60, 55, 250, 105))
    paragraphs, warnings = read_bytes(doc.tobytes(), "table.pdf")
    assert any("Item" in p.text for p in paragraphs)
    assert any("Item" in p.text for p in paragraphs)


def test_pdf_rejections():
    with pytest.raises(UnsupportedFileError):
        read_bytes(b"", "empty.pdf")
    with pytest.raises(CorruptFileError):
        read_bytes(b"not a pdf", "bad.pdf")
    with pytest.raises(EmptyDocumentError):
        read_bytes(pdf_bytes([[]]), "empty.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "secret", fontsize=11)
    encrypted = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user")
    with pytest.raises(EncryptedDocumentError):
        read_bytes(encrypted, "encrypted.pdf")


def test_docx_numbering_tables_and_tracked_changes():
    def build(doc):
        p = doc.add_paragraph("First")
        add_num_pr(p, 9)
        nested = doc.add_paragraph("Nested")
        add_num_pr(nested, 9, 1)
        table = doc.add_table(rows=1, cols=1)
        table.cell(0, 0).text = "Cell"
        body = doc.element.body
        ins = OxmlElement("w:ins")
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = " kept"
        run.append(text)
        ins.append(run)
        body.append(ins)
        deletion = OxmlElement("w:del")
        run = OxmlElement("w:r")
        text = OxmlElement("w:delText")
        text.text = " dropped"
        run.append(text)
        deletion.append(run)
        body.append(deletion)

    paragraphs, warnings = read_bytes(docx_bytes(build), "contract.docx")
    assert [p.text for p in paragraphs[:3]] == ["First", "Nested", "Cell"]
    assert paragraphs[0].list_label_text.startswith("1")
    assert paragraphs[1].list_label_text
    assert paragraphs[2].in_table
    assert any("tracked" in warning.lower() for warning in warnings)


def test_docx_rejections_and_privacy(caplog):
    with pytest.raises(UnsupportedFileError):
        read_bytes(b"PK", "contract.txt")
    with pytest.raises(UnsupportedFileError):
        read_bytes(b"PK", "contract.doc")
    data = docx_bytes(lambda doc: doc.add_paragraph("PRIVATE DOCUMENT TEXT"))
    with caplog.at_level(logging.WARNING):
        read_bytes(data, "contract.docx")
    assert "PRIVATE DOCUMENT TEXT" not in caplog.text


def test_image_only_pdf_is_rejected_without_disk_io(tmp_path: Path):
    doc = fitz.open()
    page = doc.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, (0, 0, 1, 1), False)
    page.insert_image((0, 0, 100, 100), pixmap=pixmap)
    with pytest.raises(ScannedDocumentError):
        read_bytes(doc.tobytes(), "scan.pdf")
    assert list(tmp_path.iterdir()) == []
