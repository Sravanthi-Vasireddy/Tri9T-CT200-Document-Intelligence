import re
import json
import difflib
import logging
import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import Document, DocumentVersion, DocumentNodeModel, Selection
from app.schemas import (
    StalenessStatusEnum,
    SourceNodeComparison,
    TestCaseStalenessDetail,
    GenerationStalenessReport,
    SelectionStalenessSummary,
    NodeAssociatedTestCase
)
from app.llm.store import JSONTestStore

logger = logging.getLogger("doc_intelligence.staleness")


def get_node_full_content(node: Any, db: Optional[Session] = None) -> str:
    """
    Returns complete textual representation of a node, including structured table rows
    and/or child content paragraphs for section nodes.
    """
    if not node:
        return ""

    table_data = getattr(node, "table_data", None)
    if not table_data and isinstance(node, dict):
        table_data = node.get("table_data")

    title_or_text = getattr(node, "title_or_text", None)
    if title_or_text is None and isinstance(node, dict):
        title_or_text = node.get("title_or_text", "")

    if table_data and isinstance(table_data, dict):
        headers = " | ".join(str(h) for h in table_data.get("headers", []))
        rows = "\n".join(" | ".join(str(cell or "") for cell in r) for r in table_data.get("rows", []))
        return f"{title_or_text}\n| {headers} |\n{rows}"

    node_type = getattr(node, "node_type", None)
    if node_type is None and isinstance(node, dict):
        node_type = node.get("node_type")

    node_id = getattr(node, "id", None)
    if node_id is None and isinstance(node, dict):
        node_id = node.get("node_id") or node.get("id")

    if node_type == "section" and db and node_id:
        children = (
            db.query(DocumentNodeModel)
            .filter(DocumentNodeModel.parent_id == node_id)
            .order_by(DocumentNodeModel.reading_order_index.asc())
            .all()
        )
        child_parts = []
        for ch in children:
            if ch.node_type == "table" and ch.table_data:
                h_str = " | ".join(str(h) for h in ch.table_data.get("headers", []))
                r_str = "\n".join(" | ".join(str(c or "") for c in r) for r in ch.table_data.get("rows", []))
                child_parts.append(f"{ch.title_or_text}\n| {h_str} |\n{r_str}")
            else:
                child_parts.append(ch.title_or_text)
        if child_parts:
            return f"{title_or_text}\n" + "\n".join(child_parts)

    return title_or_text or ""


def generate_diff(text1: str, text2: str) -> str:
    """Generates a concise unified diff between two text blocks."""
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    diff = list(difflib.unified_diff(lines1, lines2, fromfile="source", tofile="target", lineterm=""))
    if diff:
        return "\n".join(diff[:25])
    return "Content modified (formatting or whitespace differences)"


def detect_high_impact_changes(text1: str, text2: str) -> Tuple[bool, List[str]]:
    """
    Analyzes additions and deletions between text1 and text2 to flag potential
    high-impact specification changes (numeric thresholds, timing, units, inequalities, negations, safety).
    """
    reasons = []

    # 1. Numeric thresholds & quantities
    nums1 = set(re.findall(r"\b\d+(?:\.\d+)?\b", text1))
    nums2 = set(re.findall(r"\b\d+(?:\.\d+)?\b", text2))
    diff_nums = (nums1 - nums2) | (nums2 - nums1)
    # Filter out single-digit section numbers 1-9 to avoid false flags purely on section indices
    sig_nums = {n for n in diff_nums if not (len(n) == 1 and n in "123456789")}
    if sig_nums:
        reasons.append(f"Numeric threshold/quantity modified ({', '.join(sorted(sig_nums))})")

    # 2. Timing limits and response times
    timing_pattern = r"\b(?:\d+(?:\.\d+)?\s*(?:seconds?|s|mins?|minutes?|hours?))\b"
    t1 = set(re.findall(timing_pattern, text1, flags=re.IGNORECASE))
    t2 = set(re.findall(timing_pattern, text2, flags=re.IGNORECASE))
    if t1 != t2:
        reasons.append(f"Timing limit or response time changed ({t1} -> {t2})")

    # 3. Measurement units and tolerances
    units = ["mmhg", "beats/min", "%", "°c", "rh"]
    for u in units:
        if (u in text1.lower()) != (u in text2.lower()):
            reasons.append(f"Measurement unit reference changed ('{u}')")

    # 4. Negative clauses and safety prohibitions
    negations = ["cannot", "shall not", "do not", "never", "must not", "prevent"]
    for neg in negations:
        if (neg in text1.lower()) != (neg in text2.lower()):
            reasons.append(f"Negative safety condition or prohibition altered ('{neg}')")

    # 5. Critical safety & alarm keywords
    safety_terms = ["overpressure", "deflate", "deflation", "alarm", "hazard", "battery warning"]
    for st in safety_terms:
        if (st in text1.lower()) != (st in text2.lower()):
            reasons.append(f"Safety/alarm condition modified ('{st}')")

    is_high_impact = len(reasons) > 0
    return is_high_impact, reasons


