# Tri9T-CT200-Document-Intelligence

AI Engineering Assignment for **Tri9T AI**.

**Tri9T-CT200-Document-Intelligence** is a backend system engineered to process complex technical documentation (specifically the CardioTrack CT-200 Home Blood Pressure Monitor user manuals), reconstruct hierarchical document trees, manage document versions, detect granular content diffs, generate QA test cases via LLM, and automatically flag test cases that become stale when underlying specifications change.

---

## 1. Project Overview & Objectives

1. **Document Intelligence & Hierarchy Extraction**: Parse multi-page technical manuals (including tables, multi-level sections, lists, and cross-page spans) into a validated, structured node tree.
2. **Version Management & Delta Tracking**: Ingest multiple versions (`ct200_manual.pdf` as Version 1 and `ct200_manual_v2.pdf` as Version 2) and compute structural/semantic deltas.
3. **LLM-Powered QA Test Case Generation**: Generate structured QA test cases directly mapped to individual document sections (functional, boundary, alarm/safety conditions).
4. **Staleness Detection Engine**: Identify and flag test cases when referenced sections are updated, added, or deprecated across document versions.

---

## 2. Technology Stack

- **Language**: Python 3.10+
- **API Framework**: FastAPI
- **Data Validation & Schemas**: Pydantic v2
- **Relational Database**: SQLite with SQLAlchemy ORM (for document metadata, versions, sections, and test case state)
- **Document Store**: Justified JSON file document store (in `generated/`) with modular support for MongoDB
- **Document Parsing**: PyMuPDF (`pymupdf` / `fitz`) with vector layout analysis
- **Testing**: `pytest`, `pytest-asyncio`, `httpx`
- **Version Control**: Git

---

## 3. Project Structure

```text
Tri9T-CT200-Document-Intelligence/
├── app/                  # Application source code (models, schemas, parser, api, services)
│   └── __init__.py
├── data/                 # Source document versions
│   ├── ct200_manual.pdf    # Version 1 (6 pages, 443 KB)
│   └── ct200_manual_v2.pdf # Version 2 (7 pages, 447 KB)
├── generated/            # Document store output artifacts (JSON trees, generated tests)
│   └── .gitkeep
├── tests/                # Test suite
│   └── __init__.py
├── .env.example          # Environment variables template
├── .gitignore            # Git exclusion rules
├── APPROACH.md           # In-depth architectural analysis, findings & design strategy
├── README.md             # Project documentation and quickstart
└── requirements.txt      # Project dependencies
```

---

## 4. Setup and Installation

### Prerequisites
- Python 3.10 or higher
- Git

### 1. Clone & Navigate
```bash
git clone <repository-url>
cd Tri9T-CT200-Document-Intelligence
```

### 2. Create and Activate Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in necessary keys (e.g., your LLM API key):
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

---

## 5. Verified Data Files

Both primary technical manuals have been inspected and verified in `data/`:

| File | Version | Pages | Size (bytes) | Status | Format |
|---|---|---|---|---|---|
| `data/ct200_manual.pdf` | Version 1 | 6 | 443,032 | Verified authentic | Digital Vector PDF (NimbusSans / NotoSerif) |
| `data/ct200_manual_v2.pdf` | Version 2 | 7 | 447,477 | Verified authentic | Digital Vector PDF (NimbusSans / NotoSerif) |

> **Note**: Both PDFs contain vector fonts and selectable digital text rather than scanned raster images (zero embedded bitmap images detected). Consequently, direct digital layout parsing via PyMuPDF is the optimal and most accurate parsing strategy.

---

## 6. Document Findings & Structural Irregularities

