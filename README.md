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
*(All 15 tests pass).*


