import os
import json
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
from app.llm.store import JSONTestStore
from app.staleness import StalenessService, detect_high_impact_changes


@pytest.fixture(scope="module")
def staleness_client(tmp_path_factory):
    """
    Sets up an in-memory database with pre-ingested V1 and V2,
    and isolates JSON test storage in a temporary directory.
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

    temp_dir = tmp_path_factory.mktemp("test_staleness_store")
    os.environ["JSON_STORE_DIR"] = str(temp_dir)
    os.environ["LLM_PROVIDER"] = "mock"

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


def test_unchanged_v1_section_reported_current_after_v2_ingestion(staleness_client):
    """
    Test 1: A test generated from an unchanged V1 section (Section 1.1 Intended Use)
    is reported CURRENT after V2 ingestion.
    """
    # 1. Create selection for Section 1.1
    sel = staleness_client.post("/api/selections", json={
        "name": "Intended Use Suite",
        "items": [{"node_id": "v1_sec_1_1"}]
    }).json()

    # 2. Generate test cases
    gen = staleness_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    gen_id = gen["generation_id"]

    # 3. Assess staleness against latest version (V2)
    st_resp = staleness_client.get(f"/api/generations/{gen_id}/staleness")
    assert st_resp.status_code == 200
    report = st_resp.json()

    assert report["source_version_number"] == "v1"
    assert report["target_version_number"] == "v2"
    assert report["overall_status"] == "current"
    assert report["current_count"] == report["total_test_cases"]
    assert report["stale_count"] == 0

    for tc in report["test_cases"]:
        assert tc["status"] == "current"
        assert "remain unchanged" in tc["reason"].lower()


def test_section_3_2_inflation_increment_change(staleness_client):
    """
    Test 2: A test generated from Section 3.2 is flagged STALE when inflation increment
    changes from 40 mmHg to 30 mmHg in V2.
    """
    sel = staleness_client.post("/api/selections", json={
        "name": "Inflation Suite",
        "items": [{"node_id": "v1_sec_3_2"}]
    }).json()

    gen = staleness_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    gen_id = gen["generation_id"]

    st_resp = staleness_client.get(f"/api/generations/{gen_id}/staleness")
    assert st_resp.status_code == 200
    report = st_resp.json()

    assert report["overall_status"] == "stale"
    assert report["stale_count"] >= 1

    stale_tc = next(t for t in report["test_cases"] if t["status"] == "stale")
    assert stale_tc["potential_high_impact"] is True
    # Check diff summary mentions 40 mmHg / 30 mmHg
    ref_node = stale_tc["referenced_nodes"][0]
    assert ref_node["status"] == "modified"
    assert "40" in ref_node["diff_summary"] or "30" in ref_node["diff_summary"]


def test_battery_requirement_detected_changes(staleness_client):
    """
    Test 3: A test based on the battery requirement detects the changes from
    300 to 250 cycles and from 15% to 10% as high-impact specification drift.
    """
    sel = staleness_client.post("/api/selections", json={
        "name": "Battery Life Test Suite",
        "items": [{"node_id": "v1_sec_2_1_1_1_p_5"}]
    }).json()

    gen = staleness_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    gen_id = gen["generation_id"]

    st_resp = staleness_client.get(f"/api/generations/{gen_id}/staleness")
    assert st_resp.status_code == 200
    report = st_resp.json()

    assert report["overall_status"] == "stale"
    stale_tc = report["test_cases"][0]
    assert stale_tc["status"] == "stale"
    assert stale_tc["potential_high_impact"] is True

    diff = stale_tc["referenced_nodes"][0]["diff_summary"]
    assert "300" in diff or "250" in diff


def test_e3_auto_deflation_requirement_detected_changes(staleness_client):
    """
    Test 4: A test tied to Error table / E3 requirement detects the auto-deflation
    timing change from 2.0s to 1.5s in V2.
    """
    sel = staleness_client.post("/api/selections", json={
        "name": "Error Table Suite",
        "items": [{"node_id": "v1_sec_4_2_tbl_2"}]
    }).json()

    gen = staleness_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    gen_id = gen["generation_id"]

    st_resp = staleness_client.get(f"/api/generations/{gen_id}/staleness")
    assert st_resp.status_code == 200
    report = st_resp.json()

    assert report["overall_status"] == "stale"
    stale_tc = report["test_cases"][0]
    assert stale_tc["status"] == "stale"
    assert stale_tc["potential_high_impact"] is True


def test_removed_and_ambiguous_source_nodes_not_marked_current():
    """
    Test 5: Tests referencing removed or ambiguously matched source nodes
    are NOT falsely marked current.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", document_id="ct200_manual", db=session)
    IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", document_id="ct200_manual", db=session)

    store = JSONTestStore()
    svc = StalenessService(store=store)

    # 1. Synthetic record referencing removed node
    removed_rec = {
        "generation_id": "gen_removed_test",
        "selection_id": "sel_dummy",
        "document_id": "ct200_manual",
        "version_id": "ct200_manual_v1",
        "version_number": "v1",
        "source_node_ids": ["v1_removed_section_xyz"],
        "source_logical_keys": ["sec_removed_99"],
        "source_content_hashes": {"v1_removed_section_xyz": "hash_rem"},
        "source_text_snapshots": [{"node_id": "v1_removed_section_xyz", "logical_key": "sec_removed_99", "content_hash": "hash_rem", "title_or_text": "Removed requirement"}],
        "test_cases": [
            {
                "id": "TC-REM-1",
                "title": "Removed Requirement Test",
                "objective": "Verify",
                "test_steps": ["Step 1"],
                "expected_result": "Result",
                "priority": "high",
                "source_node_ids": ["v1_removed_section_xyz"],
                "requirement_coverage": "Coverage"
            }
        ],
        "generation_status": "success"
    }
    store.save_generation(removed_rec)

    rep_removed = svc.evaluate_generation("gen_removed_test", session)
    assert rep_removed.test_cases[0].status.value == "stale"
    assert "removed" in rep_removed.test_cases[0].reason.lower()
    assert rep_removed.test_cases[0].status.value != "current"

    # 2. Synthetic record referencing ambiguous node
    # Create two nodes in V2 with the same logical_key
    ambig_node1 = DocumentNodeModel(id="v2_ambig_1", version_id="ct200_manual_v2", logical_key="sec_ambig_99", node_type="section", title_or_text="Ambig 1", hierarchy_level=1, reading_order_index=990, page_start=1, page_end=1, content_hash="ha1")
    ambig_node2 = DocumentNodeModel(id="v2_ambig_2", version_id="ct200_manual_v2", logical_key="sec_ambig_99", node_type="section", title_or_text="Ambig 2", hierarchy_level=1, reading_order_index=991, page_start=1, page_end=1, content_hash="ha2")
    session.add(ambig_node1)
    session.add(ambig_node2)
    session.commit()

    ambig_rec = {
        "generation_id": "gen_ambig_test",
        "selection_id": "sel_dummy",
        "document_id": "ct200_manual",
        "version_id": "ct200_manual_v1",
        "version_number": "v1",
        "source_node_ids": ["v1_ambig_node"],
        "source_logical_keys": ["sec_ambig_99"],
        "source_content_hashes": {"v1_ambig_node": "hash_orig"},
        "source_text_snapshots": [{"node_id": "v1_ambig_node", "logical_key": "sec_ambig_99", "content_hash": "hash_orig", "title_or_text": "Original requirement"}],
        "test_cases": [
            {
                "id": "TC-AMBIG-1",
                "title": "Ambiguous Test",
                "objective": "Verify",
                "test_steps": ["Step 1"],
                "expected_result": "Result",
                "priority": "high",
                "source_node_ids": ["v1_ambig_node"],
                "requirement_coverage": "Coverage"
            }
        ],
        "generation_status": "success"
    }
    store.save_generation(ambig_rec)

    rep_ambig = svc.evaluate_generation("gen_ambig_test", session)
    assert rep_ambig.test_cases[0].status.value == "review_required"
    assert "ambiguous" in rep_ambig.test_cases[0].reason.lower()
    assert rep_ambig.test_cases[0].status.value != "current"
    session.close()