Our initial inspection revealed several key structural irregularities and document diffs (detailed thoroughly in [APPROACH.md](file:///c:/Users/SAI%20KUMAR/Downloads/Tri9T-CT200-Document-Intelligence/APPROACH.md)):

1. **Non-Sequential Numbering (Section 3.4 before Section 3.3)**: On Page 3 of both manuals, Section 3.4 (*Auto Shutoff*) physically precedes Section 3.3 (*Result Display and Classification*).
2. **Orphaned Subsections (Section 2.1.1.1 without 2.1.1)**: Section 2.1 (*General Specifications*) jumps straight to 2.1.1.1 (*Battery Life Under Typical Use*) without an intermediate 2.1.1 section.
3. **Structured Tabular Data**: 
   - Section 2.1: 8×2 General Specifications table.
   - Section 4.2: Error Codes table (E1–E5 in V1; E1–E6 in V2) with multi-line cells.
4. **Cross-Page Paragraph and Sentence Spans**: Text and sections split across page breaks (e.g., Section 3.1 split across pages 2–3, Section 4.3 across pages 4–5 in V2, Section 6.1 across pages 5–6 in V2, Section 8.1 across pages 6–7 in V2).
5. **Specification Deltas (V1 vs V2)**:
   - Battery life lowered from 300 cycles (15% warning) to 250 cycles (10% warning).
   - Inflation increment changed from 40 mmHg to 30 mmHg.
   - E3 auto-deflation response time tightened from 2.0s to 1.5s.
   - Addition of Error Code `E6` (Bluetooth sync failure) and alarm threshold updates.
   - Brand new Section 5.3 (*Data Export*) added in V2.

See [APPROACH.md](file:///c:/Users/SAI%20KUMAR/Downloads/Tri9T-CT200-Document-Intelligence/APPROACH.md) for full architectural specifications, data models, and implementation plans.

---

## 7. Running the PDF Parser Pipeline

To parse both `ct200_manual.pdf` (Version 1) and `ct200_manual_v2.pdf` (Version 2) and produce validated document trees:

```bash
# Execute the extraction pipeline
python scripts/parse_manuals.py
```

### Generated Artifacts
The pipeline automatically outputs validated JSON structures to `generated/`:
- `generated/ct200_manual_v1_tree.json`: Version 1 hierarchical tree (50 nodes, 6 pages, 2 tables, 1 list).
- `generated/ct200_manual_v2_tree.json`: Version 2 hierarchical tree (52 nodes, 7 pages, 2 tables, 1 list).
- `generated/validation_report.json`: Comprehensive validation metrics, reciprocity verification, and node counts.

---

## 8. Running the Test Suite

The test suite validates parser correctness, tree integrity, anomaly detection, table preservation, and hash deltas:

```bash
# Run all tests with verbose output
pytest -v tests/test_parser.py
```

### Verified Parser Test Cases
1. `test_out_of_order_sections`: Verifies Section 3.4 precedes Section 3.3 in physical reading order while both retain correct canonical parentage (`Section 3`).
2. `test_missing_intermediate_subsection_numbering`: Verifies Section 2.1.1.1 attaches directly under Section 2.1 without fabricating non-existent Section 2.1.1.
3. `test_duplicate_headings_with_distinct_node_ids`: Verifies distinct node IDs and logical keys for identical heading titles (Section 4.2 vs Section 7.1 "Error Codes").
4. `test_table_row_and_column_preservation`: Verifies structured 8×2 specifications table and error codes tables (5 rows in V1, 6 rows in V2 with E6 addition).
5. `test_content_hash_changes_on_meaningful_diff`: Verifies hash stability on unchanged sections (1.1) and hash changes on modified sections (2.1.1.1, 3.2, 4.2, 4.3) and new section 5.3.
6. `test_cross_page_paragraph_continuation`: Verifies cross-page text stitching across page boundaries (e.g., Section 3.1, Section 4.3, Section 6.1, Section 8.1).
7. `test_tree_validation_and_anomaly_detection`: Verifies `DocumentTreeValidator` passes valid trees and catches anomalies (orphan nodes, cycles, missing parents).

---

## 9. Database Ingestion & Version Management

The system persists document versions in SQLite (`tri9t_doc_intel.db`) via SQLAlchemy ORM models:
- **`Document`**: Master technical document registry.
- **`DocumentVersion`**: Versioned snapshots (`v1`, `v2`) with source filename, page counts, node counts, and binary `file_hash` for deduplication.
- **`DocumentNodeModel`**: Granular nodes holding `logical_key`, version-specific `id`, hierarchy level, parent ID, reading order, coordinates, table JSON, and content hash.

### Ingestion CLI
To ingest both V1 and V2 into SQLite and compute structural diffs:

```bash
# Execute transactional ingestion
python scripts/ingest_documents.py
```

- **Deduplication & Idempotency**: Running `python scripts/ingest_documents.py` a second time uses SHA-256 `file_hash` to detect that both versions are already stored, returning existing records in milliseconds without inserting duplicate rows.
- **Transactional Rollback**: Ingestion runs inside a strict database transaction. If parsing, validation, or foreign-key constraints fail, the session issues `db.rollback()`, ensuring no partial versions or orphan nodes are written.

### Database Test Suite
To run all database, versioning, diff, and rollback tests:

```bash
pytest -v tests/test_database.py
```

### Complete Test Suite (Parser + Database)
```bash
pytest -v
```
*(All 25 tests pass across parser, database, and API suites).*

---

## 10. FastAPI REST API (Browse, Search & Version Comparison)

The system provides a production-grade REST API built with FastAPI, Pydantic, and SQLAlchemy ORM.

### Starting the Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Interactive OpenAPI Swagger docs are available at `http://localhost:8000/docs`.

### API Endpoints & Example cURL Commands

#### 1. Health Check
Confirm that the application is running and the database connection is healthy.
```bash
curl -X GET "http://localhost:8000/health"
```
**Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "app_name": "Tri9T-CT200-Document-Intelligence"
}
```

#### 2. List Document Versions
Returns all available versions in chronological order with ingestion timestamp, file hash, page count, and node count.
```bash
curl -X GET "http://localhost:8000/api/documents/ct200_manual/versions"
```
**Response**:
```json
[
  {
    "id": "ver_ct200_manual_v1",
    "version_number": "v1",
    "source_filename": "data/ct200_manual.pdf",
    "file_hash": "62bfad94ffc859d9c222ffc322b72fec1ad7c32bfcb432e1858a221f7bcbf6e1",
    "ingested_at": "2026-10-22T23:54:12",
    "total_pages": 6,
    "total_nodes": 50,
    "root_node_id": "v1_doc_root"
  },
  {
    "id": "ver_ct200_manual_v2",
    "version_number": "v2",
    "source_filename": "data/ct200_manual_v2.pdf",
    "file_hash": "2f40c76dbb3e0fcb243be4df8344e78a666dd9cf16b0dfa9d8fa79247c43315a",
    "ingested_at": "2026-10-22T23:54:13",
    "total_pages": 7,
    "total_nodes": 52,
    "root_node_id": "v2_doc_root"
  }
]
```

#### 3. List Top-Level Sections
Return top-level sections (1 through 8) for a requested version (`?version=1` or `?version=v1`). If `version` is omitted, defaults to the latest version (`v2`).
```bash
curl -X GET "http://localhost:8000/api/documents/ct200_manual/sections?version=1"
```
**Response**:
```json
[
  {
    "id": "v1_sec_1",
    "logical_key": "sec_1",
    "heading": "1. Device Overview",
    "section_number": "1",
    "node_type": "section",
    "reading_order_index": 1,
    "page_start": 1,
    "page_end": 1,
    "content_hash": "a1c51db3f05dbd4e4142f3ae10433efcf9321e102f6ae45ea9bb0c47fc7e1cb4"
  },
  ...
]
```

#### 4. Retrieve a Specific Node
Fetches a node's complete stored content, content hash, version details, parent reference, ordered children, page references, and structured table data. Guarantees exact historical version content.
```bash
# Retrieve battery specification in V1 (shows 300 cycles, 15%)
curl -X GET "http://localhost:8000/api/nodes/v1_sec_2_1_1_1_p_5"

# Retrieve structured specifications table in V1
curl -X GET "http://localhost:8000/api/nodes/v1_sec_2_1_tbl_1"
```
**Response (Table Node)**:
```json
{
  "id": "v1_sec_2_1_tbl_1",
  "version_number": "v1",
  "logical_key": "sec_2_1_tbl_1",
  "node_type": "table",
  "title_or_text": "[Table with 7 rows, 2 columns]",
  "section_number": "2.1",
  "hierarchy_level": 2,
  "parent_id": "v1_sec_2_1",
  "reading_order_index": 7,
  "page_start": 2,
  "page_end": 2,
  "content_hash": "c0443425b041cf237a7b8e19ff5fb537683fc6e4b9f31c26f634ee0b3b429188",
  "children_ids": [],
  "table_data": {
    "headers": ["Parameter", "Value"],
    "rows": [
      ["Pressure Measurement Range", "0 to 299 mmHg"],
      ["Pulse Rate Range", "40 to 180 beats/min"],
      ["Pressure Accuracy", "±3 mmHg"],
      ["Pulse Rate Accuracy", "±5% of reading"],
      ["Inflation", "Automatic by micro rolling pump"],
      ["Deflation", "Automatic electronic control valve"],
      ["Operating Conditions", "+10°C to +40°C, 15% to 85% RH"]
    ]
  }
}
```

#### 5. Search Document
Search headings and body text with safe parameterized query building, snippets with context, node-type filtering (`section`, `paragraph`, `table`, `list`), version filtering, and pagination.
```bash
# Search for oscillometric technology
curl -X GET "http://localhost:8000/api/search?q=oscillometric&limit=5&offset=0"

# Search for Error Codes inside tables in Version 1
curl -X GET "http://localhost:8000/api/search?q=cuff&type=table&version=1"
```
**Response**:
```json
{
  "query": "oscillometric",
  "version_filter": null,
  "type_filter": null,
  "total_matches": 2,
  "limit": 5,
  "offset": 0,
  "results": [
    {
      "id": "v1_sec_1_1_p_2",
      "version_number": "v1",
      "logical_key": "sec_1_1_p_2",
      "node_type": "paragraph",
      "title_or_text": "The CT-200 utilizes the oscillometric method of blood pressure measurement...",
      "section_number": "1.1",
      "page_start": 1,
      "page_end": 1,
      "snippet": "...The CT-200 utilizes the oscillometric method of blood pressure measurement..."
    }
  ]
}
```

#### 6. Compare Node Status Across Versions
Compare a version-specific node with its counterpart in a target version (defaults to latest version if omitted). Returns status (`unchanged`, `modified`, `removed`, or `ambiguous`), node IDs, hashes, and a unified diff summary.
```bash
# Compare Section 2.1.1.1 (Modified in V2: 300 cycles -> 250 cycles)
curl -X GET "http://localhost:8000/api/nodes/v1_sec_2_1_1_1/changes?target_version=2"

# Compare Section 5.3 (Added in V2; comparing V2 -> V1 reports removed in V1)
curl -X GET "http://localhost:8000/api/nodes/v2_sec_5_3/changes?target_version=1"
```
**Response (Modified Node)**:
```json
{
  "source_version_number": "v1",
  "target_version_number": "v2",
  "source_node_id": "v1_sec_2_1_1_1",
  "target_node_id": "v2_sec_2_1_1_1",
  "logical_key": "sec_2_1_1_1",
  "status": "modified",
  "source_content_hash": "fc240aa415f36e4f3a9e64e12ec6fe5ff9d10e5aa232a5ffbe365510619a32c2",
  "target_content_hash": "2ff1a8d052a201b1e5fead848b1d9bf5be8447814b74542ee4ee0ee711149e32",
  "diff_summary": "--- v1\n+++ v2\n@@ -1,4 +1,4 @@\n-2.1.1.1. Battery Life Under Typical Use (V1: 300 measurement cycles)\n+2.1.1.1. Battery Life Under Typical Use (V2: 250 measurement cycles)"
}
```

#### 7. Create Named Selection (Version-Pinned)
Creates a named selection containing specific document nodes pinned to their exact document version and content hash. Selections will later be used for QA test case generation.
```bash
curl -X POST "http://localhost:8000/api/selections" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Inflation Safety Tests",
    "description": "Tests for the cuff inflation sequence and pressure safety thresholds",
    "items": [
      {"node_id": "v1_sec_3_2"},
      {"node_id": "v1_sec_2_1_tbl_1"}
    ]
  }'
```
**Response (201 Created)**:
```json
{
  "id": "sel_a1b2c3d4e5f6",
  "name": "Inflation Safety Tests",
  "description": "Tests for the cuff inflation sequence and pressure safety thresholds",
  "document_id": "ct200_manual",
  "version_id": "ct200_manual_v1",
  "version_number": "v1",
  "created_at": "2026-10-23T00:15:00",
  "updated_at": "2026-10-23T00:15:00",
  "total_items": 2,
  "items": [
    {
      "node_id": "v1_sec_3_2",
      "version_id": "ct200_manual_v1",
      "version_number": "v1",
      "logical_key": "sec_3.2",
      "title_or_text": "3.2. Taking a Measurement...",
      "node_type": "section",
      "section_number": "3.2",
      "hierarchy_level": 2,
      "content_hash": "b2f67623...",
      "page_start": 3,
      "page_end": 3,
      "parent_id": "v1_sec_3",
      "parent_details": {
        "id": "v1_sec_3",
        "logical_key": "sec_3",
        "title_or_text": "3. Operating Instructions",
        "section_number": "3",
        "node_type": "section"
      },
      "table_data": null,
      "order_index": 0
    },
    {
      "node_id": "v1_sec_2_1_tbl_1",
      "version_id": "ct200_manual_v1",
      "version_number": "v1",
      "logical_key": "sec_2.1_tbl_1",
      "title_or_text": "[Table with 7 rows, 2 columns]",
      "node_type": "table",
      "section_number": "2.1",
      "hierarchy_level": 2,
      "content_hash": "c0443425...",
      "page_start": 2,
      "page_end": 2,
      "parent_id": "v1_sec_2_1",
      "parent_details": null,
      "table_data": {
        "headers": ["Parameter", "Value"],
        "rows": [["Pressure Measurement Range", "0 to 299 mmHg"], ...]
      },
      "order_index": 1
    }
  ]
}
```

#### 8. Retrieve Selection
Retrieves selection metadata and all items with their exact version-pinned text content and parent hierarchy.
```bash
curl -X GET "http://localhost:8000/api/selections/sel_a1b2c3d4e5f6"
```

#### 9. List Selections
Lists existing selections with pagination and ordering.
```bash
curl -X GET "http://localhost:8000/api/selections?limit=10&offset=0"
```

#### 10. Generate QA Test Cases (LLM-Powered)
Reconstructs exact version-pinned source text from the selection, validates grounding, and generates 3–5 structured, verifiable QA test cases.
```bash
curl -X POST "http://localhost:8000/api/selections/sel_a1b2c3d4e5f6/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "force_regenerate": false
  }'
