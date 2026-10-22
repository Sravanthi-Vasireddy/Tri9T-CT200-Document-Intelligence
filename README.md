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

**Selection Integrity & Policies**:
- **Single-Version Pinning**: All nodes in a selection must belong to the exact same document version. Mixed-version selections are rejected with `HTTP 400 Bad Request`.
- **Deduplication**: Duplicate node IDs in the request are rejected with `HTTP 400 Bad Request` to prevent ambiguous ordering.
- **Historical Immutability**: Selections snapshot the exact node content and content hash at creation time. Ingesting subsequent versions (e.g., V2) will never modify, delete, or repoint existing V1 selection items.

---

## 11. Automated Test Suite

The test suite consists of 34 comprehensive tests across parsing, database versioning, REST API, and named selection layers:
```bash
pytest -v
```

- **`tests/test_parser.py` (7 tests)**: Structural anomaly handling, non-sequential numbering (3.4 before 3.3), missing intermediate subsections (2.1.1.1), table column/row extraction, cross-page stitching, and tree validation.
- **`tests/test_database.py` (8 tests)**: V1/V2 ingestion, immutable preservation of V1, unchanged/modified node detection, added/removed nodes, hash deduplication, and transactional rollback.
- **`tests/test_api.py` (10 tests)**: `/health` DB connectivity check, version listing, section listing with version defaults, exact versioned node retrieval, search across headings/body with type/version filters, cross-version change comparison, removed/ambiguous node handling, and input validation / edge cases.
- **`tests/test_selections.py` (9 tests)**: Named selection creation/retrieval, exact version-pinned content resolution (V1 300 cycles vs V2 250 cycles), post-ingestion immutability (V2 ingestion preserves pre-existing V1 selection), 404 on unknown node IDs, 400 on empty selections/invalid names, duplicate node rejection, mixed-version rejection, transaction rollback, pagination, and 404 on missing selection IDs.


