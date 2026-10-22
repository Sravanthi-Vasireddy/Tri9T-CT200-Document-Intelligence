import re
import difflib
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Document, DocumentVersion, DocumentNodeModel
from app.schemas import (
    DocumentVersionResponse,
    SectionSummaryResponse,
    NodeDetailResponse,
    SearchResponse,
    SearchResultItem,
    NodeChangeResponse
)

router = APIRouter(prefix="/api", tags=["Document Intelligence"])


def normalize_version_param(version_str: Optional[str]) -> Optional[str]:
    """Normalizes version representations ('1' -> 'v1', 'v1' -> 'v1')."""
    if not version_str:
        return None
    cleaned = version_str.strip().lower()
    if not cleaned.startswith("v"):
        return f"v{cleaned}"
    return cleaned


def create_snippet(text: str, query: str, context_len: int = 60) -> str:
    """Extracts a highlighted context window around the query occurrence."""
    if not text:
        return ""
    pos = text.lower().find(query.lower())
    if pos == -1:
        return text[: context_len * 2] + ("..." if len(text) > context_len * 2 else "")
    start = max(0, pos - context_len)
    end = min(len(text), pos + len(query) + context_len)
    snippet = text[start:end].strip()
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def generate_diff(text1: str, text2: str) -> str:
    """Generates a concise unified diff between two text blocks."""
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    diff = list(difflib.unified_diff(lines1, lines2, fromfile="source", tofile="target", lineterm=""))
    if diff:
        return "\n".join(diff[:25])
    return "Content modified (whitespace/formatting difference)"


# ---------------------------------------------------------
# 2. List Document Versions
# ---------------------------------------------------------
@router.get(
    "/documents/{document_id}/versions",
    response_model=List[DocumentVersionResponse],
    summary="List available versions of a document in chronological order"
)
def list_document_versions(document_id: str, db: Session = Depends(get_db)):
    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.ingested_at.asc())
        .all()
    )
    if not versions:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document '{document_id}' not found."
            )
        return []

    return [
        DocumentVersionResponse(
            id=v.id,
            document_id=v.document_id,
            version_number=v.version_number,
            source_filename=v.source_filename,
            file_hash=v.file_hash,
            total_pages=v.total_pages,
            total_nodes=v.total_nodes,
            root_node_id=v.root_node_id,
            ingested_at=v.ingested_at.isoformat()
        )
        for v in versions
    ]


# ---------------------------------------------------------
# 3. List Top-Level Sections
# ---------------------------------------------------------
@router.get(
    "/documents/{document_id}/sections",
    response_model=List[SectionSummaryResponse],
    summary="List top-level sections for a specified or latest version"
)
def list_top_level_sections(
    document_id: str,
    version: Optional[str] = Query(None, description="Version string or number (e.g. '1', 'v1', '2', 'v2')"),
    db: Session = Depends(get_db)
):
    # Resolve target version
    if version:
        v_norm = normalize_version_param(version)
        target_ver = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id, DocumentVersion.version_number == v_norm)
            .first()
        )
        if not target_ver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version '{version}' not found for document '{document_id}'."
            )
    else:
        # Default to latest successfully ingested version
        target_ver = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.ingested_at.desc())
            .first()
        )
        if not target_ver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No versions found for document '{document_id}'."
            )

    # Top-level sections have hierarchy_level == 1 and node_type == "section"
    sections = (
        db.query(DocumentNodeModel)
        .filter(
            DocumentNodeModel.version_id == target_ver.id,
            DocumentNodeModel.node_type == "section",
            DocumentNodeModel.hierarchy_level == 1
        )
        .order_by(DocumentNodeModel.reading_order_index.asc())
        .all()
    )

    return [
        SectionSummaryResponse(
            id=s.id,
            logical_key=s.logical_key,
            heading=s.title_or_text,
            section_number=s.section_number,
            node_type=s.node_type,
            hierarchy_level=s.hierarchy_level,
            document_order=s.reading_order_index,
            page_start=s.page_start,
            page_end=s.page_end,
            content_hash=s.content_hash
        )
        for s in sections
    ]


