"""
Patient ID translation layer for mapping external identifiers to internal Mobius UUIDs.

This table serves as the universal translation layer between external systems
(EMR MRNs, insurance IDs, lab IDs, etc.) and internal Mobius patient_context_id UUIDs.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class PatientId(Base):
    """
    Maps external identifiers to internal patient_context_id.
    
    Each patient can have multiple IDs of different types (MRN, insurance, lab, etc.).
    This is the single source of truth for ID translation across the system.
    """

    __tablename__ = "patient_ids"

    patient_id_record = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False,
    )
    
    # Identifier details
    id_type = Column(String(50), nullable=False)  # 'mrn', 'insurance', 'lab_id', 'ssn_hash'
    id_value = Column(String(255), nullable=False)  # The actual identifier value
    source_system = Column(String(100), nullable=True)  # 'epic', 'cerner', 'blue_cross', etc.
    
    # Metadata
    is_primary = Column(Boolean, default=False, nullable=False)  # Primary ID for this type?
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration for temp IDs
    
    # Relationships
    patient_context = relationship("PatientContext", backref="patient_ids")
    
    __table_args__ = (
        # No duplicate IDs of the same type
        UniqueConstraint('id_type', 'id_value', name='uq_patient_ids_type_value'),
        # Indexes for fast lookups
        Index('idx_patient_ids_type_value', 'id_type', 'id_value'),
        Index('idx_patient_ids_context', 'patient_context_id'),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id_type": self.id_type,
            "id_value": self.id_value,
            "source_system": self.source_system,
            "is_primary": self.is_primary,
        }
    
    def __repr__(self):
        return f"<PatientId {self.id_type}={self.id_value}>"
