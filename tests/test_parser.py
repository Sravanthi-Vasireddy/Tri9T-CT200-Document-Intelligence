import os
import pytest
from app.parser import CT200PDFParser
from app.validator import DocumentTreeValidator
from app.schemas import NodeType, DocumentNode


@pytest.fixture(scope="module")
def parsed_trees():
    parser = CT200PDFParser()
    t1 = parser.parse("data/ct200_manual.pdf", "v1")
    t2 = parser.parse("data/ct200_manual_v2.pdf", "v2")
    return {"v1": t1, "v2": t2}


def test_out_of_order_sections(parsed_trees):
    """
    Test 1: Section 3.4 appears before Section 3.3 in reading flow,
    yet both retain correct canonical parent (Section 3).
    """
    t1 = parsed_trees["v1"]
    sec_3_4 = t1.nodes.get("v1_sec_3_4")
    sec_3_3 = t1.nodes.get("v1_sec_3_3")
    sec_3 = t1.nodes.get("v1_sec_3")

    assert sec_3_4 is not None, "Section 3.4 node must exist"
    assert sec_3_3 is not None, "Section 3.3 node must exist"
    assert sec_3 is not None, "Section 3 parent node must exist"

    # Both must be children of Section 3
    assert sec_3_4.parent_id == "v1_sec_3"
    assert sec_3_3.parent_id == "v1_sec_3"

    # In Section 3's children list and physical reading order, 3.4 appears BEFORE 3.3
    assert sec_3_4.reading_order_index < sec_3_3.reading_order_index
    idx_3_4 = sec_3.children_ids.index("v1_sec_3_4")
    idx_3_3 = sec_3.children_ids.index("v1_sec_3_3")
    assert idx_3_4 < idx_3_3, "Section 3.4 must precede Section 3.3 in Section 3's children"


def test_missing_intermediate_subsection_numbering(parsed_trees):
    """
    Test 2: Section 2.1.1.1 exists without an obvious Section 2.1.1 heading.
    Parser attaches 2.1.1.1 directly to Section 2.1 without fabricating missing content.
    """
    t1 = parsed_trees["v1"]
    sec_2_1_1_1 = t1.nodes.get("v1_sec_2_1_1_1")
    sec_2_1 = t1.nodes.get("v1_sec_2_1")

    assert sec_2_1_1_1 is not None, "Section 2.1.1.1 must exist"
    assert sec_2_1 is not None, "Section 2.1 must exist"

    # Attached directly to 2.1
    assert sec_2_1_1_1.parent_id == "v1_sec_2_1"
    assert "v1_sec_2_1_1_1" in sec_2_1.children_ids

    # Missing intermediate parent must NOT be invented
    assert "v1_sec_2_1_1" not in t1.nodes, "Parser must not invent missing Section 2.1.1 node"
    assert sec_2_1_1_1.metadata.get("missing_intermediate_parent") == "2.1.1"


def test_duplicate_headings_with_distinct_node_ids(parsed_trees):
    """
    Test 3: Sections 4.2 and 7.1 both carry title text 'Error Codes'.
    They must produce distinct node IDs and retain the correct respective parents.
    """
    t1 = parsed_trees["v1"]
    sec_4_2 = t1.nodes.get("v1_sec_4_2")
    sec_7_1 = t1.nodes.get("v1_sec_7_1")

    assert sec_4_2 is not None, "Section 4.2 must exist"
    assert sec_7_1 is not None, "Section 7.1 must exist"

    # Distinct IDs and distinct logical keys
    assert sec_4_2.id != sec_7_1.id
    assert sec_4_2.logical_key == "sec_4.2"
    assert sec_7_1.logical_key == "sec_7.1"

    # Retain correct respective parents (Section 4 vs Section 7)
    assert sec_4_2.parent_id == "v1_sec_4"
    assert sec_7_1.parent_id == "v1_sec_7"


def test_table_row_and_column_preservation(parsed_trees):
    """
    Test 4: Tables must not be flattened into plain text.
    Row and column structures for specifications (2.1) and error codes (4.2) must be preserved.
    """
    t1 = parsed_trees["v1"]
    t2 = parsed_trees["v2"]

    # 1. Check Section 2.1 General Specifications table
    tbl_2_1 = t1.nodes.get("v1_sec_2_1_tbl_1")
    assert tbl_2_1 is not None, "Section 2.1 table must exist"
    assert tbl_2_1.node_type == NodeType.TABLE
    data_2_1 = tbl_2_1.metadata["table_data"]
    assert data_2_1["headers"] == ["Parameter", "Value"]
    assert data_2_1["row_count"] == 7
    assert data_2_1["col_count"] == 2
    # Verify exact cell pairs
    row_dict = {r[0]: r[1] for r in data_2_1["rows"]}
    assert row_dict["Measurement method"] == "Oscillometric"
    assert "0–299 mmHg" in row_dict["Pressure range"]
    assert "±3 mmHg" in row_dict["Accuracy (pressure)"]

    # 2. Check Section 4.2 Error Codes table in V1 (5 error rows)
    tbl_4_2_v1 = t1.nodes.get("v1_sec_4_2_tbl_2")
    assert tbl_4_2_v1 is not None
    data_4_2_v1 = tbl_4_2_v1.metadata["table_data"]
    assert data_4_2_v1["headers"] == ["Code", "Meaning", "Device Behavior"]
    assert data_4_2_v1["row_count"] == 5
    codes_v1 = [r[0] for r in data_4_2_v1["rows"]]
    assert codes_v1 == ["E1", "E2", "E3", "E4", "E5"]

    # 3. Check Section 4.2 Error Codes table in V2 (6 error rows, including E6)
    tbl_4_2_v2 = t2.nodes.get("v2_sec_4_2_tbl_2")
    assert tbl_4_2_v2 is not None
    data_4_2_v2 = tbl_4_2_v2.metadata["table_data"]
    assert data_4_2_v2["row_count"] == 6
    codes_v2 = [r[0] for r in data_4_2_v2["rows"]]
    assert codes_v2 == ["E1", "E2", "E3", "E4", "E5", "E6"]
    e6_row = next(r for r in data_4_2_v2["rows"] if r[0] == "E6")
    assert "Bluetooth sync failure" in e6_row[1]