```
**Response (200 OK)**:
```json
{
  "generation_id": "gen_f8c12a39d4e5",
  "selection_id": "sel_a1b2c3d4e5f6",
  "document_id": "ct200_manual",
  "version_id": "ct200_manual_v1",
  "version_number": "v1",
  "provider": "mock",
  "model": "mock-ct200-qa-v1",
  "prompt_version": "1.0.0",
  "input_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "generated_at": "2026-10-23T00:25:00",
  "cached": false,
  "validation_status": "valid",
  "total_test_cases": 3,
  "test_cases": [
    {
      "id": "TC-CT200-BAT-001",
      "title": "V1 Typical Battery Life and Low-Battery Threshold Verification",
      "objective": "Verify that typical battery life delivers approximately 300 measurement cycles and triggers low-battery indicator below 15%.",
      "preconditions": [
        "CardioTrack CT-200 unit installed with fresh AAA alkaline batteries",
        "Simulated measurement rig connected to verify cycle count"
      ],
      "test_steps": [
        "Execute consecutive simulated measurement cycles (3 per day equivalent).",
        "Monitor battery voltage degradation until 300 cycles are reached.",
        "Discharge battery cell voltage to 15% remaining capacity."
      ],
      "expected_result": "The device completes 300 measurement cycles under normal load, and low-battery warning icon appears exactly when capacity drops below 15%.",
      "priority": "high",
      "source_node_ids": ["v1_sec_2_1_1_1_p_5"],
      "source_version_identifiers": ["v1"],
      "source_content_hashes": {
        "v1_sec_2_1_1_1_p_5": "fc240aa415f36e4f3a9e64e12ec6fe5ff9d10e5aa232a5ffbe365510619a32c2"
      },
      "requirement_coverage": "Section 2.1.1.1 (Battery Life Under Typical Use - V1)",
      "ambiguities_or_flags": null
    }
  ],
  "source_node_ids": ["v1_sec_2_1_1_1_p_5", "v1_sec_2_1_tbl_1"],
  "source_text_snapshots": [
    {
      "node_id": "v1_sec_2_1_1_1_p_5",
      "logical_key": "sec_2.1.1.1_p_5",
      "content_hash": "fc240aa415f36e4f3a9e64e12ec6fe5ff9d10e5aa232a5ffbe365510619a32c2",
      "title_or_text": "Battery life: under typical use (3 measurements per day)..."
    }
  ]
}
```

#### 11. Retrieve Generated Test Cases
Retrieve historical test generation suites for a selection or by generation ID from the persistent document store:
```bash
# List all test generation runs for a selection
curl -X GET "http://localhost:8000/api/selections/sel_a1b2c3d4e5f6/generations"

