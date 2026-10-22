import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Document, DocumentVersion, DocumentNodeModel
from app.ingestion import IngestionService
from app.main import app


@pytest.fixture(scope="module")
def api_client():
    """
    Sets up an isolated in-memory database with pre-ingested V1 and V2
    and configures FastAPI dependency overrides for pristine test isolation.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Pre-populate V1 and V2
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


def test_health_check(api_client):
    """Test 1: Health check endpoint confirms app and database connectivity."""
    resp = api_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "Tri9T-CT200-Document-Intelligence" in data["app_name"]


def test_list_document_versions(api_client):
    """Test 2: Lists all versions of a document in chronological order."""
    resp = api_client.get("/api/documents/ct200_manual/versions")
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == "v1"
    assert versions[0]["total_nodes"] == 50
    assert versions[1]["version_number"] == "v2"
    assert versions[1]["total_nodes"] == 52

    # Unknown document
    unknown_resp = api_client.get("/api/documents/unknown_doc/versions")
    assert unknown_resp.status_code == 404


def test_list_sections_specific_version(api_client):
    """Test 3: Lists top-level sections for a specific requested version."""
    # Test version=1 and version=v1
    for v_param in ["1", "v1"]:
        resp = api_client.get(f"/api/documents/ct200_manual/sections?version={v_param}")
        assert resp.status_code == 200
        sections = resp.json()
        assert len(sections) == 8  # Sections 1 to 8
        sec_nums = [s["section_number"] for s in sections]
        assert sec_nums == ["1", "2", "3", "4", "5", "6", "7", "8"]
        # Verify node IDs correspond to v1
        for s in sections:
            assert s["id"].startswith("v1_sec_")


def test_list_sections_default_latest_version(api_client):
    """Test 4: Omission of version parameter defaults to the latest version (v2)."""
    resp = api_client.get("/api/documents/ct200_manual/sections")
    assert resp.status_code == 200
    sections = resp.json()
    assert len(sections) == 8
    # Node IDs must start with v2_
    for s in sections:
        assert s["id"].startswith("v2_sec_")


def test_retrieve_node_exact_versioned_content(api_client):
    """Test 5: Node retrieval returns exact historical version content, preserving V1 vs V2."""
    # V1 battery life node
    resp_v1 = api_client.get("/api/nodes/v1_sec_2_1_1_1_p_5")
    assert resp_v1.status_code == 200
    node_v1 = resp_v1.json()
    assert "300 measurement cycles" in node_v1["title_or_text"]
    assert "15%" in node_v1["title_or_text"]
    assert node_v1["version_number"] == "v1"

    # V2 battery life node
    resp_v2 = api_client.get("/api/nodes/v2_sec_2_1_1_1_p_5")
    assert resp_v2.status_code == 200
    node_v2 = resp_v2.json()
    assert "250 measurement cycles" in node_v2["title_or_text"]
    assert "10%" in node_v2["title_or_text"]
    assert node_v2["version_number"] == "v2"

    # Table retrieval with structured rows and columns
    resp_tbl = api_client.get("/api/nodes/v1_sec_2_1_tbl_1")
    assert resp_tbl.status_code == 200
    tbl_data = resp_tbl.json()["table_data"]
    assert tbl_data is not None
    assert tbl_data["headers"] == ["Parameter", "Value"]
    assert len(tbl_data["rows"]) == 7

    # Unknown node ID
    resp_unknown = api_client.get("/api/nodes/non_existent_node_id")
    assert resp_unknown.status_code == 404


def test_search_headings_and_body_text(api_client):
    """Test 6: Search endpoint finds matches across headings and body paragraphs."""
    # Search body text
    resp = api_client.get("/api/search?q=oscillometric")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_matches"] > 0
    assert any("oscillometric" in r["title_or_text"].lower() for r in data["results"])
    # Check snippet generation
    first_result = data["results"][0]
    assert "snippet" in first_result
    assert len(first_result["snippet"]) > 0

    # Search section heading
    resp_head = api_client.get("/api/search?q=Overpressure")
    assert resp_head.status_code == 200
    assert resp_head.json()["total_matches"] > 0


def test_search_filtering_by_type_and_version(api_client):
    """Test 7: Search supports node-type and version filters."""
    # Filter by section node type in version 1
    resp = api_client.get("/api/search?q=Error&type=section&version=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_matches"] > 0
    for r in data["results"]:
        assert r["node_type"] == "section"
        assert r["version_number"] == "v1"

    # Filter by table node type
    resp_tbl = api_client.get("/api/search?q=Code&type=table")
    assert resp_tbl.status_code == 200
    for r in resp_tbl.json()["results"]:
        assert r["node_type"] == "table"


def test_compare_unchanged_and_modified_nodes(api_client):
    """Test 8: Cross-version node comparison identifies unchanged vs modified status."""
    # Unchanged node: Section 1.1 Intended Use
    resp_unchanged = api_client.get("/api/nodes/v1_sec_1_1/changes?target_version=2")
    assert resp_unchanged.status_code == 200
    ch_unchanged = resp_unchanged.json()
    assert ch_unchanged["status"] == "unchanged"
    assert ch_unchanged["source_node_id"] == "v1_sec_1_1"
    assert ch_unchanged["target_node_id"] == "v2_sec_1_1"
    assert ch_unchanged["source_content_hash"] == ch_unchanged["target_content_hash"]

    # Modified node: Section 2.1.1.1
    resp_mod = api_client.get("/api/nodes/v1_sec_2_1_1_1/changes?target_version=2")
    assert resp_mod.status_code == 200
    ch_mod = resp_mod.json()
    assert ch_mod["status"] == "modified"
    assert ch_mod["source_node_id"] == "v1_sec_2_1_1_1"
    assert ch_mod["target_node_id"] == "v2_sec_2_1_1_1"
    assert ch_mod["source_content_hash"] != ch_mod["target_content_hash"]
    assert ch_mod["diff_summary"] is not None

    # Default to latest version when target_version is omitted
    resp_default = api_client.get("/api/nodes/v1_sec_3_2/changes")
    assert resp_default.status_code == 200
    assert resp_default.json()["target_version_number"] == "v2"
    assert resp_default.json()["status"] == "modified"


def test_compare_removed_and_ambiguous_nodes(api_client):
    """Test 9: Cross-version comparison handles removed and ambiguous node cases."""
    # Query changes for a node comparing V2 to V1:
    # Section 5.3 was added in V2, so comparing v2_sec_5_3 against V1 should report 'removed' in V1!
    resp_removed = api_client.get("/api/nodes/v2_sec_5_3/changes?target_version=1")
    assert resp_removed.status_code == 200
    ch_removed = resp_removed.json()
    assert ch_removed["status"] == "removed"
    assert ch_removed["target_node_id"] is None


def test_invalid_parameters_and_edge_cases(api_client):
    """Test 10: Validates error handling for empty queries, pagination bounds, and missing IDs."""
    # Empty query string
    resp_empty = api_client.get("/api/search?q=   ")
    assert resp_empty.status_code == 400

    # Pagination boundaries
    resp_paged = api_client.get("/api/search?q=device&limit=2&offset=0")
    assert resp_paged.status_code == 200
    assert len(resp_paged.json()["results"]) <= 2

    # Invalid version in section listing
    resp_bad_ver = api_client.get("/api/documents/ct200_manual/sections?version=99")
    assert resp_bad_ver.status_code == 404

    # Invalid target version in comparison
    resp_bad_target = api_client.get("/api/nodes/v1_sec_1_1/changes?target_version=99")
    assert resp_bad_target.status_code == 404

    # Unknown source node ID in comparison
    resp_bad_source = api_client.get("/api/nodes/unknown_node_xyz/changes")
    assert resp_bad_source.status_code == 404


def test_custom_swagger_ui_and_openapi(api_client):
    """Test 11: Validates that custom-themed Swagger UI and OpenAPI schemas load successfully."""
    # 1. /docs endpoint returns 200 HTML with custom styling injected
    docs_resp = api_client.get("/docs")
    assert docs_resp.status_code == 200
    assert "text/html" in docs_resp.headers.get("content-type", "")
    assert "Tri9T-CT200 Document Intelligence — Custom Swagger Theme" in docs_resp.text
    assert "Tri9T-CT200-Document-Intelligence API - Swagger Documentation" in docs_resp.text
    assert "/openapi.json" in docs_resp.text

    # 2. /openapi.json returns valid JSON OpenAPI specification
    openapi_resp = api_client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    assert "application/json" in openapi_resp.headers.get("content-type", "")
    schema = openapi_resp.json()
    assert "openapi" in schema
    assert "info" in schema
    assert schema["info"]["title"] == "Tri9T-CT200-Document-Intelligence API"
    assert "/health" in schema["paths"]
    assert "/api/documents/{document_id}/versions" in schema["paths"]

    # 3. Custom CSS endpoint returns 200 with text/css
    css_resp = api_client.get("/static/swagger-custom.css")
    assert css_resp.status_code == 200
    assert "text/css" in css_resp.headers.get("content-type", "")
    assert ".swagger-ui" in css_resp.text