def test_content_hash_changes_on_meaningful_diff(parsed_trees):
    """
    Test 5: Content hashes must change when meaningful body text or tables change,
    and remain identical when section content is unchanged.
    """
    t1 = parsed_trees["v1"]
    t2 = parsed_trees["v2"]

    # Unchanged section: Section 1.1 Intended Use
    sec_1_1_v1 = t1.nodes["v1_sec_1_1"]
    sec_1_1_v2 = t2.nodes["v2_sec_1_1"]
    assert sec_1_1_v1.content_hash == sec_1_1_v2.content_hash, "Unchanged section 1.1 must have identical content hash"

    # Modified section: 2.1.1.1 (battery life revised 300 -> 250 cycles, 15% -> 10%)
    sec_2_1_1_1_v1 = t1.nodes["v1_sec_2_1_1_1"]
    sec_2_1_1_1_v2 = t2.nodes["v2_sec_2_1_1_1"]
    assert sec_2_1_1_1_v1.content_hash != sec_2_1_1_1_v2.content_hash, "Section 2.1.1.1 hash must change between V1 and V2"

    # Modified section: 3.2 (inflation increment 40 -> 30 mmHg)
    sec_3_2_v1 = t1.nodes["v1_sec_3_2"]
    sec_3_2_v2 = t2.nodes["v2_sec_3_2"]
    assert sec_3_2_v1.content_hash != sec_3_2_v2.content_hash, "Section 3.2 hash must change between V1 and V2"

    # Modified section: 4.2 (error table E3 2.0s -> 1.5s, E6 added)
    sec_4_2_v1 = t1.nodes["v1_sec_4_2"]
    sec_4_2_v2 = t2.nodes["v2_sec_4_2"]
    assert sec_4_2_v1.content_hash != sec_4_2_v2.content_hash, "Section 4.2 hash must change between V1 and V2"

    # Modified section: 4.3 (alarm thresholds E1-E5 -> E1-E6)
    sec_4_3_v1 = t1.nodes["v1_sec_4_3"]
    sec_4_3_v2 = t2.nodes["v2_sec_4_3"]
    assert sec_4_3_v1.content_hash != sec_4_3_v2.content_hash, "Section 4.3 hash must change between V1 and V2"

    # Added section: Section 5.3 Data Export exists only in V2
    assert "v2_sec_5_3" in t2.nodes, "Section 5.3 must exist in V2"
    assert "v1_sec_5_3" not in t1.nodes, "Section 5.3 must NOT exist in V1"


def test_cross_page_paragraph_continuation(parsed_trees):
    """
    Test 6: Paragraphs split across page boundaries are stitched seamlessly
    into a single node that accurately records page_start and page_end.
    """
    t1 = parsed_trees["v1"]
    t2 = parsed_trees["v2"]

    # V1 Section 3.1 paragraph spans Page 2 and Page 3
    p_3_1 = t1.nodes["v1_sec_3_1_p_7"]
    assert p_3_1.page_start == 2
    assert p_3_1.page_end == 3
    assert "power button for one second" in p_3_1.title_or_text
    assert "select User 1 or User 2" in p_3_1.title_or_text

    # V2 Section 4.3 paragraph spans Page 4 and Page 5
    p_4_3 = t2.nodes["v2_sec_4_3_p_12"]
    assert p_4_3.page_start == 4
    assert p_4_3.page_end == 5
    assert "except for E3 (overpressure)" in p_4_3.title_or_text

    # V2 Section 8.1 paragraph spans Page 6 and Page 7
    p_8_1 = t2.nodes["v2_sec_8_1_p_20"]
    assert p_8_1.page_start == 6
    assert p_8_1.page_end == 7
    assert "Class II medical device" in p_8_1.title_or_text
    assert "validated against relevant clinical accuracy standards" in p_8_1.title_or_text


def test_tree_validation_and_anomaly_detection(parsed_trees):
    """
    Test 7: The DocumentTreeValidator confirms valid trees pass without errors,
    and detects structural anomalies when introduced.
    """
    t1 = parsed_trees["v1"]
    val1 = DocumentTreeValidator.validate(t1)
    assert val1.is_valid, f"V1 tree validation failed: {val1.errors}"
    assert len(val1.errors) == 0

    t2 = parsed_trees["v2"]
    val2 = DocumentTreeValidator.validate(t2)
    assert val2.is_valid, f"V2 tree validation failed: {val2.errors}"
    assert len(val2.errors) == 0

    # Test anomaly detection: create an orphan node
    orphan_node = DocumentNode(
        id="v1_orphan",
        logical_key="orphan",
        node_type=NodeType.PARAGRAPH,
        title_or_text="Orphan text",
        hierarchy_level=2,
        parent_id="non_existent_parent",
        page_start=1,
        page_end=1,
        reading_order_index=999,
        content_hash="abc"
    )
    t1.nodes["v1_orphan"] = orphan_node
    val_orphan = DocumentTreeValidator.validate(t1)
    assert not val_orphan.is_valid
    assert any("non_existent_parent" in err for err in val_orphan.errors)

    # Clean up test node
    del t1.nodes["v1_orphan"]
