import os
import json
import uuid
import hashlib
import logging
import datetime
from typing import Dict, Any, Optional, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Selection, SelectionItem, DocumentNodeModel
from app.schemas import (
    GenerationRequest,
    GenerationRecordResponse,
    GeneratedTestCase,
    LLMTestCasesPayload,
    SourceTextSnapshot,
    PriorityEnum
)
from app.llm.prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
    build_repair_prompt
)
from app.llm.store import JSONTestStore
from app.llm.provider import BaseLLMProvider, get_llm_provider, LLMProviderError

logger = logging.getLogger("doc_intelligence.generator")


class LLMValidationError(Exception):
    """Exception raised when LLM output violates schema or grounding validation."""
    pass


class QATestGeneratorService:
    """
    Orchestrates LLM QA test generation from version-pinned document selections:
    - Reconstructs exact versioned source text.
    - Grounding validation and unknown node reference rejection.
    - Bounded single repair attempt on formatting failures.
    - Deduplication caching and immutable JSON persistence.
    """

    def __init__(self, store: Optional[JSONTestStore] = None):
        self.store = store or JSONTestStore()

    @staticmethod
    def compute_input_hash(
        selection_id: str,
        version_id: str,
        prompt_version: str,
        model_name: str,
        items: List[SelectionItem]
    ) -> str:
        """Computes a deterministic hash of all generation inputs."""
        sorted_nodes = sorted(items, key=lambda x: x.order_index)
        payload = f"{selection_id}:{version_id}:{prompt_version}:{model_name}:" + ":".join(
            f"{it.node_id}_{it.content_hash}" for it in sorted_nodes
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def validate_test_cases_payload(
        self,
        raw_text: str,
        valid_node_ids: List[str],
        version_number: str,
        content_hashes: Dict[str, str]
    ) -> Tuple[List[GeneratedTestCase], Optional[str]]:
        """
        Validates raw LLM response text against Pydantic schema and grounding invariants.
        Returns (validated_cases, error_message).
        """
        # Clean any accidental markdown code fences
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            return [], f"Malformed JSON: {str(e)}"

        if not isinstance(data, dict) or "test_cases" not in data:
            return [], "Root object must be a dictionary with a 'test_cases' list key."

        raw_cases = data["test_cases"]
        if not isinstance(raw_cases, list):
            return [], "'test_cases' must be a list."

        if len(raw_cases) < 3 or len(raw_cases) > 5:
            return [], f"Count of test cases must be between 3 and 5 (received {len(raw_cases)})."

        validated = []
        valid_set = set(valid_node_ids)

        for idx, tc in enumerate(raw_cases):
            if not isinstance(tc, dict):
                return [], f"Test case at index {idx} must be a dictionary."

            # Verify source node IDs
            tc_node_ids = tc.get("source_node_ids", [])
            if not isinstance(tc_node_ids, list) or len(tc_node_ids) == 0:
                return [], f"Test case '{tc.get('id', idx)}' must specify at least one non-empty source_node_id."

            invalid_refs = [nid for nid in tc_node_ids if nid not in valid_set]
            if invalid_refs:
                return [], (
                    f"Test case '{tc.get('id', idx)}' references unknown/unselected source node(s): {invalid_refs}. "
                    f"Must strictly reference provided selection node IDs: {valid_node_ids}."
                )

            # Ensure version and content hash traceability
            tc["source_version_identifiers"] = [version_number]
            tc["source_content_hashes"] = {nid: content_hashes.get(nid, "") for nid in tc_node_ids}

            # Normalize priority to lowercase
            if "priority" in tc and isinstance(tc["priority"], str):
                tc["priority"] = tc["priority"].strip().lower()

            try:
                model_tc = GeneratedTestCase(**tc)
                validated.append(model_tc)
            except Exception as e:
                return [], f"Validation error in test case '{tc.get('id', idx)}': {str(e)}"

        return validated, None

    def generate_for_selection(
        self,
        selection_id: str,
        force_regenerate: bool = False,
        additional_instructions: Optional[str] = None,
        db: Optional[Session] = None,
        provider: Optional[BaseLLMProvider] = None
    ) -> GenerationRecordResponse:
        """
        Executes end-to-end grounded QA test generation for a version-pinned selection.
        """
        if not db:
            raise ValueError("Database session is required.")

        llm = provider or get_llm_provider()

        # 1. Fetch selection
        selection = db.query(Selection).filter(Selection.id == selection_id).first()
        if not selection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Selection '{selection_id}' not found."
            )

        if not selection.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Selection '{selection_id}' contains no items."
            )

        # 2. Extract exact version-pinned nodes and content snapshots
        nodes_context_list = []
        source_node_ids = []
        source_logical_keys = []
        source_content_hashes = {}
        source_text_snapshots = []

        for item in selection.items:
            node = item.node
            source_node_ids.append(item.node_id)
            source_logical_keys.append(item.logical_key)
            source_content_hashes[item.node_id] = item.content_hash

            node_dict = {
                "node_id": item.node_id,
                "logical_key": item.logical_key,
                "node_type": node.node_type if node else "section",
                "section_number": node.section_number if node else None,
                "title_or_text": node.title_or_text if node else "",
                "table_data": node.table_data if node else None,
            }
            nodes_context_list.append(node_dict)

            source_text_snapshots.append(
                SourceTextSnapshot(
                    node_id=item.node_id,
                    logical_key=item.logical_key,
                    content_hash=item.content_hash,
                    title_or_text=node.title_or_text if node else ""
                )
            )

        # 3. Check duplicate-generation cache
        input_hash = self.compute_input_hash(
            selection_id=selection.id,
            version_id=selection.version_id,
            prompt_version=PROMPT_VERSION,
            model_name=llm.model_name,
            items=selection.items
        )

        if not force_regenerate:
            cached_rec = self.store.find_by_input_hash(selection.id, input_hash)
            if cached_rec:
                logger.info(f"Returning cached generation '{cached_rec['generation_id']}' for selection '{selection.id}'")
                return GenerationRecordResponse(
                    generation_id=cached_rec["generation_id"],
                    selection_id=cached_rec["selection_id"],
                    document_id=cached_rec["document_id"],
                    version_id=cached_rec["version_id"],
                    version_number=cached_rec["version_number"],
                    provider=cached_rec["provider"],
                    model=cached_rec["model"],
                    prompt_version=cached_rec["prompt_version"],
                    input_hash=cached_rec["input_hash"],
                    generated_at=cached_rec["generated_at"],
                    cached=True,
                    validation_status=cached_rec.get("validation_status", "valid"),
                    total_test_cases=len(cached_rec.get("test_cases", [])),
                    test_cases=[GeneratedTestCase(**tc) for tc in cached_rec.get("test_cases", [])],
                    source_node_ids=cached_rec.get("source_node_ids", []),
                    source_text_snapshots=[SourceTextSnapshot(**s) for s in cached_rec.get("source_text_snapshots", [])]
                )

        # 4. Construct prompt
        user_prompt = build_user_prompt(
            document_id=selection.document_id,
            version_number=selection.version_number,
            selection_name=selection.name,
            nodes=nodes_context_list,
            valid_node_ids=source_node_ids,
            additional_instructions=additional_instructions
        )

        # 5. Call LLM provider
        try:
            raw_response = llm.generate(SYSTEM_PROMPT, user_prompt)
        except LLMProviderError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(e)
            )

        # 6. Validate output
        test_cases, err_msg = self.validate_test_cases_payload(
            raw_text=raw_response,
            valid_node_ids=source_node_ids,
            version_number=selection.version_number,
            content_hashes=source_content_hashes
        )

        validation_status = "valid"

        # 7. Bounded single repair attempt on failure
        if err_msg:
            logger.warning(f"Initial LLM response failed validation: {err_msg}. Triggering 1 repair attempt.")
            repair_prompt = build_repair_prompt(
                validation_errors=err_msg,
                previous_raw_output=raw_response[:1000],
                valid_node_ids=source_node_ids
            )
            try:
                repaired_raw = llm.generate(SYSTEM_PROMPT, repair_prompt)
                test_cases, repair_err = self.validate_test_cases_payload(
                    raw_text=repaired_raw,
                    valid_node_ids=source_node_ids,
                    version_number=selection.version_number,
                    content_hashes=source_content_hashes
                )
                if repair_err:
                    raise LLMValidationError(f"Repair attempt failed: {repair_err}")
                validation_status = "repaired"
            except LLMValidationError as ve:
                logger.error(f"Bounded repair exhausted: {ve}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"LLM generated output failed schema and grounding validation: {ve}"
                )
            except Exception as e:
                logger.error(f"Unexpected error during LLM repair: {type(e).__name__}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="LLM generation repair failed. Please retry."
                )

        # 8. Persist generation record
        generation_id = f"gen_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.datetime.utcnow().isoformat()

        record = {
            "generation_id": generation_id,
            "selection_id": selection.id,
            "document_id": selection.document_id,
            "version_id": selection.version_id,
            "version_number": selection.version_number,
            "generated_at": now_iso,
            "provider": llm.provider_name,
            "model": llm.model_name,
            "prompt_version": PROMPT_VERSION,
            "input_hash": input_hash,
            "validation_status": validation_status,
            "generation_status": "success",
            "error_details": None,
            "total_test_cases": len(test_cases),
            "test_cases": [tc.model_dump() for tc in test_cases],
            "source_node_ids": source_node_ids,
            "source_logical_keys": source_logical_keys,
            "source_content_hashes": source_content_hashes,
            "source_text_snapshots": [s.model_dump() for s in source_text_snapshots]
        }

        self.store.save_generation(record)

        return GenerationRecordResponse(
            generation_id=generation_id,
            selection_id=selection.id,
            document_id=selection.document_id,
            version_id=selection.version_id,
            version_number=selection.version_number,
            provider=llm.provider_name,
            model=llm.model_name,
            prompt_version=PROMPT_VERSION,
            input_hash=input_hash,
            generated_at=now_iso,
            cached=False,
            validation_status=validation_status,
            total_test_cases=len(test_cases),
            test_cases=test_cases,
            source_node_ids=source_node_ids,
            source_text_snapshots=source_text_snapshots
        )
