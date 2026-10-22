import os
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from app.database import init_db, SessionLocal
from app.ingestion import IngestionService


def main():
    print("=" * 65)
    print("Tri9T-CT200-Document-Intelligence: Ingestion & Versioning CLI")
    print("=" * 65)

    # 1. Initialize SQLite Database Tables
    init_db()
    db = SessionLocal()

    data_dir = WORKSPACE_ROOT / "data"
    targets = [
        ("v1", data_dir / "ct200_manual.pdf"),
        ("v2", data_dir / "ct200_manual_v2.pdf")
    ]

    try:
        for version_number, pdf_path in targets:
            print(f"\n[+] Ingesting Version '{version_number}': {pdf_path.name}")
            if not pdf_path.exists():
                print(f"[-] ERROR: File does not exist: {pdf_path}")
                sys.exit(1)

            summary = IngestionService.ingest_pdf(
                pdf_path=str(pdf_path),
                version_number=version_number,
                document_id="ct200_manual",
                db=db
            )

            if summary.already_ingested:
                print(f"    * Notice: Version already ingested! (file_hash: {summary.file_hash[:12]}...)")
                print(f"    * Returned existing record: {summary.version_id}")
            else:
                print(f"    * Ingestion Successful: {summary.version_id}")
                print(f"    * File Hash: {summary.file_hash[:16]}...")
                print(f"    * Total Nodes Stored: {summary.total_nodes} across {summary.total_pages} pages")

            if version_number == "v2" and summary.diff_details:
                print(f"    * Cross-Version Comparison (vs previous version):")
                print(f"        - Unchanged Nodes: {summary.unchanged_nodes}")
                print(f"        - Changed Nodes:   {summary.changed_nodes}")
                print(f"        - Added Nodes:     {summary.added_nodes}")
                print(f"        - Removed Nodes:   {summary.removed_nodes}")
                print(f"        - Ambiguous:       {summary.ambiguous_matches}")

        print("\n" + "=" * 65)
        print("Ingestion Pipeline Completed Successfully!")
        print("=" * 65)

    finally:
        db.close()


if __name__ == "__main__":
    main()
