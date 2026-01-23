"""
Evidence models for the 6-layer architecture.

Layer 6: RawData - Actual raw content from source systems
Layer 5: SourceDocument - Catalog of documents/transactions (one-to-many with Layer 4)
Layer 4: Evidence - Extracted facts that inform probability calculations

The chain: Layer 4 → Layer 5 → Layer 6
- One source document can produce multiple facts
- Source document links to raw data for full provenance

Join Tables:
- FactSourceLink - Links facts to sources (many-to-many with metadata)
- PlanStepFactLink - Links plan steps to facts they're based on
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, Float, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


# =============================================================================
# Join Tables (for queryability and analytics)
# =============================================================================

class FactSourceLink(Base):
    """
    Join table linking Evidence (facts) to SourceDocuments.
    
    Allows many-to-many with metadata:
    - A fact can come from multiple sources (e.g., confirmed by both API and patient)
    - A source can contribute to multiple facts
    - Each link has a role and confidence score
    """
    __tablename__ = "fact_source_link"
    
    link_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence.evidence_id"),
        nullable=False
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("source_document.source_id"),
        nullable=False
    )
    
    # Role this source plays for this fact
    role = Column(String(50), nullable=False, default="primary")  # "primary", "supporting", "conflicting", "supersedes"
    
    # Confidence in this source-fact link (0.0-1.0)
    confidence = Column(Float, default=1.0, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    fact = relationship("Evidence", back_populates="source_links")
    source = relationship("SourceDocument", back_populates="fact_links")
    
    def __repr__(self):
        return f"<FactSourceLink fact={self.fact_id} source={self.source_id} role={self.role}>"


class PlanStepFactLink(Base):
    """
    Join table linking PlanSteps to Evidence (facts).
    
    Tracks which facts justify/inform each mitigation step.
    Replaces the JSONB evidence_ids array for better queryability.
    """
    __tablename__ = "plan_step_fact_link"
    
    link_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plan_step.step_id"),
        nullable=False
    )
    fact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence.evidence_id"),
        nullable=False
    )
    
    # Order/priority of this fact for the step (for display ordering)
    display_order = Column(Integer, default=0, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships defined after PlanStep import to avoid circular dependency
    
    def __repr__(self):
        return f"<PlanStepFactLink step={self.plan_step_id} fact={self.fact_id}>"


# =============================================================================
# Layer 6: RawData
# =============================================================================


class RawData(Base):
    """
    Layer 6: Actual raw content from source systems.
    
    Stores the original API response, document content, EDI payload, etc.
    This is the lowest layer - the actual data as received from the source.
    
    Examples:
    - Full 271 EDI response from Availity
    - JSON response from an API call
    - Transcript of a patient phone call
    - Scanned insurance card (file reference)
    """
    __tablename__ = "raw_data"
    
    raw_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Content type
    content_type = Column(String(50), nullable=False)  # "edi_271", "json", "text", "pdf", "image"
    
    # The actual raw content
    # For structured data (JSON, EDI parsed to JSON, text)
    raw_content = Column(JSONB, nullable=True)
    # For large files (PDFs, images) - store reference to S3/GCS
    file_reference = Column(String(500), nullable=True)
    
    # Metadata about the source
    source_system = Column(String(100), nullable=False)  # "availity", "emr", "phone_system", "portal"
    collected_at = Column(DateTime, nullable=False)  # When the data was collected from source
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant")
    source_documents = relationship("SourceDocument", back_populates="raw_data")
    
    def __repr__(self):
        return f"<RawData {self.raw_id} type={self.content_type} source={self.source_system}>"


# =============================================================================
# Layer 5: SourceDocument
# =============================================================================


class SourceDocument(Base):
    """
    Layer 5: Catalog of source documents/transactions.
    
    Each entry represents one document or transaction that can produce multiple facts.
    This is the "what" - what document do we have?
    
    Links to Layer 6 (RawData) for the actual content.
    Links from Layer 4 (Evidence) - one document can have many facts.
    
    Examples:
    - "271 eligibility check from Availity - 2025-12-08"
    - "Patient call notes - 2025-12-22"
    - "Claim denial EOB - 2025-10-15"
    """
    __tablename__ = "source_document"
    
    source_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    raw_id = Column(
        UUID(as_uuid=True),
        ForeignKey("raw_data.raw_id"),
        nullable=True  # Nullable for cases where raw data isn't stored
    )
    
    # Document identification
    document_type = Column(String(50), nullable=False)  # "eligibility_check", "claim", "patient_note", "insurance_card"
    document_label = Column(String(255), nullable=False)  # Human-readable: "271 from Availity - 2025-12-08"
    
    # Source system info
    source_system = Column(String(100), nullable=False)  # "availity", "claims_db", "emr", "phone_system"
    transaction_id = Column(String(255), nullable=True)  # External reference ID from source system
    
    # Timing
    document_date = Column(DateTime, nullable=False)  # When the document was created/received
    
    # Trust/reliability score (0.0-1.0)
    # API responses might be 0.95, patient self-report might be 0.7
    trust_score = Column(Float, default=1.0, nullable=False)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant")
    raw_data = relationship("RawData", back_populates="source_documents")
    facts = relationship("Evidence", back_populates="source_document")
    fact_links = relationship("FactSourceLink", back_populates="source")
    
    def __repr__(self):
        return f"<SourceDocument {self.source_id} type={self.document_type} label='{self.document_label}'>"


# =============================================================================
# Layer 4: Evidence
# =============================================================================
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "source_id": str(self.source_id),
            "document_type": self.document_type,
            "document_label": self.document_label,
            "source_system": self.source_system,
            "transaction_id": self.transaction_id,
            "document_date": self.document_date.isoformat() if self.document_date else None,
            "trust_score": self.trust_score,
        }


class Evidence(Base):
    """
    Layer 4: Extracted facts that inform probability calculations.
    
    Multiple facts can come from a single source document.
    This is the "so what" - what does the document tell us?
    
    Links to Layer 5 (SourceDocument) for provenance.
    Referenced by Layer 3 (PlanStep.evidence_ids) to explain rationale.
    
    Examples from one 271 response:
    - Fact 1: "Coverage was active as of 2025-12-08" (positive)
    - Fact 2: "Eligibility check is 45 days old - may be stale" (negative)
    
    Examples from patient call:
    - Fact 1: "Patient mentioned starting new job - may affect coverage" (negative)
    """
    __tablename__ = "evidence"
    
    evidence_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("source_document.source_id"),
        nullable=True  # Nullable for manually entered facts
    )
    
    # What probability factor does this evidence relate to?
    factor_type = Column(String(20), nullable=False)  # "eligibility", "coverage", "attendance", "errors"
    
    # The fact itself
    fact_type = Column(String(50), nullable=False)  # "coverage_status", "staleness", "employment_change", "claim_denial"
    fact_summary = Column(String(500), nullable=False)  # Human-readable: "Coverage was active as of 2025-12-08"
    fact_data = Column(JSONB, nullable=False)  # Structured data extracted from source
    
    # Staleness tracking
    is_stale = Column(Boolean, default=False, nullable=False)  # Batch job marks facts as stale
    stale_after = Column(DateTime, nullable=True)  # When this fact should be considered stale
    
    # Impact on probability calculation
    impact_direction = Column(String(10), nullable=True)  # "positive", "negative", "neutral"
    impact_weight = Column(Float, nullable=True)  # 0.0-1.0, how much this affects the probability
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    patient_context = relationship("PatientContext")
    source_document = relationship("SourceDocument", back_populates="facts")
    source_links = relationship("FactSourceLink", back_populates="fact")
    
    def __repr__(self):
        return f"<Evidence {self.evidence_id} type={self.fact_type} summary='{self.fact_summary[:50]}...'>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "evidence_id": str(self.evidence_id),
            "patient_context_id": str(self.patient_context_id),
            "source_id": str(self.source_id) if self.source_id else None,
            "factor_type": self.factor_type,
            "fact_type": self.fact_type,
            "fact_summary": self.fact_summary,
            "fact_data": self.fact_data,
            "is_stale": self.is_stale,
            "impact_direction": self.impact_direction,
            "impact_weight": self.impact_weight,
            "source_document": self.source_document.to_dict() if self.source_document else None,
        }
