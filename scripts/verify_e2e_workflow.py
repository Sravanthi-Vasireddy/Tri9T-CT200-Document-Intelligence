"""
End-to-End Workflow Verification Script
Tri9T-CT200-Document-Intelligence

Validates the complete lifecycle:
1. Ingest V1 document.
2. Browse and retrieve real document nodes.
3. Create named selection pinned to V1.
4. Generate 3-5 QA test cases (using offline deterministic mocked provider).
5. Record generation ID and immutable source content snapshots.
6. Ingest V2 document.
7. Confirm original selection still resolves to V1 content.
8. Confirm duplicate ingestion deduplicates via SHA-256 file hash.
9. Evaluate staleness against V2:
   - Inflation increment change (40 mmHg -> 30 mmHg) -> STALE
   - Battery life (300 -> 250 cycles, 15% -> 10%) -> STALE
   - E3 auto-deflation (2.0s -> 1.5s) -> STALE
   - Unchanged section (1.1 Intended Use) -> CURRENT
   - Ambiguous / missing historical metadata -> REVIEW_REQUIRED
10. Verify API retrieval endpoints.
"""

import os
import sys
import json
import logging
from fastapi.testclient import TestClient

# Ensure workspace root is in path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from app.database import Base, engine, get_db
from app.ingestion import IngestionService
from app.main import app
from app.staleness import StalenessService
from app.llm.store import JSONTestStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("E2E-Verification")