class StalenessService:
    """
    Evaluates QA test case staleness and specification impact by comparing
    persisted generation source snapshots with the latest document version.
    """

    def __init__(self, store: Optional[JSONTestStore] = None):
        self.store = store or JSONTestStore()

    def evaluate_generation(
        self,
        generation_id: str,
        db: Session,
        target_version: Optional[str] = None
    ) -> GenerationStalenessReport:
        """
        Evaluates staleness of all test cases in a generation against target_version (defaults to latest).
        """
        record = self.store.get_generation(generation_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation '{generation_id}' not found in document store."
            )

        doc_id = record.get("document_id")
        source_ver_num = record.get("version_number", "")
        source_ver_id = record.get("version_id", "")

        # 1. Resolve Target DocumentVersion
        if target_version:
            v_norm = target_version.strip().lower()
            if not v_norm.startswith("v"):
                v_norm = f"v{v_norm}"
            target_ver_obj = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == doc_id, DocumentVersion.version_number == v_norm)
                .first()
            )
            if not target_ver_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target version '{target_version}' not found for document '{doc_id}'."
                )
        else:
            target_ver_obj = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == doc_id)
                .order_by(DocumentVersion.ingested_at.desc(), DocumentVersion.version_number.desc())
                .first()
            )

        if not target_ver_obj:
            # No target version exists in DB
            now_iso = datetime.datetime.utcnow().isoformat()
            return GenerationStalenessReport(
                generation_id=generation_id,
                selection_id=record.get("selection_id", ""),
                document_id=doc_id or "",
                source_version_number=source_ver_num,
                target_version_number="none",
                overall_status=StalenessStatusEnum.UNKNOWN,
                total_test_cases=len(record.get("test_cases", [])),
                current_count=0,
                stale_count=0,
                review_required_count=0,
                unknown_count=len(record.get("test_cases", [])),
                impact_summary=["No target document version found for comparison."],
                test_cases=[],
                evaluated_at=now_iso
            )

        # 2. Map source snapshots and content hashes
        snapshots_list = record.get("source_text_snapshots", [])
        snapshots_by_id = {s["node_id"]: s for s in snapshots_list}
        source_hashes = record.get("source_content_hashes", {})

        # 3. Compare each source node against target version
        source_node_comparisons: Dict[str, SourceNodeComparison] = {}

        for nid in record.get("source_node_ids", []):
            snapshot = snapshots_by_id.get(nid)

            # Check if historical snapshot metadata is missing
            if not snapshot or not snapshot.get("content_hash"):
                source_node_comparisons[nid] = SourceNodeComparison(
                    node_id=nid,
                    logical_key=snapshot.get("logical_key", "unknown") if snapshot else "unknown",
                    status="review_required",
                    source_version_id=source_ver_id,
                    target_version_id=target_ver_obj.id,
                    target_node_id=None,
                    source_hash="",
                    target_hash=None,
                    diff_summary=None,
                    potential_high_impact=False,
                    impact_reasons=["Missing historical content hash or text snapshot"],
                    details="Historical metadata incomplete. Manual review required."
                )
                continue

            logical_key = snapshot.get("logical_key")
            source_hash = snapshot.get("content_hash")
            source_text = snapshot.get("title_or_text", "")

            # If source version is target version
            if source_ver_id == target_ver_obj.id:
                source_node_comparisons[nid] = SourceNodeComparison(
                    node_id=nid,
                    logical_key=logical_key,
                    status="unchanged",
                    source_version_id=source_ver_id,
                    target_version_id=target_ver_obj.id,
                    target_node_id=nid,
                    source_hash=source_hash,
                    target_hash=source_hash,
                    diff_summary=None,
                    potential_high_impact=False,
                    impact_reasons=[],
                    details="Source version and target version are identical."
                )
                continue

            # Query matching candidate nodes in target version by logical_key
            candidates = (
                db.query(DocumentNodeModel)
                .filter(
                    DocumentNodeModel.version_id == target_ver_obj.id,
                    DocumentNodeModel.logical_key == logical_key
                )
                .all()
            )

            if len(candidates) == 1:
                target_node = candidates[0]
                if target_node.content_hash == source_hash:
                    source_node_comparisons[nid] = SourceNodeComparison(
                        node_id=nid,
                        logical_key=logical_key,
                        status="unchanged",
                        source_version_id=source_ver_id,
                        target_version_id=target_ver_obj.id,
                        target_node_id=target_node.id,
                        source_hash=source_hash,
                        target_hash=target_node.content_hash,
                        diff_summary=None,
                        potential_high_impact=False,
                        impact_reasons=[],
                        details="Node content and structure are identical across versions."
                    )
                else:
                    source_node_model = db.query(DocumentNodeModel).filter(DocumentNodeModel.id == nid).first()
                    source_full_text = get_node_full_content(source_node_model, db) if source_node_model else source_text
                    target_full_text = get_node_full_content(target_node, db)

                    diff_str = generate_diff(source_full_text, target_full_text)
                    is_hi, hi_reasons = detect_high_impact_changes(source_full_text, target_full_text)
                    source_node_comparisons[nid] = SourceNodeComparison(
                        node_id=nid,
                        logical_key=logical_key,
                        status="modified",
                        source_version_id=source_ver_id,
                        target_version_id=target_ver_obj.id,
                        target_node_id=target_node.id,
                        source_hash=source_hash,
                        target_hash=target_node.content_hash,
                        diff_summary=diff_str,
                        potential_high_impact=is_hi,
                        impact_reasons=hi_reasons,
                        details=f"Content modified in version {target_ver_obj.version_number}."
                    )
            elif len(candidates) == 0:
                source_node_comparisons[nid] = SourceNodeComparison(
                    node_id=nid,
                    logical_key=logical_key,
                    status="removed",
                    source_version_id=source_ver_id,
                    target_version_id=target_ver_obj.id,
                    target_node_id=None,
                    source_hash=source_hash,
                    target_hash=None,
                    diff_summary=f"- {source_text[:100]}",
                    potential_high_impact=True,
                    impact_reasons=["Requirement was removed from target version"],
                    details=f"Node '{logical_key}' was removed in version {target_ver_obj.version_number}."
                )
            else:
                source_node_comparisons[nid] = SourceNodeComparison(
                    node_id=nid,
                    logical_key=logical_key,
                    status="ambiguous",
                    source_version_id=source_ver_id,
                    target_version_id=target_ver_obj.id,
                    target_node_id=None,
                    source_hash=source_hash,
                    target_hash=None,
                    diff_summary=None,
                    potential_high_impact=False,
                    impact_reasons=["Ambiguous match: multiple target nodes share this logical key"],
                    details=f"Multiple candidate nodes ({len(candidates)}) share key in target version."
                )

        # 4. Evaluate each test case individually
        test_case_details: List[TestCaseStalenessDetail] = []
        impact_summary_lines: List[str] = []

        for tc in record.get("test_cases", []):
            tc_id = tc.get("id", "TC-UNKNOWN")
            tc_title = tc.get("title", "")
            tc_node_ids = tc.get("source_node_ids", [])

            # Collect comparisons for this test case's source nodes
            tc_comparisons = [
                source_node_comparisons[nid]
                for nid in tc_node_ids
                if nid in source_node_comparisons
            ]

            if len(tc_comparisons) != len(tc_node_ids) or any(c.status == "review_required" for c in tc_comparisons):
                tc_status = StalenessStatusEnum.REVIEW_REQUIRED
                tc_reason = "Missing historical metadata or unmapped source node reference."
                tc_hi = False
                tc_hi_reasons = ["Incomplete source lineage"]

            elif any(c.status in ("modified", "removed") for c in tc_comparisons):
                tc_status = StalenessStatusEnum.STALE
                stale_items = [c for c in tc_comparisons if c.status in ("modified", "removed")]
                reasons_sub = []
                for sc in stale_items:
                    if sc.status == "modified":
                        reasons_sub.append(f"Source requirement '{sc.logical_key}' was modified in {target_ver_obj.version_number}")
                    else:
                        reasons_sub.append(f"Source requirement '{sc.logical_key}' was removed in {target_ver_obj.version_number}")
                tc_reason = "; ".join(reasons_sub)
                tc_hi = any(c.potential_high_impact for c in tc_comparisons)
                tc_hi_reasons = []
                for c in tc_comparisons:
                    tc_hi_reasons.extend(c.impact_reasons)

            elif any(c.status == "ambiguous" for c in tc_comparisons):
                tc_status = StalenessStatusEnum.REVIEW_REQUIRED
                tc_reason = "Source requirement match is ambiguous in target version."
                tc_hi = False
                tc_hi_reasons = ["Ambiguous logical match"]

            elif all(c.status == "unchanged" for c in tc_comparisons):
                tc_status = StalenessStatusEnum.CURRENT
                tc_reason = f"All {len(tc_comparisons)} referenced source node(s) remain unchanged in {target_ver_obj.version_number}."
                tc_hi = False
                tc_hi_reasons = []

            else:
                tc_status = StalenessStatusEnum.UNKNOWN
                tc_reason = "Target comparison undetermined."
                tc_hi = False
                tc_hi_reasons = []

            test_case_details.append(
                TestCaseStalenessDetail(
                    test_case_id=tc_id,
                    title=tc_title,
                    status=tc_status,
                    reason=tc_reason,
                    potential_high_impact=tc_hi,
                    impact_reasons=tc_hi_reasons,
                    referenced_nodes=tc_comparisons
                )
            )

        # 5. Summarize generation metrics
        total = len(test_case_details)
        current_cnt = sum(1 for t in test_case_details if t.status == StalenessStatusEnum.CURRENT)
        stale_cnt = sum(1 for t in test_case_details if t.status == StalenessStatusEnum.STALE)
        review_cnt = sum(1 for t in test_case_details if t.status == StalenessStatusEnum.REVIEW_REQUIRED)
        unknown_cnt = sum(1 for t in test_case_details if t.status == StalenessStatusEnum.UNKNOWN)

        if stale_cnt > 0:
            overall = StalenessStatusEnum.STALE
        elif review_cnt > 0:
            overall = StalenessStatusEnum.REVIEW_REQUIRED
        elif current_cnt == total and total > 0:
            overall = StalenessStatusEnum.CURRENT
        else:
            overall = StalenessStatusEnum.UNKNOWN

        # Build human-readable impact summary
        modified_nodes = [c for c in source_node_comparisons.values() if c.status == "modified"]
        removed_nodes = [c for c in source_node_comparisons.values() if c.status == "removed"]
        stale_tests = [t for t in test_case_details if t.status == StalenessStatusEnum.STALE]

        if modified_nodes:
            impact_summary_lines.append(
                f"{len(modified_nodes)} source node(s) modified in {target_ver_obj.version_number}: "
                f"{', '.join(m.logical_key for m in modified_nodes)}."
            )
        if removed_nodes:
            impact_summary_lines.append(
                f"{len(removed_nodes)} source node(s) removed in {target_ver_obj.version_number}: "
                f"{', '.join(r.logical_key for r in removed_nodes)}."
            )
        if stale_tests:
            impact_summary_lines.append(
                f"{len(stale_tests)} test case(s) rendered STALE: {', '.join(t.test_case_id for t in stale_tests)}."
            )
        if not modified_nodes and not removed_nodes:
            impact_summary_lines.append(
                f"All source requirements remain identical in {target_ver_obj.version_number}. All test cases are CURRENT."
            )

        return GenerationStalenessReport(
            generation_id=generation_id,
            selection_id=record.get("selection_id", ""),
            document_id=doc_id or "",
            source_version_number=source_ver_num,
            target_version_number=target_ver_obj.version_number,
            overall_status=overall,
            total_test_cases=total,
            current_count=current_cnt,
            stale_count=stale_cnt,
            review_required_count=review_cnt,
            unknown_count=unknown_cnt,
            impact_summary=impact_summary_lines,
            test_cases=test_case_details,
            evaluated_at=datetime.datetime.utcnow().isoformat()
        )

    def evaluate_selection(
        self,
        selection_id: str,
        db: Session,
        target_version: Optional[str] = None
    ) -> SelectionStalenessSummary:
        """
        Aggregates staleness across all successful generations for a selection.
        """
        selection = db.query(Selection).filter(Selection.id == selection_id).first()
        if not selection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Selection '{selection_id}' not found."
            )

        gen_records = self.store.list_by_selection(selection_id)
        successful_records = [r for r in gen_records if r.get("generation_status") == "success"]

        reports = []
        for r in successful_records:
            try:
                rep = self.evaluate_generation(r["generation_id"], db, target_version)
                reports.append(rep)
            except Exception as e:
                logger.error(f"Failed to evaluate generation '{r.get('generation_id')}': {e}")

        total_tc = sum(rep.total_test_cases for rep in reports)
        total_curr = sum(rep.current_count for rep in reports)
        total_stale = sum(rep.stale_count for rep in reports)
        total_rev = sum(rep.review_required_count for rep in reports)
        total_unk = sum(rep.unknown_count for rep in reports)
        target_ver_str = reports[0].target_version_number if reports else "none"

        return SelectionStalenessSummary(
            selection_id=selection.id,
            selection_name=selection.name,
            document_id=selection.document_id,
            source_version_number=selection.version_number,
            target_version_number=target_ver_str,
            total_generations=len(reports),
            total_test_cases=total_tc,
            current_count=total_curr,
            stale_count=total_stale,
            review_required_count=total_rev,
            unknown_count=total_unk,
            generation_reports=reports,
            evaluated_at=datetime.datetime.utcnow().isoformat()
        )

    def get_test_cases_for_node(
        self,
        node_id: str,
        db: Session
    ) -> List[NodeAssociatedTestCase]:
        """
        Retrieves all generated test cases that reference a specific version-specific node ID,
        including their current staleness assessment.
        """
        # Verify node exists in document_nodes or in stored snapshots
        node = db.query(DocumentNodeModel).filter(DocumentNodeModel.id == node_id).first()

        # Search all generations in store referencing this node_id
        matched_cases: List[NodeAssociatedTestCase] = []

        for file in self.store.store_dir.glob("gen_*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                    if node_id not in rec.get("source_node_ids", []):
                        continue

                    # Evaluate staleness of this generation
                    gen_id = rec.get("generation_id")
                    gen_report = self.evaluate_generation(gen_id, db)
                    tc_map = {t.test_case_id: t for t in gen_report.test_cases}

                    # Find test cases citing node_id
                    for tc in rec.get("test_cases", []):
                        if node_id in tc.get("source_node_ids", []):
                            tc_detail = tc_map.get(tc.get("id"))
                            # Get diff summary for this specific node
                            node_comp = next((c for c in (tc_detail.referenced_nodes if tc_detail else []) if c.node_id == node_id), None)
                            matched_cases.append(
                                NodeAssociatedTestCase(
                                    test_case_id=tc.get("id", ""),
                                    title=tc.get("title", ""),
                                    generation_id=gen_id,
                                    selection_id=rec.get("selection_id", ""),
                                    source_version_number=rec.get("version_number", ""),
                                    priority=tc.get("priority", "medium"),
                                    staleness_status=tc_detail.status.value if tc_detail else "unknown",
                                    reason=tc_detail.reason if tc_detail else "",
                                    potential_high_impact=node_comp.potential_high_impact if node_comp else False,
                                    diff_summary=node_comp.diff_summary if node_comp else None
                                )
                            )
            except Exception as e:
                logger.error(f"Error inspecting generation file {file}: {e}")

        if not node and not matched_cases:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node '{node_id}' not found."
            )

        return matched_cases
