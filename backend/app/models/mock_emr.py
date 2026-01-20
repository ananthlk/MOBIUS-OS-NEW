"""
Mock EMR clinical data model.

This table stores clinical data for the mock EMR page, including:
- Allergies
- Medications
- Vitals
- Recent visits
- Provider information
- Emergency contact

This data is displayed on the mock EMR page for testing the Mini extension.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class MockEmrRecord(Base):
    """
    Clinical data for the mock EMR page.
    
    One record per patient. All clinical fields are stored here,
    separate from the ID translation layer (patient_ids table).
    """

    __tablename__ = "mock_emr"

    mock_emr_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False,
    )
    
    # Clinical data (JSONB for flexibility)
    allergies = Column(JSONB, nullable=True)  # ["Penicillin", "Sulfa"]
    medications = Column(JSONB, nullable=True)  # [{"name": "Metformin", "dose": "500mg", "frequency": "BID"}]
    vitals = Column(JSONB, nullable=True)  # {"bp": "120/80", "hr": 72, "temp": 98.6, "weight_lbs": 165}
    recent_visits = Column(JSONB, nullable=True)  # [{"date": "2026-01-10", "type": "Office Visit", "provider": "Dr. Smith"}]
    
    # Provider info
    primary_care_provider = Column(String(255), nullable=True)
    
    # Emergency contact
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    emergency_contact_relation = Column(String(100), nullable=True)
    
    # Additional clinical
    blood_type = Column(String(10), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    patient_context = relationship("PatientContext", backref="mock_emr_records")
    
    __table_args__ = (
        # One mock_emr record per patient
        UniqueConstraint('patient_context_id', name='uq_mock_emr_patient_context'),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "allergies": self.allergies or [],
            "medications": self.medications or [],
            "vitals": self.vitals or {},
            "recent_visits": self.recent_visits or [],
            "primary_care_provider": self.primary_care_provider,
            "emergency_contact": {
                "name": self.emergency_contact_name,
                "phone": self.emergency_contact_phone,
                "relation": self.emergency_contact_relation,
            } if self.emergency_contact_name else None,
            "blood_type": self.blood_type,
        }
    
    def __repr__(self):
        return f"<MockEmrRecord patient_context_id={self.patient_context_id}>"
