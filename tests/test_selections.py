import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
import app.models
from app.models import Document, DocumentVersion, DocumentNodeModel, Selection, SelectionItem
from app.ingestion import IngestionService
from app.main import app


@pytest.fixture(scope="module")
def api_client():
    """
    Sets up an isolated in-memory SQLite database pre-populated with V1 and V2,
    and configures FastAPI dependency overrides for pristine test isolation.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Ingest V1 and V2
    init_session = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", document_id="ct200_manual", db=init_session)
    IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", document_id="ct200_manual", db=init_session)
    init_session.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


def test_create_and_retrieve_selection(api_client):
    """
    Test 1: Creating a named selection returns 201 Created with full metadata,
    and retrieving it via GET returns the exact persisted selection.
    """
    payload = {
        "name": "General Specifications Test Suite",
        "description": "Functional tests for hardware specifications and measurement parameters",
        "items": [
            {"node_id": "v1_sec_2_1"},
            {"node_id": "v1_sec_2_1_tbl_1"}
        ]
    }
    resp = api_client.post("/api/selections", json=payload)
    assert resp.status_code == 201
    created = resp.json()

    assert created["id"].startswith("sel_")
    assert created["name"] == "General Specifications Test Suite"
    assert created["description"] == "Functional tests for hardware specifications and measurement parameters"
    assert created["document_id"] == "ct200_manual"
    assert created["version_number"] == "v1"
    assert created["total_items"] == 2

    # Verify items
    item0 = created["items"][0]
    assert item0["node_id"] == "v1_sec_2_1"
    assert item0["logical_key"] == "sec_2.1"
    assert item0["order_index"] == 0

    item1 = created["items"][1]
    assert item1["node_id"] == "v1_sec_2_1_tbl_1"
    assert item1["node_type"] == "table"
    assert item1["table_data"] is not None
    assert item1["table_data"]["headers"] == ["Parameter", "Value"]
    assert item1["order_index"] == 1

    # Retrieve selection via GET
    get_resp = api_client.get(f"/api/selections/{created['id']}")
    assert get_resp.status_code == 200
    retrieved = get_resp.json()
    assert retrieved["id"] == created["id"]
    assert retrieved["total_items"] == 2
    assert retrieved["items"][0]["node_id"] == "v1_sec_2_1"


def test_exact_version_pinned_content_retrieval(api_client):
    """
    Test 2: Selection retrieves the exact version-pinned text content and snapshot hash.
    V1 selection returns 300 cycles; V2 selection returns 250 cycles.
    """
    # Create V1 selection
    resp_v1 = api_client.post("/api/selections", json={
        "name": "V1 Battery Test",
        "items": [{"node_id": "v1_sec_2_1_1_1_p_5"}]
    })
    assert resp_v1.status_code == 201
    sel_v1 = resp_v1.json()
    assert "300 measurement cycles" in sel_v1["items"][0]["title_or_text"]
    assert "15%" in sel_v1["items"][0]["title_or_text"]
    assert sel_v1["version_number"] == "v1"

    # Create V2 selection
    resp_v2 = api_client.post("/api/selections", json={
        "name": "V2 Battery Test",
        "items": [{"node_id": "v2_sec_2_1_1_1_p_5"}]
    })
    assert resp_v2.status_code == 201
    sel_v2 = resp_v2.json()
    assert "250 measurement cycles" in sel_v2["items"][0]["title_or_text"]
    assert "10%" in sel_v2["items"][0]["title_or_text"]
    assert sel_v2["version_number"] == "v2"

    # Retrieve both and confirm neither replaced the other
    get_v1 = api_client.get(f"/api/selections/{sel_v1['id']}").json()
    get_v2 = api_client.get(f"/api/selections/{sel_v2['id']}").json()

    assert "300 measurement cycles" in get_v1["items"][0]["title_or_text"]
    assert "250 measurement cycles" in get_v2["items"][0]["title_or_text"]
    assert get_v1["items"][0]["content_hash"] != get_v2["items"][0]["content_hash"]


def test_ingesting_v2_after_selection_preserves_v1_selection():
    """
    Test 3: Rigorous immutability test. Ingests V1, creates a selection,
    subsequently ingests V2 into the database, and verifies the pre-existing V1 selection
    still cleanly resolves to the original V1 content.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 1. Ingest V1 only
    s1 = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", document_id="ct200_manual", db=s1)
    s1.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    local_client = TestClient(app)

    # 2. Create selection pinned to V1
    resp = local_client.post("/api/selections", json={
        "name": "Pre-V2 Ingestion Selection",
        "items": [{"node_id": "v1_sec_2_1_1_1_p_5"}]
    })
    assert resp.status_code == 201
    sel_id = resp.json()["id"]

    # Verify initial retrieval is V1
    get_pre = local_client.get(f"/api/selections/{sel_id}").json()
    assert "300 measurement cycles" in get_pre["items"][0]["title_or_text"]

    # 3. Now ingest V2 into the database
    s2 = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", document_id="ct200_manual", db=s2)
    s2.close()

    # 4. Verify the pre-existing selection still retrieves V1 content!
    get_post = local_client.get(f"/api/selections/{sel_id}").json()
    assert get_post["version_number"] == "v1"
    assert "300 measurement cycles" in get_post["items"][0]["title_or_text"]
    assert "250 measurement cycles" not in get_post["items"][0]["title_or_text"]

    app.dependency_overrides.clear()


