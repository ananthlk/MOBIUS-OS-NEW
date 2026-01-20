"""
Patient context and snapshot models (PRD §13.2.8-10).
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Date, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class PatientIdentityRef(Base):
    """
    Optional mapping to an external/master patient record (PRD §13.2.8).

    Use when you have a stable external identifier.
    """

    __tablename__ = "patient_identity_ref"

    patient_identity_ref_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), nullable=False
    )
    source_system = Column(String(100), nullable=True)  # e.g., EHR name
    external_patient_id_hash = Column(String(255), nullable=False)  # one-way hash
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PatientContext(Base):
    """
    Mobius-owned anchor for UI state (PRD §13.2.9).

    Scoped to tenant + patient_key (tokenized).
    """

    __tablename__ = "patient_context"

    patient_context_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), nullable=False
    )
    patient_key = Column(String(255), nullable=False)  # tokenized, no raw MRN
    patient_identity_ref_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_identity_ref.patient_identity_ref_id"),
        nullable=True,
    )
    
    # User override of attention status (from Mini dropdown)
    # Values: "resolved" | "confirmed_unresolved" | "unable_to_confirm" | null
    attention_status = Column(String(30), nullable=True)
    attention_status_at = Column(DateTime, nullable=True)
    attention_status_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=True,
    )
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Uniqueness constraint: (tenant_id, patient_key)
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    # Relationships
    snapshots = relationship("PatientSnapshot", back_populates="patient_context")
    system_responses = relationship("SystemResponse", back_populates="patient_context")
    submissions = relationship("MiniSubmission", back_populates="patient_context")


class PatientSnapshot(Base):
    """
    Display-only patient fields shown in Mini (PRD §13.2.10).

    Versioned - each update creates a new row.
    Includes decision-relevant flags used by decision agents.
    """

    __tablename__ = "patient_snapshot"

    patient_snapshot_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False,
    )
    snapshot_version = Column(Integer, default=1, nullable=False)
    
    # Display fields
    display_name = Column(String(255), nullable=True)  # policy-controlled
    id_label = Column(String(100), nullable=True)  # e.g., "MRN", "ID"
    id_masked = Column(String(100), nullable=True)  # masked identifier
    dob = Column(Date, nullable=True)
    
    # Decision-relevant flags (used by decision agents)
    verified = Column(Boolean, default=False, nullable=False)
    data_complete = Column(Boolean, default=False, nullable=False)
    critical_alert = Column(Boolean, default=False, nullable=False)
    needs_review = Column(Boolean, default=False, nullable=False)
    additional_info_available = Column(Boolean, default=False, nullable=False)
    
    # Warnings (stored as JSON array)
    warnings = Column(JSONB, nullable=True)  # ["Warning 1", "Warning 2"]
    
    # Extended data (flexible JSONB for additional attributes)
    extended_data = Column(JSONB, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(255), nullable=True)  # user or system that created
    source = Column(String(100), nullable=True)  # e.g., "ehr_sync", "manual", "api"

    # Relationships
    patient_context = relationship("PatientContext", back_populates="snapshots")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "display_name": self.display_name,
            "id_label": self.id_label,
            "id_masked": self.id_masked,
            "dob": self.dob.isoformat() if self.dob else None,
            "verified": self.verified,
            "data_complete": self.data_complete,
            "critical_alert": self.critical_alert,
            "needs_review": self.needs_review,
            "additional_info_available": self.additional_info_available,
            "warnings": self.warnings,
            "version": self.snapshot_version,
        }