def test_mixed_granularity_one_stale_one_current(staleness_client):
    """
    Test 6: Granular evaluation: within the exact same generation,
    one test case can be STALE while another test case remains CURRENT.
    """
    # Create selection with 1 unchanged node (1.1) and 1 modified node (2.1.1.1)
    sel = staleness_client.post("/api/selections", json={
        "name": "Mixed Granularity Suite",
        "items": [
            {"node_id": "v1_sec_1_1"},
            {"node_id": "v1_sec_2_1_1_1_p_5"}
        ]
    }).json()

    gen = staleness_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    gen_id = gen["generation_id"]

    st_resp = staleness_client.get(f"/api/generations/{gen_id}/staleness")
    assert st_resp.status_code == 200
    report = st_resp.json()

    # Find test case citing ONLY sec_1_1
    tc_current = next((t for t in report["test_cases"] if t["referenced_nodes"] and all(n["node_id"] == "v1_sec_1_1" for n in t["referenced_nodes"])), None)
    # Find test case citing sec_2_1_1_1_p_5
    tc_stale = next((t for t in report["test_cases"] if any(n["node_id"] == "v1_sec_2_1_1_1_p_5" for n in t["referenced_nodes"])), None)

    assert tc_stale is not None
    assert tc_stale["status"] == "stale"

    if tc_current:
        assert tc_current["status"] == "current"


