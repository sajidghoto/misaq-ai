import io

from docx import Document
from hypothesis import given
from hypothesis import strategies as st

from misaq.contracts import Paragraph
from misaq.ingestion.readers import read_docx
from misaq.ingestion.structure import ContractNode, build_structure


def paragraphs(*texts: str) -> list[Paragraph]:
    return [Paragraph(index, text, None) for index, text in enumerate(texts)]


def all_nodes(node: ContractNode) -> list[ContractNode]:
    return [node, *[child_node for child in node.children for child_node in all_nodes(child)]]


def test_decimal_alpha_and_roman_hierarchy():
    result = build_structure(paragraphs(
        "1. General", "The Client shall pay.", "1.1 Payment", "The fee is due.",
        "1.1(a) Timing", "Payment is due monthly.", "1.1(a)(i) Date", "On the first day.",
    ))
    nodes = all_nodes(result)
    assert [node.path for node in nodes] == ["root", "1", "1.1", "1.1(a)", "1.1(a)(i)"]
    assert result.children[0].body_indexes == (0, 1)
    assert next(node for node in nodes if node.path == "1.1(a)(i)").body_indexes == (6, 7)


def test_named_labels_and_mixed_sequence():
    result = build_structure(paragraphs(
        "Article 1 General", "1. Services", "5.2(a)(ii) Payment", "The Client shall pay.",
        "Schedule 2 Deliverables",
    ))
    labels = [node.label for node in all_nodes(result) if node.label]
    assert labels == ["Article 1", "1", "5.2(a)(ii)", "Schedule 2"]


def test_docx_heading_style_is_a_heading():
    document = Document()
    document.add_heading("Definitions", level=1)
    document.add_paragraph("Client means the purchaser.")
    stream = io.BytesIO()
    document.save(stream)
    source, _ = read_docx(stream.getvalue())
    result = build_structure(source)
    assert result.children[0].heading == "Definitions"
    assert result.children[0].kind == "definitions"


def test_title_parties_definitions_and_boilerplate_classification():
    result = build_structure([
        Paragraph(0, "SERVICE AGREEMENT", None, caps_ratio=1.0),
        Paragraph(1, "PARTIES", None, caps_ratio=1.0),
        Paragraph(2, "DEFINITIONS", None, caps_ratio=1.0),
        Paragraph(3, "Client means the purchaser.", None),
        Paragraph(4, "BOILERPLATE", None, caps_ratio=1.0),
        Paragraph(5, "Miscellaneous provisions.", None),
    ])
    kinds = [node.kind for node in all_nodes(result)]
    assert "title" in kinds
    assert "parties" in kinds
    assert "definitions" in kinds
    assert "boilerplate" in kinds


def test_ambiguous_label_and_orphan_text_warn():
    result = build_structure(paragraphs(
        "Unattached text before numbering.", "(i) Item", "1. First clause",
    ))
    warnings = [warning.lower() for node in all_nodes(result) for warning in node.warnings]
    assert any("ambiguous" in warning for warning in warnings)
    assert any("orphan" in warning for warning in warnings)


def test_no_empty_nodes_and_flat_unnumbered_fallback():
    result = build_structure(paragraphs("First paragraph.", "Second paragraph.", "Third paragraph."))
    assert result.low_confidence
    assert result.body_indexes == (0, 1, 2)
    assert all(node.body_indexes or node.children for node in all_nodes(result))


def test_roman_after_alpha_is_alpha_but_list_start_is_roman():
    result = build_structure(paragraphs(
        "5. Terms", "(h) Earlier.", "(i) Next alpha.", "6. End",
    ))
    assert [node.label for node in result.children[0].children] == ["(h)", "(i)"]
    roman = build_structure(paragraphs("Definitions", "(i) First item.", "(ii) Second item."))
    assert [node.scheme for node in all_nodes(roman) if node.label] == ["roman", "roman"]


def test_false_labels_are_body_text_and_cross_reference_is_not_a_label():
    result = build_structure(paragraphs(
        "30 days after notice the term begins.", "Section 5.2 shall apply to all parties.",
    ))
    assert result.children == ()
    assert result.body_indexes == (0, 1)


def test_headings_run_in_headings_and_unumbered_fallback():
    result = build_structure([
        Paragraph(0, "PAYMENT TERMS", None, caps_ratio=1.0),
        Paragraph(1, "Payment. The Client shall pay within 30 days.", None, bold_ratio=1.0),
        Paragraph(2, "The Client must keep records.", None),
    ])
    assert result.low_confidence
    assert [node.heading for node in result.children] == ["PAYMENT TERMS", "Payment"]
    assert result.children[1].body_indexes == (1, 2)


def test_classification_recitals_signature_and_schedule():
    result = build_structure(paragraphs(
        "WHEREAS the parties agree.", "1. Services", "The Provider shall perform.",
        "SIGNED by the parties.", "SCHEDULE 1", "The schedule applies.",
    ))
    kinds = [node.kind for node in all_nodes(result)]
    assert "preamble" in kinds
    assert "operative_clause" in kinds
    assert "signature_block" in kinds
    assert "schedule" in kinds


def test_coverage_order_and_determinism():
    items = paragraphs("1. One", "body", "2. Two", "body two", "loose")
    first = build_structure(items)
    second = build_structure(items)
    nodes = all_nodes(first)
    indexes = [index for node in nodes for index in node.body_indexes]
    assert indexes == list(range(len(items)))
    assert len(indexes) == len(set(indexes))
    assert first == second


def test_numbering_gap_and_restart_are_reported():
    gap = build_structure(paragraphs("1. One", "3. Three"))
    restart = build_structure(paragraphs("1. One", "2. Two", "1. Restart"))
    assert any("gap" in warning.lower() for warning in gap.children[-1].warnings)
    assert any("restart" in warning.lower() for warning in restart.children[-1].warnings)


@given(st.lists(st.text(min_size=0, max_size=80), max_size=30))
def test_arbitrary_paragraphs_do_not_crash(texts: list[str]):
    result = build_structure([Paragraph(index, text, None) for index, text in enumerate(texts)])
    indexes = [index for node in all_nodes(result) for index in node.body_indexes]
    assert indexes == list(range(len(texts)))
