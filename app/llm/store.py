import os
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger("doc_intelligence.store")


class JSONTestStore:
    """
    Manages persistent JSON document storage for generated QA test suites.
    Outputs are stored under generated/test_generations/ (or configured JSON_STORE_DIR).
    """

    def __init__(self, base_dir: Optional[str] = None):
        if not base_dir:
            base_dir = os.getenv("JSON_STORE_DIR", "./generated")
        self.store_dir = Path(base_dir) / "test_generations"
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, generation_id: str) -> Path:
        filename = f"{generation_id}.json" if generation_id.startswith("gen_") else f"gen_{generation_id}.json"
        return self.store_dir / filename

    def save_generation(self, record: Dict[str, Any]) -> str:
        """Persists a generation record as an immutable JSON document."""
        generation_id = record["generation_id"]
        path = self._file_path(generation_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved generation '{generation_id}' to {path}")
        return str(path)

    def get_generation(self, generation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a generation record by its unique ID."""
        path = self._file_path(generation_id)
        if not path.exists():
            alt = self.store_dir / f"gen_{generation_id}.json"
            if alt.exists():
                path = alt
            else:
                return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read generation file {path}: {e}")
            return None

    def find_by_input_hash(self, selection_id: str, input_hash: str) -> Optional[Dict[str, Any]]:
        """
        Locates a pre-existing successful generation matching the selection and identical input hash.
        Used for deterministic duplicate-generation caching.
        """
        for file in self.store_dir.glob("gen_*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                    if (
                        rec.get("selection_id") == selection_id
                        and rec.get("input_hash") == input_hash
                        and rec.get("generation_status") == "success"
                    ):
                        return rec
            except Exception:
                continue
        return None

    def list_by_selection(self, selection_id: str) -> List[Dict[str, Any]]:
        """Lists all generations created for a given selection ID, sorted newest first."""
        records = []
        for file in self.store_dir.glob("gen_*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                    if rec.get("selection_id") == selection_id:
                        records.append(rec)
            except Exception:
                continue
        records.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
        return records