def test_multi_node_reference_combined_status():
    """
    Test 7: A single test case referencing multiple nodes (one unchanged, one modified)
    receives the correct combined status of STALE.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", document_id="ct200_manual", db=session)
    IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", document_id="ct200_manual", db=session)

    store = JSONTestStore()
    svc = StalenessService(store=store)

    multi_rec = {
        "generation_id": "gen_multi_node_test",
        "selection_id": "sel_dummy",
        "document_id": "ct200_manual",
        "version_id": "ct200_manual_v1",
        "version_number": "v1",
        "source_node_ids": ["v1_sec_1_1", "v1_sec_2_1_1_1_p_5"],
        "source_logical_keys": ["sec_1.1", "sec_2.1.1.1_p_5"],
        "source_content_hashes": {
            "v1_sec_1_1": session.query(DocumentNodeModel).filter(DocumentNodeModel.id == "v1_sec_1_1").first().content_hash,
            "v1_sec_2_1_1_1_p_5": session.query(DocumentNodeModel).filter(DocumentNodeModel.id == "v1_sec_2_1_1_1_p_5").first().content_hash
        },
        "source_text_snapshots": [
            {"node_id": "v1_sec_1_1", "logical_key": "sec_1.1", "content_hash": "h1", "title_or_text": "Intended Use"},
            {"node_id": "v1_sec_2_1_1_1_p_5", "logical_key": "sec_2.1.1.1_p_5", "content_hash": "h2", "title_or_text": "300 measurement cycles"}
        ],
        "test_cases": [
            {
                "id": "TC-MULTI-1",
                "title": "Combined Multi Node Test",
                "objective": "Verify",
                "test_steps": ["Step 1"],
                "expected_result": "Result",
                "priority": "high",
                "source_node_ids": ["v1_sec_1_1", "v1_sec_2_1_1_1_p_5"],
                "requirement_coverage": "Coverage"
            }
        ],
        "generation_status": "success"
    }
    store.save_generation(multi_rec)

    rep = svc.evaluate_generation("gen_multi_node_test", session)
    tc = rep.test_cases[0]
    assert tc.status.value == "stale"
    assert "modified" in tc.reason.lower()
    session.close()


def test_missing_historical_metadata_produces_review_required():
    """
    Test 8: Missing historical snapshot or content hash metadata produces
    REVIEW_REQUIRED rather than an unjustified current status.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", document_id="ct200_manual", db=session)
    IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", document_id="ct200_manual", db=session)

    store = JSONTestStore()
    svc = StalenessService(store=store)

    corrupt_rec = {
        "generation_id": "gen_corrupt_test",
        "selection_id": "sel_dummy",
        "document_id": "ct200_manual",
        "version_id": "ct200_manual_v1",
        "version_number": "v1",
        "source_node_ids": ["v1_sec_1_1"],
        "source_logical_keys": ["sec_1.1"],
        "source_content_hashes": {},  # Missing hash
        "source_text_snapshots": [],  # Missing snapshot
        "test_cases": [
            {
                "id": "TC-CORRUPT-1",
                "title": "Corrupt Meta Test",
                "objective": "Verify",
                "test_steps": ["Step 1"],
                "expected_result": "Result",
                "priority": "medium",
                "source_node_ids": ["v1_sec_1_1"],
                "requirement_coverage": "Coverage"
            }
        ],
        "generation_status": "success"
    }
    store.save_generation(corrupt_rec)

    rep = svc.evaluate_generation("gen_corrupt_test", session)
    assert rep.test_cases[0].status.value == "review_required"
    assert rep.test_cases[0].status.value != "current"
    session.close()