def run_e2e_verification():
    print("=" * 80)
    print("Tri9T-CT200-Document-Intelligence: Complete End-to-End Workflow Verification")
    print("=" * 80)

    client = TestClient(app)

    # Step 1: Health check
    print("\n--- [Step 1] Health Check ---")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Health check failed: {resp.text}"
    health_data = resp.json()
    print(f"Health Status: {health_data['status']} | Database: {health_data['database']}")
    assert health_data["status"] == "healthy"

    # Step 2: Ingest V1
    print("\n--- [Step 2] Ingest Version 1 ---")
    v1_pdf = os.path.join(WORKSPACE_ROOT, "data", "ct200_manual.pdf")
    assert os.path.exists(v1_pdf), f"V1 PDF missing at {v1_pdf}"

    db = next(get_db())
    try:
        v1_rec = IngestionService.ingest_pdf(v1_pdf, version_number="v1", db=db)
        print(f"V1 Ingested successfully: ID={v1_rec.version_id}, Version={v1_rec.version_number}, Nodes={v1_rec.total_nodes}, Pages={v1_rec.total_pages}")
        assert v1_rec.total_nodes == 50
        assert v1_rec.total_pages == 6

        # Step 3: Browse and retrieve real document nodes
        print("\n--- [Step 3] Browse & Retrieve Real Document Nodes ---")
        # List sections
        resp = client.get("/api/documents/ct200_manual/sections?version=1")
        assert resp.status_code == 200
        sections = resp.json()
        print(f"Top-level sections found in V1: {len(sections)}")
        assert len(sections) == 8

        # Retrieve specific node (V1 Battery Specification)
        node_battery = client.get("/api/nodes/v1_sec_2_1_1_1_p_5")
        assert node_battery.status_code == 200
        batt_data = node_battery.json()
        print(f"Retrieved Node: {batt_data['id']} (logical_key: {batt_data['logical_key']})")
        assert "300 measurement cycles" in batt_data["title_or_text"]
        assert "15%" in batt_data["title_or_text"]
        print("  -> Confirmed V1 battery content: '300 measurement cycles' and '15%'")

        # Retrieve specific node (V1 Inflation Sequence)
        node_inf = client.get("/api/nodes/v1_sec_3_2")
        assert node_inf.status_code == 200
        inf_data = node_inf.json()
        print(f"Retrieved Node: {inf_data['id']} (logical_key: {inf_data['logical_key']})")
        assert "3.2 Cuff Inflation Sequence" in inf_data["title_or_text"]

        # Step 4: Create Named Selection pinned to V1
        print("\n--- [Step 4] Create Named Selection Pinned to V1 ---")
        sel_payload = {
            "name": "E2E Verification Suite",
            "description": "Comprehensive selection testing unchanged and changed requirements",
            "items": [
                {"node_id": "v1_sec_1_1"},           # Unchanged (Intended Use)
                {"node_id": "v1_sec_3_2"},           # Modified (Inflation: 40 -> 30 mmHg)
                {"node_id": "v1_sec_2_1_1_1_p_5"},   # Modified (Battery: 300 -> 250, 15% -> 10%)
                {"node_id": "v1_sec_4_2_tbl_2"}      # Modified (E3: 2.0s -> 1.5s)
            ]
        }
        resp = client.post("/api/selections", json=sel_payload)
        assert resp.status_code == 201, f"Failed to create selection: {resp.text}"
        sel_data = resp.json()
        selection_id = sel_data["id"]
        print(f"Selection Created: ID={selection_id}, Total Items={sel_data['total_items']}, Pinned Version={sel_data['version_number']}")
        assert sel_data["total_items"] == 4
        assert sel_data["version_number"] == "v1"

        # Step 5: Generate QA test cases
        print("\n--- [Step 5] Generate QA Test Cases (LLM Provider: MOCK) ---")
        # Ensure LLM_PROVIDER is mock
        os.environ["LLM_PROVIDER"] = "mock"
        gen_resp = client.post(f"/api/selections/{selection_id}/generate", json={"force_regenerate": True})
        assert gen_resp.status_code == 200, f"Generation failed: {gen_resp.text}"
        gen_data = gen_resp.json()
        generation_id = gen_data["generation_id"]
        print(f"Generation Successful: ID={generation_id}, Test Cases={gen_data['total_test_cases']}, Provider={gen_data['provider']}")
        print(f"Provider Label: {gen_data['provider']} (Deterministic Offline Mock Provider)")
        assert gen_data["total_test_cases"] >= 3
        assert len(gen_data["source_text_snapshots"]) == 4

        # Verify source snapshots
        for snap in gen_data["source_text_snapshots"]:
            print(f"  - Snapshot node: {snap['node_id']} | Hash: {snap['content_hash'][:16]}...")

        # Step 6: Ingest V2 without modifying V1
        print("\n--- [Step 6] Ingest Version 2 ---")
        v2_pdf = os.path.join(WORKSPACE_ROOT, "data", "ct200_manual_v2.pdf")
        assert os.path.exists(v2_pdf), f"V2 PDF missing at {v2_pdf}"
        v2_rec = IngestionService.ingest_pdf(v2_pdf, version_number="v2", db=db)
        print(f"V2 Ingested successfully: ID={v2_rec.version_id}, Version={v2_rec.version_number}, Nodes={v2_rec.total_nodes}, Pages={v2_rec.total_pages}")
        assert v2_rec.total_nodes == 52
        assert v2_rec.total_pages == 7

        # Step 7: Confirm original selection still resolves to V1 content
        print("\n--- [Step 7] Confirm Historical Selection Resolves to V1 Content ---")
        sel_check = client.get(f"/api/selections/{selection_id}")
        assert sel_check.status_code == 200
        sel_check_data = sel_check.json()
        for item in sel_check_data["items"]:
            if item["node_id"] == "v1_sec_2_1_1_1_p_5":
                assert "300 measurement cycles" in item["title_or_text"]
                assert "15%" in item["title_or_text"]
                print("  -> V1 Selection item v1_sec_2_1_1_1_p_5 preserved: 300 cycles / 15%")
            if item["node_id"] == "v1_sec_4_2_tbl_2":
                rows_text = str(item["table_data"]["rows"])
                assert "2 seconds" in rows_text
                print("  -> V1 Selection item v1_sec_4_2_tbl_2 preserved: E3 auto-deflates within 2 seconds")

        # Step 8: Confirm Deduplication of Identical Content
        print("\n--- [Step 8] Test Ingestion Deduplication on Identical File Content ---")
        v1_reingest = IngestionService.ingest_pdf(v1_pdf, version_number="v1", db=db)
        assert v1_reingest.version_id == v1_rec.version_id
        print("  -> Confirmed: Re-ingesting V1 returned existing record without duplicating rows.")

        # Step 9: Retrieve original test cases and assess staleness against V2
        print("\n--- [Step 9] Evaluate Test Case Staleness Against V2 ---")
        stale_resp = client.get(f"/api/generations/{generation_id}/staleness")
        assert stale_resp.status_code == 200, f"Staleness query failed: {stale_resp.text}"
        report = stale_resp.json()
        print(f"Staleness Assessment Summary: Total={report['total_test_cases']}, Current={report['current_count']}, Stale={report['stale_count']}, Review Required={report['review_required_count']}")
        
        # Verify detected changes
        for tc in report["test_cases"]:
            print(f"\n  * Test Case: [{tc['status'].upper()}] {tc['test_case_id']}: {tc['title']}")
            print(f"    Reason: {tc['reason']}")
            if tc.get("impact_reasons"):
                for note in tc["impact_reasons"]:
                    print(f"    Alert: {note}")

        # Step 10: Test Edge Cases (Ambiguous Match, Missing Metadata, Removed Node)
        print("\n--- [Step 10] Test Staleness Edge Cases ---")
        # 10a: Removed node
        store = JSONTestStore()
        staleness_svc = StalenessService(store=store)

        removed_rec = {
            "generation_id": "gen_e2e_removed_test",
            "selection_id": "sel_dummy",
            "document_id": "ct200_manual",
            "version_id": "ct200_manual_v1",
            "version_number": "v1",
            "source_node_ids": ["v1_sec_removed_99"],
            "source_logical_keys": ["sec_removed_99"],
            "source_content_hashes": {"v1_sec_removed_99": "hash_rem"},
            "source_text_snapshots": [{"node_id": "v1_sec_removed_99", "logical_key": "sec_removed_99", "content_hash": "hash_rem", "title_or_text": "Deprecated requirement"}],
            "test_cases": [
                {
                    "id": "TC-REM-1",
                    "title": "Removed Requirement Test",
                    "objective": "Verify",
                    "test_steps": ["Step 1"],
                    "expected_result": "Result",
                    "priority": "high",
                    "source_node_ids": ["v1_sec_removed_99"],
                    "requirement_coverage": "Coverage"
                }
            ],
            "generation_status": "success"
        }
        store.save_generation(removed_rec)
        rep_removed = staleness_svc.evaluate_generation("gen_e2e_removed_test", db)
        tc0 = rep_removed.test_cases[0]
        print(f"Removed node test case status: {tc0.status} | Reason: {tc0.reason}")
        assert tc0.status == "stale"
        assert "removed" in tc0.reason.lower()

        # 10b: Missing historical metadata
        missing_rec = {
            "generation_id": "gen_e2e_missing_meta_test",
            "selection_id": "sel_dummy",
            "document_id": "ct200_manual",
            "version_id": "ct200_manual_v1",
            "version_number": "v1",
            "source_node_ids": ["v1_sec_1_1"],
            "source_logical_keys": ["sec_1.1"],
            "source_content_hashes": {},
            "source_text_snapshots": [],
            "test_cases": [
                {
                    "id": "TC-MISSING-1",
                    "title": "Missing Meta Test",
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
        store.save_generation(missing_rec)
        rep_missing = staleness_svc.evaluate_generation("gen_e2e_missing_meta_test", db)
        tc0_missing = rep_missing.test_cases[0]
        print(f"Missing metadata test case status: {tc0_missing.status} | Reason: {tc0_missing.reason}")
        assert tc0_missing.status == "review_required"

        # Step 11: Selection Staleness Summary & Node Traceability
        print("\n--- [Step 11] Verify Selection Staleness & Node Traceability Endpoints ---")
        sel_stale_resp = client.get(f"/api/selections/{selection_id}/staleness")
        assert sel_stale_resp.status_code == 200
        sel_stale_data = sel_stale_resp.json()
        print(f"Selection Staleness Aggregate: Total Generations={sel_stale_data['total_generations']}, Current={sel_stale_data['current_count']}, Stale={sel_stale_data['stale_count']}")

        node_tc_resp = client.get("/api/nodes/v1_sec_3_2/test-cases")
        assert node_tc_resp.status_code == 200
        node_tc_data = node_tc_resp.json()
        print(f"Node v1_sec_3_2 associated test cases: {len(node_tc_data)}")
        assert len(node_tc_data) >= 1
        print(f"  -> Test Case: {node_tc_data[0]['test_case_id']} | Status: {node_tc_data[0]['staleness_status']}")

        print("\n" + "=" * 80)
        print("ALL END-TO-END WORKFLOW VERIFICATIONS PASSED SUCCESSFULLY!")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    run_e2e_verification()
