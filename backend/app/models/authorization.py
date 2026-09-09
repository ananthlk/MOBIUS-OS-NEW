"""AuthorizationLog — the extension's invocation-correlation table.

Provenance source of truth for PHI authorizations. Keyed by the client-minted
task_id; the PHI agent's compliance log stores the attestation under the same
task_id. PHI-safe: host + hashed URL + MASKED identifier labels only.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.postgres import Base


class AuthorizationLog(Base):
    __tablename__ = "authorization_log"

    task_id = Column(String(64), primary_key=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    surface = Column(String(32), nullable=False)
    origin_host = Column(String(255), nullable=True)
    origin_url_sha256 = Column(String(64), nullable=True)
    action = Column(String(32), nullable=False)
    phi_present = Column(Boolean, nullable=False, default=False)
    phi_labels = Column(JSONB, nullable=True)
    chat_correlation_id = Column(String(64), nullable=True)
    phi_audit_ref = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Recognized authorization actions (validated at the API boundary).
    ACTIONS = {
        "phi_ack_on",       # PHI toggle turned ON (attestation for the site)
        "phi_ack_off",      # PHI toggle turned OFF (revoked)
        "read_ack",         # per-read consent accepted in the ack card
        "read_auto",        # read auto-attached under a prior grant
        "override_send",    # server PHI block overridden and sent
        "site_grant",       # "Always on this site" (non-PHI) granted
    }