def test_reject_unknown_node_ids(api_client):
    """
    Test 4: Selection creation with unknown or non-existent node IDs returns 404 Not Found.
    """
    payload = {
        "name": "Invalid Node Selection",
        "items": [
            {"node_id": "v1_sec_1_1"},
            {"node_id": "v1_non_existent_node_xyz"}
        ]
    }
    resp = api_client.post("/api/selections", json=payload)
    assert resp.status_code == 404
    assert "v1_non_existent_node_xyz" in resp.json()["detail"]


def test_reject_empty_selection_and_invalid_names(api_client):
    """
    Test 5: Validates rejection of empty selection names, whitespace names,
    empty items list, and empty node IDs.
    """
    # Empty name
    resp_empty_name = api_client.post("/api/selections", json={
        "name": "   ",
        "items": [{"node_id": "v1_sec_1_1"}]
    })
    assert resp_empty_name.status_code == 400
    assert "name" in resp_empty_name.json()["detail"].lower()

    # Empty items list
    resp_empty_items = api_client.post("/api/selections", json={
        "name": "Empty Items Test",
        "items": []
    })
    assert resp_empty_items.status_code == 400
    assert "at least one node" in resp_empty_items.json()["detail"].lower()

    # Empty node_id inside item
    resp_empty_nid = api_client.post("/api/selections", json={
        "name": "Empty Node ID Test",
        "items": [{"node_id": "  "}]
    })
    assert resp_empty_nid.status_code == 400
    assert "node id" in resp_empty_nid.json()["detail"].lower()


def test_duplicate_node_handling(api_client):
    """
    Test 6: Reject requests containing duplicate node IDs with HTTP 400.
    """
    payload = {
        "name": "Duplicate Node Selection",
        "items": [
            {"node_id": "v1_sec_1_1"},
            {"node_id": "v1_sec_1_1"}
        ]
    }
    resp = api_client.post("/api/selections", json=payload)
    assert resp.status_code == 400
    assert "duplicate" in resp.json()["detail"].lower()


def test_mixed_version_selection_policy(api_client):
    """
    Test 7: Reject attempts to mix nodes from multiple versions (e.g. V1 and V2)
    with HTTP 400 per documented policy.
    """
    payload = {
        "name": "Mixed Version Selection",
        "items": [
            {"node_id": "v1_sec_1_1"},
            {"node_id": "v2_sec_1_1"}
        ]
    }
    resp = api_client.post("/api/selections", json=payload)
    assert resp.status_code == 400
    assert "mixed-version" in resp.json()["detail"].lower()


def test_transaction_rollback_on_failure():
    """
    Test 8: Ensures database transaction rollback on any failure,
    preventing partial selection records or orphan selection items from persisting.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    init_session = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", document_id="ct200_manual", db=init_session)
    init_session.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    local_client = TestClient(app)

    # Attempt selection with one valid node and one invalid node
    fail_payload = {
        "name": "Rollback Test",
        "items": [
            {"node_id": "v1_sec_1_1"},
            {"node_id": "v1_bogus_node_id"}
        ]
    }
    resp = local_client.post("/api/selections", json=fail_payload)
    assert resp.status_code == 404

    # Verify that NO selection or selection item was written
    verify_session = TestingSessionLocal()
    assert verify_session.query(Selection).count() == 0
    assert verify_session.query(SelectionItem).count() == 0
    verify_session.close()

    app.dependency_overrides.clear()


def test_pagination_and_missing_selection_ids(api_client):
    """
    Test 9: Pagination bounds, filtering, and missing selection ID handling (404).
    """
    # Create 3 selections
    for i in range(3):
        api_client.post("/api/selections", json={
            "name": f"Paged Selection {i}",
            "items": [{"node_id": "v1_sec_1"}]
        })

    # Test pagination limit=2, offset=0
    resp_paged = api_client.get("/api/selections?limit=2&offset=0")
    assert resp_paged.status_code == 200
    data = resp_paged.json()
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["items"]) == 2
    assert data["total"] >= 3

    # Test pagination offset=2
    resp_page2 = api_client.get("/api/selections?limit=2&offset=2")
    assert resp_page2.status_code == 200
    data2 = resp_page2.json()
    assert len(data2["items"]) >= 1

    # Missing selection ID returns 404
    resp_missing = api_client.get("/api/selections/sel_non_existent_99999")
    assert resp_missing.status_code == 404
    assert "not found" in resp_missing.json()["detail"].lower()
