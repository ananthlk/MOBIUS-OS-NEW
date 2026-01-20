"""
Invocation and session models (PRD §13.2.6-7).
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class Invocation(Base):
    """
    Represents a single Mini/Sidecar instance, e.g., a browser tab (PRD §13.2.6).
    """

    __tablename__ = "invocation"

    invocation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), nullable=False
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=False)
    application_id = Column(
        UUID(as_uuid=True), ForeignKey("application.application_id"), nullable=True
    )
    page_signature = Column(String(500), nullable=True)  # URL pattern or page identifier
    surface_type = Column(String(20), nullable=False)  # 'mini' | 'sidecar'
    ui_variant_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), default="active", nullable=False)


class Session(Base):
    """
    Time-bounded activity within an invocation (PRD §13.2.7).
    """

    __tablename__ = "session"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invocation_id = Column(
        UUID(as_uuid=True), ForeignKey("invocation.invocation_id"), nullable=False
    )
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    end_reason = Column(String(100), nullable=True)  # timeout | navigation | explicit
