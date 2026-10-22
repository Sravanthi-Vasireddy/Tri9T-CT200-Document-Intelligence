import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Document, DocumentVersion, DocumentNodeModel
from app.ingestion import IngestionService
from app.versioning import DocumentVersionMatcher
from app.schemas import DocumentTree, DocumentNode, NodeType, NodeChangeStatus


@pytest.fixture
def test_db():
    """Creates a pristine in-memory SQLite database for test isolation."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_initial_v1_ingestion(test_db):
    """
    Test 1: Ingesting V1 creates Document, DocumentVersion, and all DocumentNodeModel records.
    """
    summary = IngestionService.ingest_pdf(
        pdf_path="data/ct200_manual.pdf",
        version_number="v1",
        document_id="ct200_manual",
        db=test_db
    )

    assert not summary.already_ingested
    assert summary.version_id == "ct200_manual_v1"
    assert summary.total_pages == 6
    assert summary.total_nodes == 50

    # Verify Document in DB
    doc = test_db.query(Document).filter(Document.id == "ct200_manual").first()
    assert doc is not None
    assert len(doc.versions) == 1

    # Verify Version in DB
    version = doc.versions[0]
    assert version.version_number == "v1"
    assert len(version.nodes) == 50

    # Verify root node
    root_node = test_db.query(DocumentNodeModel).filter(DocumentNodeModel.id == "v1_doc").first()
    assert root_node is not None
    assert root_node.parent_id is None
    assert root_node.logical_key == "doc_root"


def test_v2_ingestion_preserves_v1(test_db):
    """
    Test 2: Ingesting V2 must preserve V1 nodes and historical records without overwriting.
    """
    # 1. Ingest V1
    sum1 = IngestionService.ingest_pdf(
        pdf_path="data/ct200_manual.pdf",
        version_number="v1",
        document_id="ct200_manual",
        db=test_db
    )
    assert sum1.total_nodes == 50

    # 2. Ingest V2
    sum2 = IngestionService.ingest_pdf(
        pdf_path="data/ct200_manual_v2.pdf",
        version_number="v2",
        document_id="ct200_manual",
        db=test_db
    )
    assert sum2.total_nodes == 52

    # Verify both versions exist
    doc = test_db.query(Document).filter(Document.id == "ct200_manual").first()
    assert len(doc.versions) == 2
    version_numbers = [v.version_number for v in doc.versions]
    assert "v1" in version_numbers
    assert "v2" in version_numbers

    # Verify V1 nodes remain intact (50 nodes)
    v1_nodes = test_db.query(DocumentNodeModel).filter(DocumentNodeModel.version_id == "ct200_manual_v1").all()
    assert len(v1_nodes) == 50

    # Verify V2 nodes exist separately (52 nodes)
    v2_nodes = test_db.query(DocumentNodeModel).filter(DocumentNodeModel.version_id == "ct200_manual_v2").all()
    assert len(v2_nodes) == 52

    # Total nodes in DB
    total_nodes = test_db.query(DocumentNodeModel).count()
    assert total_nodes == 102


def test_unchanged_node_recognition(test_db):
    """
    Test 3: Unchanged sections between V1 and V2 are recognized as UNCHANGED.
    """
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", db=test_db)
    summary_v2 = IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", db=test_db)

    # At least 35 nodes unchanged
    assert summary_v2.unchanged_nodes >= 35

    diff_map = {m.logical_key: m for m in summary_v2.diff_details}
    # Section 1.1 Intended Use is unchanged
    assert "sec_1.1" in diff_map
    assert diff_map["sec_1.1"].status == NodeChangeStatus.UNCHANGED
    assert diff_map["sec_1.1"].prev_hash == diff_map["sec_1.1"].curr_hash

    # Section 2.1 General Specifications table is unchanged
    assert "sec_2.1_tbl_1" in diff_map
    assert diff_map["sec_2.1_tbl_1"].status == NodeChangeStatus.UNCHANGED


def test_changed_body_text_with_stable_logical_identity(test_db):
    """
    Test 4: Changed sections and body text maintain stable logical keys with status CHANGED.
    """
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", db=test_db)
    summary_v2 = IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", db=test_db)

    diff_map = {m.logical_key: m for m in summary_v2.diff_details}

    # Section 2.1.1.1 (battery life revised 300 -> 250)
    assert "sec_2.1.1.1" in diff_map
    assert diff_map["sec_2.1.1.1"].status == NodeChangeStatus.CHANGED
    assert diff_map["sec_2.1.1.1"].prev_hash != diff_map["sec_2.1.1.1"].curr_hash

    # Verify both version records in DB retain stable logical identity but distinct text
    node_v1 = test_db.query(DocumentNodeModel).filter(DocumentNodeModel.id == "v1_sec_2_1_1_1_p_5").first()
    node_v2 = test_db.query(DocumentNodeModel).filter(DocumentNodeModel.id == "v2_sec_2_1_1_1_p_5").first()
    assert node_v1 is not None and node_v2 is not None
    assert node_v1.logical_key == node_v2.logical_key
    assert "300 measurement cycles" in node_v1.title_or_text
    assert "250 measurement cycles" in node_v2.title_or_text

    # Section 4.2 table (E3 deflates 1.5s, E6 added)
    assert "sec_4.2_tbl_2" in diff_map
    assert diff_map["sec_4.2_tbl_2"].status == NodeChangeStatus.CHANGED


def test_added_and_removed_nodes(test_db):
    """
    Test 5: Newly introduced sections in V2 are classified as ADDED.
    """
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", db=test_db)
    summary_v2 = IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", db=test_db)

    diff_map = {m.logical_key: m for m in summary_v2.diff_details}

    # Section 5.3 Data Export is ADDED
    assert "sec_5.3" in diff_map
    assert diff_map["sec_5.3"].status == NodeChangeStatus.ADDED
    assert diff_map["sec_5.3"].prev_node_id is None
    assert diff_map["sec_5.3"].curr_node_id == "v2_sec_5_3"

    # Paragraph under Section 5.3 is ADDED
    assert "sec_5.3_p_15" in diff_map
    assert diff_map["sec_5.3_p_15"].status == NodeChangeStatus.ADDED

    assert summary_v2.added_nodes == 2
    assert summary_v2.removed_nodes == 0


def test_repeated_headings_and_ambiguous_matches(test_db):
    """
    Test 6: Repeated headings (4.2 Error Codes vs 7.1 Error Codes) are disambiguated by parent,
    and genuinely ambiguous nodes are flagged.
    """
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", db=test_db)
    summary_v2 = IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", db=test_db)

    diff_map = {m.logical_key: m for m in summary_v2.diff_details}

    # Both 4.2 and 7.1 exist with distinct logical keys
    assert "sec_4.2" in diff_map
    assert "sec_7.1" in diff_map

    # 4.2 is modified (error table changed)
    assert diff_map["sec_4.2"].status == NodeChangeStatus.CHANGED

    # 7.1 is unchanged
    assert diff_map["sec_7.1"].status == NodeChangeStatus.UNCHANGED

    assert summary_v2.ambiguous_matches == 0

    # Test synthetic ambiguous matching
    synthetic_prev = {
        "p1": {"id": "p1", "logical_key": "sec_9.9", "node_type": "section", "section_number": "9.9", "parent_id": "root", "content_hash": "a", "title_or_text": "Duplicate"},
        "p2": {"id": "p2", "logical_key": "sec_9.9", "node_type": "section", "section_number": "9.9", "parent_id": "root", "content_hash": "b", "title_or_text": "Duplicate"}
    }

    synthetic_tree = DocumentTree(
        document_id="test",
        version="v2",
        source_file="dummy.pdf",
        title="Test",
        total_pages=1,
        root_node_id="root",
        nodes={
            "root": DocumentNode(id="root", logical_key="doc_root", node_type=NodeType.DOCUMENT, title_or_text="Root", hierarchy_level=0, page_start=1, page_end=1, reading_order_index=0, content_hash="r"),
            "c1": DocumentNode(id="c1", logical_key="sec_9.9", node_type=NodeType.SECTION, title_or_text="Duplicate", section_number="9.9", hierarchy_level=1, parent_id="root", page_start=1, page_end=1, reading_order_index=1, content_hash="c")
        },
        reading_order=["root", "c1"]
    )
    matches, counts = DocumentVersionMatcher.match_versions(synthetic_prev, synthetic_tree)
    assert counts["ambiguous"] == 1
    ambig_match = next(m for m in matches if m.status == NodeChangeStatus.AMBIGUOUS)
    assert ambig_match.logical_key == "sec_9.9"


def test_transaction_rollback_on_invalid_ingestion(test_db):
    """
    Test 7: If ingestion fails midway, transaction is rolled back leaving no orphan rows.
    """
    # Attempting to ingest a non-existent PDF raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        IngestionService.ingest_pdf("data/non_existent.pdf", "v1", db=test_db)

    # Database must remain completely clean
    assert test_db.query(Document).count() == 0
    assert test_db.query(DocumentVersion).count() == 0
    assert test_db.query(DocumentNodeModel).count() == 0


def test_deterministic_behavior_and_file_hash_deduplication(test_db):
    """
    Test 8: Running ingestion twice on the same PDF returns already_ingested=True
    without creating duplicate records in SQLite.
    """
    sum1 = IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", db=test_db)
    assert not sum1.already_ingested
    assert test_db.query(DocumentVersion).count() == 1
    assert test_db.query(DocumentNodeModel).count() == 50

    # Ingest again with same PDF
    sum2 = IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", db=test_db)
    assert sum2.already_ingested
    assert sum2.version_id == sum1.version_id
    assert sum2.file_hash == sum1.file_hash

    # Database still has only 1 version and 50 nodes!
    assert test_db.query(DocumentVersion).count() == 1
    assert test_db.query(DocumentNodeModel).count() == 50
