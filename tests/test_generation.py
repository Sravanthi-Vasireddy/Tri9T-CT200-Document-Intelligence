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
from app.llm.provider import MockLLMProvider, BaseLLMProvider
from app.llm.generator import QATestGeneratorService
from app.llm.store import JSONTestStore


@pytest.fixture(scope="module")
def api_client(tmp_path_factory):
    """
    Sets up an isolated in-memory database with V1 and V2,
    and points the JSON test store to a temporary test directory.
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
    IngestionService.ingest_pdf("data/ct200_manual_v2.pdf", "v2", document_id="ct200_manual", db=init_session)
    init_session.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Configure temporary JSON test store dir
    temp_dir = tmp_path_factory.mktemp("test_generations")
    os.environ["JSON_STORE_DIR"] = str(temp_dir)
    os.environ["LLM_PROVIDER"] = "mock"

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


def test_generate_test_cases_from_selection(api_client):
    """
    Test 1: Generates 3 to 5 grounded QA test cases from a version-pinned selection.
    Verifies full field traceability, exact grounded values, and valid source node IDs.
    """
    # 1. Create selection containing V1 battery life and specifications table
    sel_resp = api_client.post("/api/selections", json={
        "name": "V1 Specifications & Power Suite",
        "description": "Verifies electrical specifications and typical battery life",
        "items": [
            {"node_id": "v1_sec_2_1_1_1_p_5"},
            {"node_id": "v1_sec_2_1_tbl_1"}
        ]
    })
    assert sel_resp.status_code == 201
    sel_id = sel_resp.json()["id"]

    # 2. Call generate endpoint
    gen_resp = api_client.post(f"/api/selections/{sel_id}/generate", json={
        "force_regenerate": True
    })
    assert gen_resp.status_code == 200
    data = gen_resp.json()

    assert data["selection_id"] == sel_id
    assert data["version_number"] == "v1"
    assert data["provider"] == "mock"
    assert data["cached"] is False
    assert 3 <= data["total_test_cases"] <= 5
    assert len(data["test_cases"]) == data["total_test_cases"]

    # Verify test cases structure and grounding
    valid_source_ids = {"v1_sec_2_1_1_1_p_5", "v1_sec_2_1_tbl_1"}
    for tc in data["test_cases"]:
        assert tc["id"].startswith("TC-")
        assert len(tc["title"]) > 0
        assert len(tc["objective"]) > 0
        assert len(tc["test_steps"]) >= 1
        assert len(tc["expected_result"]) > 0
        assert tc["priority"] in ["critical", "high", "medium", "low"]
        assert len(tc["source_node_ids"]) >= 1
        for src_id in tc["source_node_ids"]:
            assert src_id in valid_source_ids
        assert tc["source_version_identifiers"] == ["v1"]
        assert len(tc["requirement_coverage"]) > 0

    # Specifically check grounding on V1 battery numbers (300 cycles, 15%)
    battery_tc = next((t for t in data["test_cases"] if "Battery" in t["title"] or "battery" in t["objective"].lower()), None)
    assert battery_tc is not None
    assert "300" in battery_tc["expected_result"] or "300" in battery_tc["objective"]
    assert "15%" in battery_tc["expected_result"] or "15%" in battery_tc["objective"]


def test_version_pinned_generation_v1_vs_v2(api_client):
    """
    Test 2: Verifies that test case generation strictly respects version-pinning.
    V1 selection generates tests with 300 cycles / 15%.
    V2 selection generates tests with 250 cycles / 10%.
    """
    # Create V1 selection
    sel_v1 = api_client.post("/api/selections", json={
        "name": "V1 Power Suite",
        "items": [{"node_id": "v1_sec_2_1_1_1_p_5"}]
    }).json()

    # Create V2 selection
    sel_v2 = api_client.post("/api/selections", json={
        "name": "V2 Power Suite",
        "items": [{"node_id": "v2_sec_2_1_1_1_p_5"}]
    }).json()

    # Generate V1
    gen_v1 = api_client.post(f"/api/selections/{sel_v1['id']}/generate", json={"force_regenerate": True}).json()
    assert gen_v1["version_number"] == "v1"
    tc_v1 = gen_v1["test_cases"][0]
    assert "300" in tc_v1["expected_result"] or "300" in tc_v1["objective"]
    assert "15%" in tc_v1["expected_result"] or "15%" in tc_v1["objective"]

    # Generate V2
    gen_v2 = api_client.post(f"/api/selections/{sel_v2['id']}/generate", json={"force_regenerate": True}).json()
    assert gen_v2["version_number"] == "v2"
    tc_v2 = gen_v2["test_cases"][0]
    assert "250" in tc_v2["expected_result"] or "250" in tc_v2["objective"]
    assert "10%" in tc_v2["expected_result"] or "10%" in tc_v2["objective"]


def test_duplicate_generation_caching_and_force_regenerate(api_client):
    """
    Test 3: Duplicate generation policy returns cached result by default
    when selection and source inputs are identical, and executes fresh generation when force_regenerate=True.
    """
    sel = api_client.post("/api/selections", json={
        "name": "Caching Test Selection",
        "items": [{"node_id": "v1_sec_1"}]
    }).json()

    # 1. First generation: not cached
    gen1 = api_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": False}).json()
    assert gen1["cached"] is False
    gen1_id = gen1["generation_id"]

    # 2. Second generation with force_regenerate=False: cached!
    gen2 = api_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": False}).json()
    assert gen2["cached"] is True
    assert gen2["generation_id"] == gen1_id
    assert gen2["input_hash"] == gen1["input_hash"]

    # 3. Third generation with force_regenerate=True: fresh generation!
    gen3 = api_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    assert gen3["cached"] is False
    assert gen3["generation_id"] != gen1_id


def test_rejection_of_unknown_selection(api_client):
    """
    Test 4: Generating test cases for a non-existent selection ID returns 404 Not Found.
    """
    resp = api_client.post("/api/selections/sel_non_existent_9999/generate")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_validation_rejects_hallucinated_source_node_ids():
    """
    Test 5: Validator rejects test cases referencing unselected or fabricated node IDs.
    """
    service = QATestGeneratorService()
    fake_raw = json.dumps({
        "test_cases": [
            {
                "id": "TC-1",
                "title": "Hallucinated Test",
                "objective": "Verify behavior",
                "preconditions": [],
                "test_steps": ["Step 1"],
                "expected_result": "Result",
                "priority": "high",
                "source_node_ids": ["v1_fabricated_node_id_xyz"],
                "requirement_coverage": "Coverage"
            },
            {
                "id": "TC-2",
                "title": "Valid Test 2",
                "objective": "Verify behavior",
                "preconditions": [],
                "test_steps": ["Step 1"],
                "expected_result": "Result",
                "priority": "high",
                "source_node_ids": ["v1_real_node"],
                "requirement_coverage": "Coverage"
            },
            {
                "id": "TC-3",
                "title": "Valid Test 3",
                "objective": "Verify behavior",
                "preconditions": [],
                "test_steps": ["Step 1"],
                "expected_result": "Result",
                "priority": "high",
                "source_node_ids": ["v1_real_node"],
                "requirement_coverage": "Coverage"
            }
        ]
    })

    cases, err = service.validate_test_cases_payload(
        raw_text=fake_raw,
        valid_node_ids=["v1_real_node"],
        version_number="v1",
        content_hashes={"v1_real_node": "hash123"}
    )
    assert len(cases) == 0
    assert err is not None
    assert "unknown/unselected source node" in err


def test_validation_rejects_invalid_test_case_counts():
    """
    Test 6: Validates that test case counts strictly adhere to 3 <= count <= 5.
    """
    service = QATestGeneratorService()

    # Test count = 2 (too few)
    under_raw = json.dumps({
        "test_cases": [
            {
                "id": "TC-1",
                "title": "T1",
                "objective": "O1",
                "test_steps": ["S1"],
                "expected_result": "R1",
                "priority": "high",
                "source_node_ids": ["n1"],
                "requirement_coverage": "C1"
            },
            {
                "id": "TC-2",
                "title": "T2",
                "objective": "O2",
                "test_steps": ["S2"],
                "expected_result": "R2",
                "priority": "high",
                "source_node_ids": ["n1"],
                "requirement_coverage": "C2"
            }
        ]
    })
    _, err_under = service.validate_test_cases_payload(under_raw, ["n1"], "v1", {"n1": "h"})
    assert err_under is not None
    assert "between 3 and 5" in err_under


def test_bounded_repair_retry_success():
    """
    Test 7: Bounded single repair attempt successfully recovers from initial malformed JSON.
    """
    class SingleFailProvider(BaseLLMProvider):
        def __init__(self):
            self.attempts = 0

        @property
        def provider_name(self) -> str:
            return "test_single_fail"

        @property
        def model_name(self) -> str:
            return "test_model"

        def generate(self, system_prompt: str, user_prompt: str) -> str:
            self.attempts += 1
            if self.attempts == 1:
                # Return malformed JSON
                return "{ 'test_cases': [ malformed json without closing..."
            # On repair attempt, return valid output
            return json.dumps({
                "test_cases": [
                    {
                        "id": "TC-FIXED-1",
                        "title": "Fixed Test 1",
                        "objective": "Verify",
                        "test_steps": ["Step 1"],
                        "expected_result": "Result 1",
                        "priority": "high",
                        "source_node_ids": ["v1_sec_1"],
                        "requirement_coverage": "Coverage 1"
                    },
                    {
                        "id": "TC-FIXED-2",
                        "title": "Fixed Test 2",
                        "objective": "Verify",
                        "test_steps": ["Step 1"],
                        "expected_result": "Result 2",
                        "priority": "medium",
                        "source_node_ids": ["v1_sec_1"],
                        "requirement_coverage": "Coverage 2"
                    },
                    {
                        "id": "TC-FIXED-3",
                        "title": "Fixed Test 3",
                        "objective": "Verify",
                        "test_steps": ["Step 1"],
                        "expected_result": "Result 3",
                        "priority": "low",
                        "source_node_ids": ["v1_sec_1"],
                        "requirement_coverage": "Coverage 3"
                    }
                ]
            })

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", document_id="ct200_manual", db=session)

    # Create selection
    sel = Selection(id="sel_repair_test", name="Repair Test", document_id="ct200_manual", version_id="ct200_manual_v1", version_number="v1")
    session.add(sel)
    session.flush()
    item = SelectionItem(selection_id=sel.id, node_id="v1_sec_1", version_id="ct200_manual_v1", logical_key="sec_1", content_hash="h1", order_index=0)
    session.add(item)
    session.commit()

    service = QATestGeneratorService()
    provider = SingleFailProvider()
    result = service.generate_for_selection("sel_repair_test", force_regenerate=True, db=session, provider=provider)

    assert result.validation_status == "repaired"
    assert provider.attempts == 2
    assert len(result.test_cases) == 3
    session.close()


def test_bounded_repair_retry_exhaustion():
    """
    Test 8: If repair attempt also fails, bounded retry terminates and returns HTTP 502 safely.
    """
    class AlwaysFailProvider(BaseLLMProvider):
        @property
        def provider_name(self) -> str:
            return "always_fail"

        @property
        def model_name(self) -> str:
            return "fail_model"

        def generate(self, system_prompt: str, user_prompt: str) -> str:
            return "invalid response always"

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    IngestionService.ingest_pdf("data/ct200_manual.pdf", "v1", document_id="ct200_manual", db=session)

    sel = Selection(id="sel_fail_test", name="Fail Test", document_id="ct200_manual", version_id="ct200_manual_v1", version_number="v1")
    session.add(sel)
    session.flush()
    session.add(SelectionItem(selection_id=sel.id, node_id="v1_sec_1", version_id="ct200_manual_v1", logical_key="sec_1", content_hash="h1", order_index=0))
    session.commit()

    service = QATestGeneratorService()
    provider = AlwaysFailProvider()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        service.generate_for_selection("sel_fail_test", force_regenerate=True, db=session, provider=provider)

    assert exc_info.value.status_code == 502
    assert "validation" in exc_info.value.detail.lower()
    session.close()


def test_persistent_storage_retrieval_and_auditability(api_client):
    """
    Test 9: Verifies persistent JSON store auditability.
    Retrieves saved generation record via GET /api/selections/{id}/test-cases and GET /api/generations/{id},
    confirming presence of immutable source_text_snapshots, input_hash, and prompt_version.
    """
    sel = api_client.post("/api/selections", json={
        "name": "Audit Test Selection",
        "items": [{"node_id": "v1_sec_1"}]
    }).json()

    gen_resp = api_client.post(f"/api/selections/{sel['id']}/generate", json={"force_regenerate": True}).json()
    gen_id = gen_resp["generation_id"]

    # 1. Retrieve by selection ID
    list_resp = api_client.get(f"/api/selections/{sel['id']}/test-cases")
    assert list_resp.status_code == 200
    suites = list_resp.json()
    assert len(suites) >= 1
    assert suites[0]["generation_id"] == gen_id

    # 2. Retrieve by generation ID
    single_resp = api_client.get(f"/api/generations/{gen_id}")
    assert single_resp.status_code == 200
    record = single_resp.json()
    assert record["generation_id"] == gen_id
    assert record["input_hash"] is not None
    assert record["prompt_version"] == "1.0.0"
    assert len(record["source_text_snapshots"]) == 1
    assert record["source_text_snapshots"][0]["node_id"] == "v1_sec_1"
    assert len(record["source_text_snapshots"][0]["title_or_text"]) > 0

    # 3. Missing generation ID returns 404
    missing_resp = api_client.get("/api/generations/gen_non_existent_123")
    assert missing_resp.status_code == 404