# Retrieve specific immutable generation record with embedded current staleness report
curl -X GET "http://localhost:8000/api/generations/gen_f8c12a39d4e5"
```

**Generation Policies & Architecture**:
- **Strict Grounding & Traceability**: Each test case specifies an actionable title, objective, preconditions, test steps, measurable expected result, and exact `source_node_ids`. All `source_node_ids` must belong strictly to the selection (invented or hallucinated node IDs are rejected).
- **Exact Numeric Preservation**: Numerical values (e.g. 300 cycles / 15% in V1 vs 250 cycles / 10% in V2) and units are preserved with complete fidelity.
- **Bounded Single Repair Strategy**: If the LLM produces malformed JSON or validation errors, exactly 1 repair attempt is triggered with validation feedback. If the repair fails, a safe HTTP 502 error is returned without exposing API keys or hanging indefinitely.
- **Duplicate-Generation Caching**: When `force_regenerate=false` (default), the service calculates an SHA-256 `input_hash` of the selection ID, version ID, prompt version, model, and source text snapshots. If a matching successful generation exists, it returns immediately with `cached: true`.
- **Immutable JSON Document Store**: Generated records, along with immutable source text snapshots, are persisted in `generated/test_generations/gen_{id}.json` for lifelong auditability.

---

## 12. Staleness Detection, Impact Analysis & Test Case Retrieval

When product requirements and technical manuals evolve across versions (e.g. from Version 1 to Version 2), previously generated test cases can become obsolete, inaccurate, or hazardous. The **Staleness Detection Engine** (`app/staleness.py`) analyzes persisted test generation records against target document versions, evaluating granular source-node changes and computing per-test-case staleness statuses without modifying or regenerating historical records.

### Staleness Status Taxonomy

| Status | Definition | Criteria |
|---|---|---|
| `current` | Up-to-date | All referenced source nodes are confidently matched in the latest version and their content hashes are identical. |
| `stale` | Outdated specification | At least one referenced source node was modified or removed in the latest version. |
| `review_required` | Ambiguous or incomplete | Source logical matching is ambiguous, required historical metadata is missing, or comparison cannot be performed reliably. |
| `unknown` | Target version missing | No target document version exists in the database to compare against. |

### High-Impact Specification Change Detection
The staleness engine incorporates rule-based heuristics that analyze unified diffs to detect potential high-impact clinical/engineering changes:
- **Numerical Thresholds & Values**: e.g., inflation increment changed from `40 mmHg` to `30 mmHg`, battery cycles reduced from `300` to `250`.
- **Units of Measure**: `mmHg`, `bpm`, `seconds`, `%`, `°C`.
- **Timing Limits**: Auto-deflation response time tightened from `2.0s` to `1.5s`.
- **Inequalities & Comparisons**: `<`, `>`, `≤`, `≥`, `exceeds`, `below`, `minimum`, `maximum`.
- **Negations & Safety Constraints**: `cannot`, `must not`, `never`, `warning`, `danger`, `abort`, `caution`.

> **Note**: Highlighted changes are flagged as *potential high-impact specification changes* to alert QA engineers; the system does not claim to establish clinical safety significance automatically.

### End-to-End V1-to-V2 Staleness Workflow

Here is the complete end-to-end workflow demonstrating how V1 test cases are evaluated against V2:

#### Step 1: Create a V1 Selection & Generate Test Cases
Create a selection pinned to V1 nodes (Section 3.2 Cuff Inflation and Section 2.1.1.1 Battery Life) and generate QA test cases:
```bash
# 1. Create selection pinned to V1
curl -X POST "http://localhost:8000/api/selections" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "V1 Core Verification Suite",
    "description": "Inflation sequence and battery specifications from V1 manual",
    "items": [
      {"node_id": "v1_sec_3_2"},
      {"node_id": "v1_sec_2_1_1_1_p_5"}
    ]
  }'