# ---------------------------------------------------------
# 4. Retrieve a Specific Node
# ---------------------------------------------------------
@router.get(
    "/nodes/{node_id}",
    response_model=NodeDetailResponse,
    summary="Retrieve exact versioned content and structure for a node"
)
def get_node_detail(node_id: str, db: Session = Depends(get_db)):
    node = db.query(DocumentNodeModel).filter(DocumentNodeModel.id == node_id).first()
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found."
        )

    # Parent details if parent exists
    parent_details = None
    if node.parent_id:
        parent = db.query(DocumentNodeModel).filter(DocumentNodeModel.id == node.parent_id).first()
        if parent:
            parent_details = {
                "id": parent.id,
                "logical_key": parent.logical_key,
                "title_or_text": parent.title_or_text,
                "section_number": parent.section_number,
                "node_type": parent.node_type
            }

    return NodeDetailResponse(
        id=node.id,
        version_id=node.version_id,
        version_number=node.version.version_number if node.version else "",
        logical_key=node.logical_key,
        node_type=node.node_type,
        title_or_text=node.title_or_text,
        section_number=node.section_number,
        hierarchy_level=node.hierarchy_level,
        parent_id=node.parent_id,
        parent_details=parent_details,
        children_ids=node.children_ids,
        reading_order_index=node.reading_order_index,
        page_start=node.page_start,
        page_end=node.page_end,
        content_hash=node.content_hash,
        extraction_confidence=node.extraction_confidence,
        is_uncertain=node.is_uncertain,
        table_data=node.table_data,
        metadata=node.metadata_dict
    )


