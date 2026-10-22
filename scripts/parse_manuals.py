import os
import sys
import json
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

from app.parser import CT200PDFParser
from app.validator import DocumentTreeValidator

def main():
    print("=" * 60)
    print("Tri9T-CT200-Document-Intelligence: PDF Parser Pipeline")
    print("=" * 60)

    generated_dir = WORKSPACE_ROOT / "generated"
    generated_dir.mkdir(exist_ok=True)

    data_dir = WORKSPACE_ROOT / "data"
    targets = [
        ("v1", data_dir / "ct200_manual.pdf", generated_dir / "ct200_manual_v1_tree.json"),
        ("v2", data_dir / "ct200_manual_v2.pdf", generated_dir / "ct200_manual_v2_tree.json")
    ]

    parser = CT200PDFParser()
    validation_summary = {}

    for version, pdf_path, output_json in targets:
        print(f"\n[+] Parsing {version.upper()}: {pdf_path}")
        if not pdf_path.exists():
            print(f"[-] ERROR: File does not exist: {pdf_path}")
            sys.exit(1)

        tree = parser.parse(str(pdf_path), version)
        print(f"    - Extracted {len(tree.nodes)} total nodes across {tree.total_pages} pages")
        print(f"    - Physical reading order contains {len(tree.reading_order)} elements")

        # Run validation
        val_result = DocumentTreeValidator.validate(tree, raise_on_error=False)
        print(f"    - Validation Status: {'PASSED' if val_result.is_valid else 'FAILED'}")
        print(f"    - Errors: {len(val_result.errors)}, Warnings: {len(val_result.warnings)}")
        print(f"    - Stats: {val_result.stats}")

        if not val_result.is_valid:
            print("[-] FATAL VALIDATION ERRORS:")
            for err in val_result.errors:
                print(f"    * {err}")
            sys.exit(1)

        # Write tree JSON
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(tree.model_dump(), f, indent=2, ensure_ascii=False)
        print(f"    - Saved tree JSON to: {output_json}")

        validation_summary[version] = {
            "source_file": str(pdf_path),
            "output_file": str(output_json),
            "is_valid": val_result.is_valid,
            "errors": val_result.errors,
            "warnings": val_result.warnings,
            "stats": val_result.stats
        }

    # Write validation summary
    val_summary_path = generated_dir / "validation_report.json"
    with open(val_summary_path, "w", encoding="utf-8") as f:
        json.dump(validation_summary, f, indent=2, ensure_ascii=False)
    print(f"\n[+] Validation report saved to: {val_summary_path}")
    print("\n[+] Parser pipeline completed successfully!")

if __name__ == "__main__":
    main()