# 2. Generate QA test cases (returns generation_id, e.g. gen_e1a2b3c4d5f6)
curl -X POST "http://localhost:8000/api/selections/sel_YOUR_ID/generate" \
  -H "Content-Type: application/json" \
  -d '{"force_regenerate": false}'
```

#### Step 2: Ingest Version 2 of the Manual
When Version 2 (`data/ct200_manual_v2.pdf`) is ingested, the system populates V2 nodes without overwriting any V1 records or historical test cases:
```bash
python scripts/ingest_documents.py
```

#### Step 3: Check Generation Staleness Assessment
Query the staleness endpoint for the generation to see which test cases became stale:
```bash
curl -X GET "http://localhost:8000/api/generations/gen_e1a2b3c4d5f6/staleness"
```
**Example Response**:
```json
{
  "generation_id": "gen_e1a2b3c4d5f6",
  "selection_id": "sel_YOUR_ID",
  "source_version_number": "v1",
  "target_version_number": "v2",
  "evaluated_at": "2026-10-23T00:30:00",
  "summary": {
    "total_test_cases": 3,
    "current": 1,
    "stale": 2,
    "review_required": 0,
    "unknown": 0
  },
  "test_case_results": [
    {
      "test_case_id": "TC-CT200-BAT-001",
      "title": "V1 Typical Battery Life and Low-Battery Threshold Verification",
      "status": "stale",
      "reason": "Referenced node v1_sec_2_1_1_1_p_5 was modified in target version v2 (content hash changed from fc240aa4... to 2ff1a8d0...).",
      "referenced_node_ids": ["v1_sec_2_1_1_1_p_5"],
      "impact_notes": [
        "Potential high-impact change detected in node v1_sec_2_1_1_1_p_5: Numeric threshold/value change detected: - Battery life: under typical use (3 measurements per day), the device operates for approximately 300 measurement cycles. / + Battery life: under typical use (3 measurements per day), the device operates for approximately 250 measurement cycles.",
        "Potential high-impact change detected in node v1_sec_2_1_1_1_p_5: Unit of measurement modified: - A low-battery indicator appears on the display when battery capacity drops below 15%. / + A low-battery indicator appears on the display when battery capacity drops below 10%."
      ],
      "diff_summaries": {
        "v1_sec_2_1_1_1_p_5": "--- v1 (v1_sec_2_1_1_1_p_5)\n+++ v2 (v2_sec_2_1_1_1_p_5)\n@@ -1,4 +1,5 @@\n-Battery life: under typical use (3 measurements per day), the device operates for approximately 300 measurement cycles.\n-A low-battery indicator appears on the display when battery capacity drops below 15%.\n+Battery life: under typical use (3 measurements per day), the device operates for approximately 250 measurement cycles.\n+A low-battery indicator appears on the display when battery capacity drops below 10%.\n+Note: Battery life specifications were revised based on extended field testing under variable temperature conditions."
      }
    },
    {
      "test_case_id": "TC-CT200-INF-001",
      "title": "Cuff Inflation Increment Step Verification",
      "status": "stale",
      "reason": "Referenced node v1_sec_3_2 was modified in target version v2 (content hash changed).",
      "referenced_node_ids": ["v1_sec_3_2"],
      "impact_notes": [
        "Potential high-impact change detected in node v1_sec_3_2: Numeric threshold/value change detected: - The cuff inflates in 40 mmHg increments / + The cuff inflates in 30 mmHg increments"
      ],
      "diff_summaries": {
        "v1_sec_3_2": "--- v1 (v1_sec_3_2)\n+++ v2 (v2_sec_3_2)\n@@ -1,5 +1,5 @@\n-3.2 Cuff Inflation Sequence\n-The cuff inflates in 40 mmHg increments...\n+3.2 Cuff Inflation Sequence\n+The cuff inflates in 30 mmHg increments..."
      }
    }
  ],
  "node_comparisons": [
    {
      "source_node_id": "v1_sec_2_1_1_1_p_5",
      "target_node_id": "v2_sec_2_1_1_1_p_5",
      "logical_key": "sec_2.1.1.1_p_5",
      "status": "modified",
      "source_hash": "fc240aa415f36e4f3a9e64e12ec6fe5ff9d10e5aa232a5ffbe365510619a32c2",
      "target_hash": "2ff1a8d052a201b1e5fead848b1d9bf5be8447814b74542ee4ee0ee711149e32",
      "has_diff": true,
      "diff_summary": "--- v1\n+++ v2\n@@ ...",
      "impact_notes": [
        "Numeric threshold/value change detected: 300 -> 250 cycles",
        "Unit/threshold modified: 15% -> 10%"
      ]
    }
  ]
}
```

#### Step 4: Aggregate Staleness for a Selection
View aggregate staleness metrics across all generations for a selection:
```bash
curl -X GET "http://localhost:8000/api/selections/sel_YOUR_ID/staleness"
```

#### Step 5: Trace Test Cases Linked to a Specific Node
Lookup all generated test cases originating from a specific node ID, along with their current staleness status:
```bash
curl -X GET "http://localhost:8000/api/nodes/v1_sec_2_1_1_1_p_5/test-cases"
```
**Example Response**:
```json
{
  "node_id": "v1_sec_2_1_1_1_p_5",
  "document_id": "ct200_manual",
  "version_number": "v1",
  "logical_key": "sec_2.1.1.1_p_5",
  "total_test_cases": 1,
  "test_cases": [
    {
      "test_case_id": "TC-CT200-BAT-001",
      "title": "V1 Typical Battery Life and Low-Battery Threshold Verification",
      "objective": "Verify that typical battery life delivers approximately 300 measurement cycles...",
      "priority": "high",
      "generation_id": "gen_e1a2b3c4d5f6",
      "selection_id": "sel_YOUR_ID",
      "source_version_number": "v1",
      "staleness_status": "stale",
      "staleness_reason": "Referenced node v1_sec_2_1_1_1_p_5 was modified in target version v2."
    }
  ]
}
```

---

## 13. Automated Test Suite

The test suite consists of **53 comprehensive automated tests** across parsing, database versioning, REST API, named selections, LLM generation, and cross-version staleness evaluation:

```bash
# Run complete test suite
pytest -v
```

### Module Breakdown
- **`tests/test_parser.py` (7 tests)**: Structural anomaly handling, non-sequential numbering (3.4 before 3.3), missing intermediate subsections (2.1.1.1), table column/row extraction, cross-page text stitching, and tree validation.
- **`tests/test_database.py` (8 tests)**: V1/V2 ingestion, immutable preservation of V1, unchanged/modified node detection, added/removed nodes, hash deduplication, and transactional rollback.
- **`tests/test_api.py` (10 tests)**: `/health` DB connectivity check, version listing, section listing with version defaults, exact versioned node retrieval, search across headings/body with type/version filters, cross-version change comparison, removed/ambiguous node handling, and input validation / edge cases.
- **`tests/test_selections.py` (9 tests)**: Named selection creation/retrieval, exact version-pinned content resolution (V1 300 cycles vs V2 250 cycles), post-ingestion immutability (V2 ingestion preserves pre-existing V1 selection), 404 on unknown node IDs, 400 on empty selections/invalid names, duplicate node rejection, mixed-version rejection, transaction rollback, pagination, and 404 on missing selection IDs.
- **`tests/test_generation.py` (9 tests)**: LLM test case generation from selection, strict version-pinned grounding (V1 300 cycles vs V2 250 cycles), duplicate generation caching (`cached=True`) vs `force_regenerate=True`, 404 on unknown selections, rejection of hallucinated source node IDs, rejection of out-of-bounds test case counts (<3 or >5), bounded single repair recovery on malformed output, safe 502 handling on repair exhaustion, and JSON document store auditability with immutable source text snapshots.
- **`tests/test_staleness.py` (10 tests)**:
  1. `test_unchanged_v1_section_reported_current_after_v2_ingestion`: Verifies unchanged sections (e.g. Section 1.1) evaluate to `current` with `diff_summary=None`.
  2. `test_section_3_2_inflation_increment_change`: Verifies cuff inflation change from 40 mmHg to 30 mmHg triggers `stale` with high-impact numeric change detected.
  3. `test_battery_requirement_detected_changes`: Verifies battery specification change from 300 to 250 cycles and 15% to 10% triggers `stale` with unit/threshold detection.
  4. `test_e3_auto_deflation_requirement_detected_changes`: Verifies E3 table change from 2.0s to 1.5s is detected as `stale` with timing limit alert.
  5. `test_removed_and_ambiguous_source_nodes_not_marked_current`: Verifies deleted nodes are flagged `stale` and ambiguous multi-matches flagged `review_required`.
  6. `test_mixed_granularity_one_stale_one_current`: Proves per-test-case granularity where one test is `current` while another in the same generation is `stale`.
  7. `test_multi_node_reference_combined_status`: Proves combined status logic across multiple nodes (unchanged + modified = stale; unchanged + ambiguous = review_required).
  8. `test_missing_historical_metadata_produces_review_required`: Ensures corrupted or incomplete historical snapshots produce `review_required` rather than false `current`.
  9. `test_staleness_retrieval_endpoints`: Validates `/api/selections/{id}/generations`, `/api/generations/{id}`, `/api/generations/{id}/staleness`, `/api/selections/{id}/staleness`, and `/api/nodes/{id}/test-cases`.
  10. `test_deterministic_repeated_assessments`: Confirms multiple consecutive staleness requests return identical, deterministic results without mutating data.

---

## 14. Frontend Application (React + Vite + TypeScript + Tailwind CSS)

The project includes an enterprise document-intelligence dashboard located in `frontend/`.

### Tech Stack
- **Framework**: React 19 + Vite
- **Language**: TypeScript
- **Styling**: Tailwind CSS v3
- **Icons**: Lucide React
- **Architecture**: Modular layout with persistent sidebar, typed API client, and live backend connection badge

### Frontend Setup & Running Instructions

#### Prerequisites
- Node.js v18 or higher (tested on Node v22)
- npm v9 or higher

#### 1. Navigate to the Frontend Directory
```bash
cd frontend
```

#### 2. Install Frontend Dependencies
```bash
npm install
```

#### 3. Configure Backend Base URL (Optional)
By default, the frontend automatically connects to `http://127.0.0.1:8000`. To customize the target backend, create or edit `frontend/.env`:
```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

#### 4. Start the Development Server
```bash
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

#### 5. Build for Production
To validate and compile the production bundle:
```bash
npm run build
```
*(Artifacts compile cleanly to `frontend/dist/` in ~2 seconds).*

### Dashboard Features
- **Live Backend Connection Banner**: Real-time health probe confirming SQLite and FastAPI status.
- **Enterprise Stat Cards**: Document version counts, extracted node hierarchy stats (102 nodes), active selections, and staleness engine status.
- **Dual Version Inspection**: Side-by-side metadata for Version 1 and Version 2 with SHA-256 file hashes.
- **Specification Drift Matrix**: Visual table highlighting critical requirements differences (cuff increment 40 $\rightarrow$ 30 mmHg, battery 300 $\rightarrow$ 250 cycles, E3 response 2.0s $\rightarrow$ 1.5s, E6 Bluetooth error addition, and Section 5.3 Data Export addition).
- **Document Sections Hierarchy**: Live list of top-level sections with reading order and content hashes.
- **Developer Quicklinks**: Direct link to the backend's interactive Swagger UI documentation at `http://127.0.0.1:8000/docs`.




