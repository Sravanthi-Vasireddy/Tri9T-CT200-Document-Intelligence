import os
import json
import hashlib
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models import Document, DocumentVersion, DocumentNodeModel
from app.parser import CT200PDFParser
from app.validator import DocumentTreeValidator
from app.versioning import DocumentVersionMatcher
from app.schemas import IngestionSummary, NodeMatch, DocumentTree


class IngestionService:
    """
    Transactional service to ingest PDF documents, parse hierarchy,
    detect duplicate file hashes, match against prior versions,
    and persist versions and nodes into the relational database.
    """

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """Computes SHA-256 hash of a file's binary contents."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def ingest_pdf(
        cls,
        pdf_path: str,
        version_number: str,
        document_id: str = "ct200_manual",
        document_name: str = "CardioTrack CT-200 Technical & User Manual",
        db: Optional[Session] = None
    ) -> IngestionSummary:
        """
        Parses and transactionally ingests a PDF version into SQLite.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

        close_session = False
        if db is None:
            from app.database import SessionLocal
            db = SessionLocal()
            close_session = True

        try:
            return cls._ingest_pdf_internal(
                pdf_path=pdf_path,
                version_number=version_number,
                document_id=document_id,
                document_name=document_name,
                db=db
            )
        finally:
            if close_session:
                db.close()

    @classmethod
    def _ingest_pdf_internal(
        cls,
        pdf_path: str,
        version_number: str,
        document_id: str,
        document_name: str,
        db: Session
    ) -> IngestionSummary:
        file_hash = cls.calculate_file_hash(pdf_path)
        source_filename = os.path.basename(pdf_path)
        version_id = f"{document_id}_{version_number}"

        # 1. Deduplication Check via file_hash
        existing_version = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id, DocumentVersion.file_hash == file_hash)
            .first()
        )
        if existing_version:
            # Already ingested with identical file hash; return existing summary without duplicating
            diff_summary = existing_version.diff_summary or {}
            diff_details = [NodeMatch(**m) for m in diff_summary.get("matches", [])]
            return IngestionSummary(
                version_id=existing_version.id,
                version_number=existing_version.version_number,
                document_id=existing_version.document_id,
                source_filename=existing_version.source_filename,
                file_hash=existing_version.file_hash,
                total_pages=existing_version.total_pages,
                total_nodes=existing_version.total_nodes,
                added_nodes=diff_summary.get("counts", {}).get("added", 0),
                removed_nodes=diff_summary.get("counts", {}).get("removed", 0),
                changed_nodes=diff_summary.get("counts", {}).get("changed", 0),
                unchanged_nodes=diff_summary.get("counts", {}).get("unchanged", existing_version.total_nodes),
                ambiguous_matches=diff_summary.get("counts", {}).get("ambiguous", 0),
                already_ingested=True,
                diff_details=diff_details
            )

        # Check if version_number already exists with a different file hash
        existing_vnum = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id, DocumentVersion.version_number == version_number)
            .first()
        )
        if existing_vnum:
            raise ValueError(
                f"Version '{version_number}' for document '{document_id}' already exists with different file hash ({existing_vnum.file_hash[:8]})."
            )

        # 2. Parse PDF into tree
        parser = CT200PDFParser(doc_id=document_id)
        tree: DocumentTree = parser.parse(pdf_path, version_number)

        # 3. Validate Tree
        DocumentTreeValidator.validate(tree, raise_on_error=True)

        # 4. Find most recent prior version for diffing
        prior_version = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.ingested_at.desc())
            .first()
        )

        diff_matches: List[NodeMatch] = []
        counts: Dict[str, int] = {
            "added": len(tree.nodes) if not prior_version else 0,
            "removed": 0,
            "changed": 0,
            "unchanged": 0,
            "ambiguous": 0
        }

        if prior_version:
            # Query prior nodes
            prior_nodes_db = (
                db.query(DocumentNodeModel)
                .filter(DocumentNodeModel.version_id == prior_version.id)
                .all()
            )
            prior_nodes_dict = {n.id: n for n in prior_nodes_db}
            diff_matches, counts = DocumentVersionMatcher.match_versions(prior_nodes_dict, tree)

        diff_summary_dict = {
            "matches": [m.model_dump() for m in diff_matches],
            "counts": counts
        }

        # 5. Transactional Persistence
        try:
            # Ensure parent Document exists
            doc_record = db.query(Document).filter(Document.id == document_id).first()
            if not doc_record:
                doc_record = Document(
                    id=document_id,
                    name=document_name,
                    description=tree.title
                )
                db.add(doc_record)
                db.flush()

            # Create DocumentVersion
            version_record = DocumentVersion(
                id=version_id,
                document_id=document_id,
                version_number=version_number,
                source_filename=source_filename,
                file_hash=file_hash,
                total_pages=tree.total_pages,
                total_nodes=len(tree.nodes),
                root_node_id=tree.root_node_id,
                diff_summary_json=json.dumps(diff_summary_dict),
                metadata_json=json.dumps(tree.metadata)
            )
            db.add(version_record)
            db.flush()

            # Create DocumentNodeModel records
            for node in tree.nodes.values():
                node_model = DocumentNodeModel(
                    id=node.id,
                    version_id=version_id,
                    logical_key=node.logical_key,
                    node_type=node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type),
                    title_or_text=node.title_or_text,
                    section_number=node.section_number,
                    hierarchy_level=node.hierarchy_level,
                    parent_id=node.parent_id,
                    reading_order_index=node.reading_order_index,
                    page_start=node.page_start,
                    page_end=node.page_end,
                    content_hash=node.content_hash,
                    extraction_confidence=node.extraction_confidence,
                    is_uncertain=node.is_uncertain,
                    children_ids_json=json.dumps(node.children_ids),
                    table_data_json=json.dumps(node.metadata.get("table_data")) if node.metadata.get("table_data") else None,
                    metadata_json=json.dumps(node.metadata) if node.metadata else None
                )
                db.add(node_model)

            db.commit()

        except Exception as e:
            db.rollback()
            raise RuntimeError(f"Ingestion transaction failed for {pdf_path}: {e}") from e

        return IngestionSummary(
            version_id=version_id,
            version_number=version_number,
            document_id=document_id,
            source_filename=source_filename,
            file_hash=file_hash,
            total_pages=tree.total_pages,
            total_nodes=len(tree.nodes),
            added_nodes=counts["added"],
            removed_nodes=counts["removed"],
            changed_nodes=counts["changed"],
            unchanged_nodes=counts["unchanged"],
            ambiguous_matches=counts["ambiguous"],
            already_ingested=False,
            diff_details=diff_matches
        )
