"""
EventLogService: append-only audit event logging (PRD §6, §13.2.14).

PHI-safe payloads only - no raw MRN, SSN, etc.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session as DbSession

from app.db.postgres import get_db_session
from app.models import EventLog


class EventLogService:
    """
    Append-only audit event logging.

    Event types from PRD §6:
    - System.Response: Mobius surfaces/updates computed state
    - User.Interaction: Optional navigational events (non-committal)
    - User.Acknowledged: User pressed Send (state-committing)
    """

    # Standard event types
    SYSTEM_RESPONSE = "System.Response"
    USER_INTERACTION = "User.Interaction"
    USER_ACKNOWLEDGED = "User.Acknowledged"

    def __init__(self, db_session: Optional[DbSession] = None):
        self._explicit_db = db_session  # Only set if explicitly passed

    @property
    def db(self) -> DbSession:
        # Always get a fresh session unless explicitly passed
        if self._explicit_db is not None:
            return self._explicit_db
        return get_db_session()

    def append_event(
        self,
        tenant_id: uuid.UUID,
        event_type: str,
        patient_context_id: Optional[uuid.UUID] = None,
        invocation_id: Optional[uuid.UUID] = None,
        actor_user_id: Optional[uuid.UUID] = None,
        payload: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> EventLog:
        """
        Append an event to the audit log.

        This is INSERT-only; events are never updated or deleted.
        """
        # Validate payload is PHI-safe (basic check)
        sanitized_payload = self._sanitize_payload(payload) if payload else None

        event = EventLog(
            tenant_id=tenant_id,
            event_type=event_type,
            patient_context_id=patient_context_id,
            invocation_id=invocation_id,
            actor_user_id=actor_user_id,
            payload_json=sanitized_payload,
            correlation_id=correlation_id,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def log_system_response(
        self,
        tenant_id: uuid.UUID,
        patient_context_id: uuid.UUID,
        system_response_id: uuid.UUID,
        proceed_indicator: str,
        execution_mode: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> EventLog:
        """Log a System.Response event."""
        return self.append_event(
            tenant_id=tenant_id,
            event_type=self.SYSTEM_RESPONSE,
            patient_context_id=patient_context_id,
            payload={
                "system_response_id": str(system_response_id),
                "proceed_indicator": proceed_indicator,
                "execution_mode": execution_mode,
            },
            correlation_id=correlation_id,
        )

    def log_user_acknowledged(
        self,
        tenant_id: uuid.UUID,
        patient_context_id: uuid.UUID,
        user_id: uuid.UUID,
        submission_id: uuid.UUID,
        system_response_id: uuid.UUID,
        has_overrides: bool = False,
        correlation_id: Optional[str] = None,
    ) -> EventLog:
        """Log a User.Acknowledged event (Send pressed)."""
        return self.append_event(
            tenant_id=tenant_id,
            event_type=self.USER_ACKNOWLEDGED,
            patient_context_id=patient_context_id,
            actor_user_id=user_id,
            payload={
                "submission_id": str(submission_id),
                "system_response_id": str(system_response_id),
                "has_overrides": has_overrides,
            },
            correlation_id=correlation_id,
        )

    def log_user_interaction(
        self,
        tenant_id: uuid.UUID,
        invocation_id: uuid.UUID,
        user_id: uuid.UUID,
        interaction_type: str,
        patient_context_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[str] = None,
    ) -> EventLog:
        """Log a User.Interaction event (optional, non-committal)."""
        return self.append_event(
            tenant_id=tenant_id,
            event_type=self.USER_INTERACTION,
            patient_context_id=patient_context_id,
            invocation_id=invocation_id,
            actor_user_id=user_id,
            payload={"interaction_type": interaction_type},
            correlation_id=correlation_id,
        )

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Basic PHI sanitization for audit payloads.

        TODO: Implement more robust PHI detection/redaction.
        """
        # List of keys that should never appear in audit logs
        phi_keys = {"mrn", "ssn", "social_security", "dob", "date_of_birth", "address"}

        sanitized = {}
        for key, value in payload.items():
            key_lower = key.lower()
            if key_lower in phi_keys:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_payload(value)
            else:
                sanitized[key] = value
        return sanitized
