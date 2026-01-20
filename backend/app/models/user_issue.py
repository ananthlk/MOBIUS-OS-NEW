"""
User-reported issues model.

Stores issues reported by users from the Mini widget.
These are queued for batch job processing to calculate probabilities.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class UserReportedIssue(Base):
    """
    User-reported issues from Mini widget.
    
    Status flow: pending -> processed | dismissed
    Batch job picks up pending issues, calculates probability,
    creates PaymentProbability record, then marks as processed.
    """

    __tablename__ = "user_reported_issue"

    issue_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_context_id = Column(
        UUID(as_uuid=True), ForeignKey("patient_context.patient_context_id"), nullable=False
    )
    reported_by_id = Column(
        UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True
    )
    issue_text = Column(String(500), nullable=False)
    status = Column(
        String(20), default="pending", nullable=False,
        comment="pending | processed | dismissed"
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    # Optional: link to resulting PaymentProbability after processing
    payment_probability_id = Column(
        UUID(as_uuid=True), ForeignKey("payment_probability.probability_id"), nullable=True
    )
