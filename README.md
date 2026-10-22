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
