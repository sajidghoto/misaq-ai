from __future__ import annotations

import io
import zipfile
from collections import defaultdict
from xml.etree import ElementTree as ET

from docx import Document
from docx.document import Document as DocumentType

from misaq.contracts import Paragraph
from misaq.domain.errors import CorruptFileError, EmptyDocumentError

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def read_docx(data: bytes) -> tuple[list[Paragraph], list[str]]:
    warnings: list[str] = []
    try:
        document = Document(io.BytesIO(data))
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        raise CorruptFileError("The document could not be read because it is corrupt.") from error
    numbering = _numbering(archive)
    counters: dict[tuple[int, int], int] = defaultdict(int)
    result: list[Paragraph] = []
    document_xml = archive.read("word/document.xml")
    tracked = b"<w:ins" in document_xml or b"<w:del" in document_xml
    for element in document.element.body:
        if element.tag == W + "p":
            text, saw_tracking = _paragraph_text(element)
            tracked |= saw_tracking
            if not text.strip():
                continue
            style = _style_name(element, document)
            label = _label(element, numbering, counters)
            result.append(Paragraph(
                len(result), text, None, None, _bold_ratio(element), _caps_ratio(text),
                0.0, style, label, False, bool(style and "heading" in style.lower()),
            ))
        elif element.tag == W + "tbl":
            for cell_paragraph in element.iter(W + "p"):
                text, saw_tracking = _paragraph_text(cell_paragraph)
                tracked |= saw_tracking
                if text.strip():
                    result.append(Paragraph(
                        len(result), text, None, None, _bold_ratio(cell_paragraph),
                        _caps_ratio(text), 0.0, _style_name_xml(cell_paragraph), "",
                        True, False,
                    ))
    if tracked:
        warnings.append("Tracked changes detected; final text kept insertions and dropped deletions.")
    if any(name.startswith(("word/header", "word/footer", "word/comments")) for name in archive.namelist()):
        warnings.append("Headers, footers, comments, and text boxes are ignored.")
    if b"w:txbxContent" in archive.read("word/document.xml"):
        warnings.append("Headers, footers, comments, and text boxes are ignored.")
    if not result:
        raise EmptyDocumentError("The document is empty or contains no selectable text.")
    return result, warnings


def _paragraph_text(element: ET.Element) -> tuple[str, bool]:
    parts: list[str] = []
    tracked = False
    for child in element.iter():
        if child.tag in {W + "ins", W + "del"}:
            tracked = True
        if child.tag == W + "del":
            continue
        if child.tag == W + "t" and child.text:
            parts.append(child.text)
        elif child.tag == W + "tab":
            parts.append("\t")
        elif child.tag == W + "br":
            parts.append("\n")
    return "".join(parts), tracked


def _style_name(element: ET.Element, document: DocumentType) -> str | None:
    style = element.find("./w:pPr/w:pStyle", NS)
    style_id = style.get(W + "val") if style is not None else None
    if not style_id:
        return None
    for style in document.styles:
        if style.style_id == style_id:
            return style.name
    return style_id


def _style_name_xml(element: ET.Element) -> str | None:
    style = element.find("./w:pPr/w:pStyle", NS)
    return style.get(W + "val") if style is not None else None


def _bold_ratio(element: ET.Element) -> float:
    runs = [run for run in element.iter(W + "r") if run.find(W + "t") is not None]
    bold = sum(1 for run in runs if run.find("./w:rPr/w:b", NS) is not None)
    return bold / len(runs) if runs else 0.0


def _caps_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    return sum(char.isupper() for char in letters) / len(letters) if letters else 0.0


def _numbering(archive: zipfile.ZipFile) -> dict[int, dict[int, dict[str, str]]]:
    try:
        root = ET.fromstring(archive.read("word/numbering.xml"))
    except KeyError:
        return {}
    abstract: dict[int, dict[int, dict[str, str]]] = {}
    for item in root.findall(W + "abstractNum"):
        aid = int(item.get(W + "abstractNumId", "0"))
        abstract[aid] = {}
        for level in item.findall(W + "lvl"):
            ilvl = int(level.get(W + "ilvl", "0"))
            abstract[aid][ilvl] = {
                "fmt": _attribute_value(level, "numFmt", "decimal"),
                "text": _attribute_value(level, "lvlText", ""),
                "start": _attribute_value(level, "start", "1"),
            }
    result: dict[int, dict[int, dict[str, str]]] = {}
    for item in root.findall(W + "num"):
        num_id = int(item.get(W + "numId", "0"))
        abstract_id = item.find(W + "abstractNumId", NS)
        if abstract_id is not None:
            result[num_id] = abstract.get(int(abstract_id.get(W + "val", "0")), {})
    return result


def _label(element: ET.Element, numbering: dict[int, dict[int, dict[str, str]]],
           counters: dict[tuple[int, int], int]) -> str:
    numpr = element.find("./w:pPr/w:numPr", NS)
    if numpr is None:
        return ""
    num_element = numpr.find(W + "numId", NS)
    level_element = numpr.find(W + "ilvl", NS)
    num_id = int(num_element.get(W + "val", "0") if num_element is not None else "0")
    ilvl = int(level_element.get(W + "val", "0") if level_element is not None else "0")
    levels = numbering.get(num_id, {})
    spec = levels.get(ilvl)
    if spec is None:
        spec = {"fmt": "decimal", "text": "%{}.".format(ilvl + 1), "start": "1"}
        levels[ilvl] = spec
    for key in list(counters):
        if key[0] == num_id and key[1] > ilvl:
            counters.pop(key)
    if (num_id, ilvl) not in counters:
        counters[(num_id, ilvl)] = int(spec.get("start", "1")) - 1
    counters[(num_id, ilvl)] += 1
    values = [counters.get((num_id, level), 1) for level in range(ilvl + 1)]
    label = spec["text"] or "%{}".format(ilvl + 1)
    for level, value in enumerate(values, 1):
        label = label.replace("%" + str(level), _format_number(value, levels.get(level - 1, {}).get("fmt", "decimal")))
    return label


def _attribute_value(parent: ET.Element, name: str, default: str) -> str:
    child = parent.find(W + name)
    return child.get(W + "val", default) if child is not None else default


def _format_number(value: int, fmt: str) -> str:
    if fmt == "lowerLetter":
        return chr(96 + value)
    if fmt == "upperLetter":
        return chr(64 + value)
    if fmt == "lowerRoman":
        return _roman(value).lower()
    if fmt == "upperRoman":
        return _roman(value)
    if fmt == "bullet":
        return "•"
    return str(value)


def _roman(value: int) -> str:
    result = ""
    for number, token in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
                          (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
                          (5, "V"), (4, "IV"), (1, "I")):
        while value >= number:
            result += token
            value -= number
    return result
