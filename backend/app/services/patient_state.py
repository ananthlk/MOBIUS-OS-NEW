"""
SharedPatientStateCore: shared read/write services for patient state.

Both Mini and Sidecar surface routes delegate here to ensure
they reference the same underlying state (PRD invariant).
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session as DbSession

from app.db.postgres import get_db_session
from app.models import (
    PatientContext,
    PatientSnapshot,
    SystemResponse,
    MiniSubmission,
)


class PatientStateService:
    """
    Shared read/write operations for patient state.

    Ensures Mini and Sidecar always see the same underlying state.
    """

    def __init__(self, db_session: Optional[DbSession] = None):
        self._db = db_session

    @property
    def db(self) -> DbSession:
        if self._db is None:
            self._db = get_db_session()
        return self._db

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def get_patient_context(
        self, tenant_id: uuid.UUID, patient_key: str
    ) -> Optional[PatientContext]:
        """Get patient context by tenant + patient_key."""
        return (
            self.db.query(PatientContext)
            .filter(
                PatientContext.tenant_id == tenant_id,
                PatientContext.patient_key == patient_key,
            )
            .first()
        )

    def get_latest_snapshot(
        self, patient_context_id: uuid.UUID
    ) -> Optional[PatientSnapshot]:
        """Get the latest patient snapshot for a context."""
        return (
            self.db.query(PatientSnapshot)
            .filter(PatientSnapshot.patient_context_id == patient_context_id)
            .order_by(PatientSnapshot.snapshot_version.desc())
            .first()
        )

    def get_latest_system_response(
        self, patient_context_id: uuid.UUID
    ) -> Optional[SystemResponse]:
        """Get the latest system response for a patient context."""
        return (
            self.db.query(SystemResponse)
            .filter(SystemResponse.patient_context_id == patient_context_id)
            .order_by(SystemResponse.computed_at.desc())
            .first()
        )

    def get_patient_state(self, tenant_id: uuid.UUID, patient_key: str) -> dict:
        """
        Get full patient state for UI rendering.

        Returns a dict suitable for Mini/Sidecar consumption.
        """
        context = self.get_patient_context(tenant_id, patient_key)
        if not context:
            return {"found": False, "patient_key": patient_key}

        snapshot = self.get_latest_snapshot(context.patient_context_id)
        response = self.get_latest_system_response(context.patient_context_id)

        return {
            "found": True,
            "patient_key": patient_key,
            "patient_context_id": str(context.patient_context_id),
            "snapshot": (
                {
                    "display_name": snapshot.display_name,
                    "id_label": snapshot.id_label,
                    "id_masked": snapshot.id_masked,
                    "dob": snapshot.dob.isoformat() if snapshot.dob else None,
                    "version": snapshot.snapshot_version,
                }
                if snapshot
                else None
            ),
            "system_response": (
                {
                    "system_response_id": str(response.system_response_id),
                    "proceed_indicator": response.proceed_indicator,
                    "execution_mode": response.execution_mode,
                    "tasking_summary": response.tasking_summary,
                    "rationale": response.rationale,
                    "computed_at": response.computed_at.isoformat(),
                }
                if response
                else None
            ),
        }

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    def upsert_patient_context(
        self, tenant_id: uuid.UUID, patient_key: str
    ) -> PatientContext:
        """Create or update patient context."""
        context = self.get_patient_context(tenant_id, patient_key)
        if context:
            context.last_updated_at = datetime.utcnow()
        else:
            context = PatientContext(
                tenant_id=tenant_id,
                patient_key=patient_key,
            )
            self.db.add(context)
        self.db.commit()
        self.db.refresh(context)
        return context

    def create_snapshot(
        self,
        patient_context_id: uuid.UUID,
        display_name: Optional[str] = None,
        id_label: Optional[str] = None,
        id_masked: Optional[str] = None,
        dob=None,
    ) -> PatientSnapshot:
        """Create a new patient snapshot (versioned)."""
        # Get current max version
        latest = self.get_latest_snapshot(patient_context_id)
        next_version = (latest.snapshot_version + 1) if latest else 1

        snapshot = PatientSnapshot(
            patient_context_id=patient_context_id,
            snapshot_version=next_version,
            display_name=display_name,
            id_label=id_label,
            id_masked=id_masked,
            dob=dob,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def create_system_response(
        self,
        tenant_id: uuid.UUID,
        patient_context_id: uuid.UUID,
        proceed_indicator: str = "grey",
        execution_mode: Optional[str] = None,
        tasking_summary: Optional[str] = None,
        rationale: Optional[str] = None,
        surface_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> SystemResponse:
        """Create a new system response (append-only)."""
        response = SystemResponse(
            tenant_id=tenant_id,
            patient_context_id=patient_context_id,
            proceed_indicator=proceed_indicator,
            execution_mode=execution_mode,
            tasking_summary=tasking_summary,
            rationale=rationale,
            surface_type=surface_type,
            correlation_id=correlation_id,
        )
        self.db.add(response)
        self.db.commit()
        self.db.refresh(response)
        return response

    def create_submission(
        self,
        tenant_id: uuid.UUID,
        patient_context_id: uuid.UUID,
        system_response_id: uuid.UUID,
        user_id: uuid.UUID,
        note_text: str,
        override_proceed: Optional[str] = None,
        override_tasking: Optional[str] = None,
        invocation_id: Optional[uuid.UUID] = None,
    ) -> MiniSubmission:
        """
        Create a submission (acknowledgement via Send).

        Raises ValueError if note_text is empty.
        """
        if not note_text or not note_text.strip():
            raise ValueError("note_text is required for submissions")

        submission = MiniSubmission(
            tenant_id=tenant_id,
            patient_context_id=patient_context_id,
            system_response_id=system_response_id,
            user_id=user_id,
            note_text=note_text.strip(),
            override_proceed=override_proceed,
            override_tasking=override_tasking,
            invocation_id=invocation_id,
        )
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return submission
