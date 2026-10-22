import datetime
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    """
    Represents a managed technical document entity (e.g. CardioTrack CT-200 manual).
    """
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.ingested_at.asc()"
    )

    def __repr__(self):
        return f"<Document(id='{self.id}', name='{self.name}')>"


class DocumentVersion(Base):
    """
    Represents an immutable, versioned ingestion snapshot of a document.
    """
    __tablename__ = "document_versions"

    id = Column(String(128), primary_key=True)  # e.g. "ct200_manual_v1"
    document_id = Column(String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(String(32), nullable=False, index=True)  # e.g. "v1", "v2"
    source_filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256 of the source PDF
    total_pages = Column(Integer, nullable=False)
    total_nodes = Column(Integer, nullable=False)
    root_node_id = Column(String(128), nullable=False)
    ingested_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    diff_summary_json = Column(Text, nullable=True)  # JSON summary of diff vs previous version
    metadata_json = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
        Index("idx_doc_version_hash", "document_id", "file_hash"),
    )

    # Relationships
    document = relationship("Document", back_populates="versions")
    nodes = relationship(
        "DocumentNodeModel",
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="DocumentNodeModel.reading_order_index.asc()"
    )

    @property
    def diff_summary(self) -> Optional[Dict[str, Any]]:
        if self.diff_summary_json:
            return json.loads(self.diff_summary_json)
        return None

    def __repr__(self):
        return f"<DocumentVersion(id='{self.id}', doc_id='{self.document_id}', version='{self.version_number}')>"


class DocumentNodeModel(Base):
    """
    Represents a specific structural node (section, paragraph, table, list) in a document version.
    """
    __tablename__ = "document_nodes"

    id = Column(String(128), primary_key=True)  # Version-specific ID, e.g. "v1_sec_2_1_1_1"
    version_id = Column(String(128), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    logical_key = Column(String(128), nullable=False, index=True)  # Cross-version stable key, e.g. "sec_2.1.1.1"
    node_type = Column(String(32), nullable=False, index=True)  # "document", "section", "paragraph", "table", "list"
    title_or_text = Column(Text, nullable=False)
    section_number = Column(String(32), nullable=True, index=True)
    hierarchy_level = Column(Integer, nullable=False)
    parent_id = Column(String(128), nullable=True, index=True)
    reading_order_index = Column(Integer, nullable=False, index=True)
    page_start = Column(Integer, nullable=False)
    page_end = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    extraction_confidence = Column(Float, default=1.0, nullable=False)
    is_uncertain = Column(Boolean, default=False, nullable=False)
    children_ids_json = Column(Text, default="[]", nullable=False)
    table_data_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_node_version_logical", "version_id", "logical_key"),
        Index("idx_node_version_reading", "version_id", "reading_order_index"),
    )

    # Relationships
    version = relationship("DocumentVersion", back_populates="nodes")

    @property
    def children_ids(self) -> List[str]:
        if self.children_ids_json:
            return json.loads(self.children_ids_json)
        return []

    @property
    def table_data(self) -> Optional[Dict[str, Any]]:
        if self.table_data_json:
            return json.loads(self.table_data_json)
        return None

    @property
    def metadata_dict(self) -> Dict[str, Any]:
        if self.metadata_json:
            return json.loads(self.metadata_json)
        return {}

    def __repr__(self):
        return f"<DocumentNodeModel(id='{self.id}', type='{self.node_type}', key='{self.logical_key}')>"