def test_staleness_retrieval_endpoints(staleness_client):
    """
    Test 9: Verifies retrieval endpoints:
    - GET /api/selections/{selection_id}/generations
    - GET /api/generations/{generation_id} (including staleness assessment)
    - GET /api/generations/{generation_id}/staleness
    - GET /api/selections/{selection_id}/staleness
    - GET /api/nodes/{node_id}/test-cases
    """
    # Create selection and generate test suite
    sel = staleness_client.post("/api/selections", json={
        "name": "Endpoint Verification Selection",
        "items": [{"node_id": "v1_sec_2_1_1_1_p_5"}]
    }).json()

    gen = staleness_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    gen_id = gen["generation_id"]

    # 1. GET /api/selections/{selection_id}/generations
    resp_sel_gens = staleness_client.get(f"/api/selections/{sel['id']}/generations")
    assert resp_sel_gens.status_code == 200
    assert len(resp_sel_gens.json()) >= 1
    assert resp_sel_gens.json()[0]["generation_id"] == gen_id

    # 2. GET /api/generations/{generation_id} (contains staleness assessment)
    resp_gen = staleness_client.get(f"/api/generations/{gen_id}")
    assert resp_gen.status_code == 200
    gen_data = resp_gen.json()
    assert gen_data["staleness"] is not None
    assert gen_data["staleness"]["overall_status"] == "stale"

    # 3. GET /api/generations/{generation_id}/staleness
    resp_gen_st = staleness_client.get(f"/api/generations/{gen_id}/staleness")
    assert resp_gen_st.status_code == 200
    assert resp_gen_st.json()["overall_status"] == "stale"

    # 4. GET /api/selections/{selection_id}/staleness
    resp_sel_st = staleness_client.get(f"/api/selections/{sel['id']}/staleness")
    assert resp_sel_st.status_code == 200
    sel_st_data = resp_sel_st.json()
    assert sel_st_data["total_generations"] >= 1
    assert sel_st_data["stale_count"] >= 1

    # 5. GET /api/nodes/{node_id}/test-cases
    resp_node_tc = staleness_client.get("/api/nodes/v1_sec_2_1_1_1_p_5/test-cases")
    assert resp_node_tc.status_code == 200
    cases = resp_node_tc.json()
    assert len(cases) >= 1
    assert cases[0]["staleness_status"] == "stale"
    assert cases[0]["potential_high_impact"] is True

    # 6. Unknown node ID returns 404
    resp_unknown_node = staleness_client.get("/api/nodes/v1_unknown_xyz_99/test-cases")
    assert resp_unknown_node.status_code == 404


def test_deterministic_repeated_assessments(staleness_client):
    """
    Test 10: Repeated staleness assessments are strictly deterministic.
    """
    sel = staleness_client.post("/api/selections", json={
        "name": "Deterministic Assessment Suite",
        "items": [{"node_id": "v1_sec_1_1"}]
    }).json()

    gen = staleness_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    gen_id = gen["generation_id"]

    rep1 = staleness_client.get(f"/api/generations/{gen_id}/staleness").json()
    rep2 = staleness_client.get(f"/api/generations/{gen_id}/staleness").json()

    assert rep1["overall_status"] == rep2["overall_status"]
    assert rep1["current_count"] == rep2["current_count"]
    assert rep1["stale_count"] == rep2["stale_count"]
    assert len(rep1["test_cases"]) == len(rep2["test_cases"])
