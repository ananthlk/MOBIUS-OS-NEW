"""
Event log model for audit (PRD §13.2.14).

Append-only ledger with PHI-safe payloads.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.postgres import Base


class EventLog(Base):
    """
    Append-only audit ledger (PRD §13.2.14).

    PHI-safe payloads only - no raw MRN, SSN, etc.
    """

    __tablename__ = "event_log"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), nullable=False
    )
    event_type = Column(String(100), nullable=False)  # System.Response, User.Acknowledged, etc.

    # Optional references
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=True,
    )
    invocation_id = Column(UUID(as_uuid=True), nullable=True)
    actor_user_id = Column(
        UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True
    )

    # PHI-safe payload
    payload_json = Column(JSONB, nullable=True)

    # Timestamps and correlation
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    correlation_id = Column(String(100), nullable=True)