# ---------------------------------------------------------
# 5. Search the Document
# ---------------------------------------------------------
@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search headings and body text across nodes"
)
def search_documents(
    q: str = Query(..., description="Search query string"),
    version: Optional[str] = Query(None, description="Optional version filter ('1', 'v1', '2', 'v2')"),
    type: Optional[str] = Query(None, description="Optional node-type filter (section, paragraph, table, list)"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return (1-100)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    query_str = q.strip()
    if not query_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query 'q' must not be empty or whitespace."
        )

    # Base query joined with DocumentVersion
    base_query = db.query(DocumentNodeModel).join(
        DocumentVersion, DocumentNodeModel.version_id == DocumentVersion.id
    )

    # Version filter
    if version:
        v_norm = normalize_version_param(version)
        base_query = base_query.filter(DocumentVersion.version_number == v_norm)

    # Node type filter
    if type:
        node_type_clean = type.strip().lower()
        base_query = base_query.filter(DocumentNodeModel.node_type == node_type_clean)

    # Content filter (searching headings, body text, or section number)
    search_pattern = f"%{query_str}%"
    base_query = base_query.filter(
        or_(
            DocumentNodeModel.title_or_text.ilike(search_pattern),
            DocumentNodeModel.section_number.ilike(search_pattern)
        )
    )

    total_matches = base_query.count()

    # Deterministic ordering
    results = (
        base_query.order_by(
            DocumentVersion.ingested_at.desc(),
            DocumentNodeModel.reading_order_index.asc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = []
    for node in results:
        snippet = create_snippet(node.title_or_text, query_str)
        items.append(
            SearchResultItem(
                node_id=node.id,
                logical_key=node.logical_key,
                title_or_text=node.title_or_text,
                snippet=snippet,
                section_number=node.section_number,
                node_type=node.node_type,
                page_start=node.page_start,
                page_end=node.page_end,
                version_id=node.version_id,
                version_number=node.version.version_number if node.version else "",
                content_hash=node.content_hash
            )
        )

    return SearchResponse(
        query=query_str,
        total_matches=total_matches,
        limit=limit,
        offset=offset,
        results=items
    )


# ---------------------------------------------------------
# 6. Compare Node Changes Across Versions
# ---------------------------------------------------------
@router.get(
    "/nodes/{node_id}/changes",
    response_model=NodeChangeResponse,
    summary="Compare a node's logical identity and content against a target version"
)
def compare_node_changes(
    node_id: str,
    target_version: Optional[str] = Query(None, description="Target version number (e.g. '2', 'v2'). Defaults to latest."),
    db: Session = Depends(get_db)
):
    source_node = db.query(DocumentNodeModel).filter(DocumentNodeModel.id == node_id).first()
    if not source_node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source node '{node_id}' not found."
        )

    source_ver = source_node.version
    if not source_ver:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Corrupt node data: Node '{node_id}' has no associated version record."
        )

    doc_id = source_ver.document_id

    # Resolve target version
    if target_version:
        t_norm = normalize_version_param(target_version)
        target_ver_obj = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc_id, DocumentVersion.version_number == t_norm)
            .first()
        )
        if not target_ver_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target version '{target_version}' not found for document '{doc_id}'."
            )
    else:
        # Default to latest version
        target_ver_obj = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc_id)
            .order_by(DocumentVersion.ingested_at.desc())
            .first()
        )
        if not target_ver_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No versions found for document '{doc_id}'."
            )

    # If source version is target version
    if source_ver.id == target_ver_obj.id:
        return NodeChangeResponse(
            source_node_id=source_node.id,
            source_version_id=source_ver.id,
            source_version_number=source_ver.version_number,
            target_node_id=source_node.id,
            target_version_id=target_ver_obj.id,
            target_version_number=target_ver_obj.version_number,
            logical_key=source_node.logical_key,
            status="unchanged",
            source_content_hash=source_node.content_hash,
            target_content_hash=source_node.content_hash,
            diff_summary=None,
            details="Source and target version are identical."
        )

    # Query matching candidate nodes in target version by logical_key
    target_candidates = (
        db.query(DocumentNodeModel)
        .filter(
            DocumentNodeModel.version_id == target_ver_obj.id,
            DocumentNodeModel.logical_key == source_node.logical_key
        )
        .all()
    )

    if len(target_candidates) == 1:
        target_node = target_candidates[0]
        if target_node.content_hash == source_node.content_hash:
            change_status = "unchanged"
            diff_str = None
            details_str = "Node content and structure are identical across versions."
        else:
            change_status = "modified"
            diff_str = generate_diff(source_node.title_or_text, target_node.title_or_text)
            details_str = "Content differs between versions."

        return NodeChangeResponse(
            source_node_id=source_node.id,
            source_version_id=source_ver.id,
            source_version_number=source_ver.version_number,
            target_node_id=target_node.id,
            target_version_id=target_ver_obj.id,
            target_version_number=target_ver_obj.version_number,
            logical_key=source_node.logical_key,
            status=change_status,
            source_content_hash=source_node.content_hash,
            target_content_hash=target_node.content_hash,
            diff_summary=diff_str,
            details=details_str
        )

    elif len(target_candidates) == 0:
        return NodeChangeResponse(
            source_node_id=source_node.id,
            source_version_id=source_ver.id,
            source_version_number=source_ver.version_number,
            target_node_id=None,
            target_version_id=target_ver_obj.id,
            target_version_number=target_ver_obj.version_number,
            logical_key=source_node.logical_key,
            status="removed",
            source_content_hash=source_node.content_hash,
            target_content_hash=None,
            diff_summary=f"- {source_node.title_or_text[:100]}",
            details=f"Node '{source_node.logical_key}' was removed or not matched in version {target_ver_obj.version_number}."
        )

    else:
        return NodeChangeResponse(
            source_node_id=source_node.id,
            source_version_id=source_ver.id,
            source_version_number=source_ver.version_number,
            target_node_id=None,
            target_version_id=target_ver_obj.id,
            target_version_number=target_ver_obj.version_number,
            logical_key=source_node.logical_key,
            status="ambiguous",
            source_content_hash=source_node.content_hash,
            target_content_hash=None,
            diff_summary=None,
            details=f"Multiple ambiguous candidate nodes ({len(target_candidates)}) found in target version."
        )
