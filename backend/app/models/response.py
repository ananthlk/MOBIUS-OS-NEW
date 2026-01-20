"""
System response and submission models (PRD §13.2.11-12).
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class SystemResponse(Base):
    """
    A system-emitted assessment for a patient context (PRD §13.2.11).

    Append-only: new responses supersede old ones.
    """

    __tablename__ = "system_response"

    system_response_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), nullable=False
    )
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False,
    )
    surface_type = Column(String(20), nullable=True)  # 'mini' | 'sidecar' | null
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Decision agent outputs
    proceed_indicator = Column(String(20), nullable=False, default="grey")
    execution_mode = Column(String(50), nullable=True)  # agentic | copilot | user-driven
    tasking_summary = Column(Text, nullable=True)
    rationale = Column(Text, nullable=True)

    # Correlation for tracing
    correlation_id = Column(String(100), nullable=True)

    # Relationships
    patient_context = relationship("PatientContext", back_populates="system_responses")
    submissions = relationship("MiniSubmission", back_populates="system_response")

    __table_args__ = (
        CheckConstraint(
            "proceed_indicator IN ('grey', 'green', 'yellow', 'blue', 'red')",
            name="check_proceed_indicator",
        ),
    )


class MiniSubmission(Base):
    """
    Mini-specific acknowledgement via override submission (PRD §13.2.12).

    Created when user presses Send.
    """

    __tablename__ = "mini_submission"

    mini_submission_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), nullable=False
    )
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False,
    )
    system_response_id = Column(
        UUID(as_uuid=True),
        ForeignKey("system_response.system_response_id"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=False)
    invocation_id = Column(UUID(as_uuid=True), nullable=True)  # optional FK to invocation

    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Override fields (at least one should be non-null per PRD)
    override_proceed = Column(String(20), nullable=True)
    override_tasking = Column(Text, nullable=True)

    # Note is required when overrides present
    note_text = Column(Text, nullable=False)

    # Relationships
    patient_context = relationship("PatientContext", back_populates="submissions")
    system_response = relationship("SystemResponse", back_populates="submissions")

    __table_args__ = (
        CheckConstraint(
            "note_text IS NOT NULL AND note_text != ''",
            name="check_note_required",
        ),
    )
