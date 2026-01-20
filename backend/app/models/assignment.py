"""
Assignment model for offline pickup (PRD §13.2.13).
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class Assignment(Base):
    """
    Offline pickup / inbox item (PRD §13.2.13).

    Created when a system response requires acknowledgement and user hasn't acted.
    """

    __tablename__ = "assignment"

    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), nullable=False
    )
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False,
    )
    reason_code = Column(String(100), nullable=True)

    # Assignment target (one of these should be set)
    assigned_to_user_id = Column(
        UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True
    )
    assigned_to_role_id = Column(
        UUID(as_uuid=True), ForeignKey("role.role_id"), nullable=True
    )

    status = Column(String(50), default="open", nullable=False)  # open | resolved
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
