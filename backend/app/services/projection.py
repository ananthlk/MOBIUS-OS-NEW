"""
ProjectionService: realtime Firestore projection updates (PRD §12, §13.3).

Updates denormalized documents in Firestore for fast UI subscriptions.
This is OPTIONAL - runs in no-op mode if Firestore is disabled or unavailable.

All Firestore operations are NON-BLOCKING to prevent API latency issues.
"""

import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any

from app.db.firestore import get_firestore_client, firestore_enabled, firestore_available

# Timeout for Firestore operations (seconds)
FIRESTORE_TIMEOUT = 3.0


class ProjectionService:
    """
    Manages Firestore projection documents.

    Document paths (PRD §13.3):
    - tenants/{tenant_id}/patient_state/{patient_key}
    - tenants/{tenant_id}/user_inbox/{user_id}
    
    All operations are non-blocking (fire-and-forget) to prevent
    API latency issues when Firestore is slow or unavailable.
    """

    def __init__(self):
        self._client = None
        self._enabled = None

    @property
    def enabled(self) -> bool:
        if self._enabled is None:
            self._enabled = firestore_enabled() and firestore_available()
        return self._enabled

    @property
    def client(self):
        if self._client is None:
            self._client = get_firestore_client()
        return self._client
    
    def _run_async(self, func, *args, **kwargs):
        """
        Run a function asynchronously in a daemon thread.
        
        Fire-and-forget pattern - doesn't block the caller.
        """
        def _wrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"[ProjectionService] Async operation failed: {e}")
        
        thread = threading.Thread(target=_wrapper, daemon=True)
        thread.start()
        return True

    def _get_patient_state_ref(self, tenant_id: uuid.UUID, patient_key: str):
        """Get reference to patient_state document."""
        if not self.client:
            return None
        return (
            self.client.collection("tenants")
            .document(str(tenant_id))
            .collection("patient_state")
            .document(patient_key)
        )

    def _get_user_inbox_ref(self, tenant_id: uuid.UUID, user_id: uuid.UUID):
        """Get reference to user_inbox document."""
        if not self.client:
            return None
        return (
            self.client.collection("tenants")
            .document(str(tenant_id))
            .collection("user_inbox")
            .document(str(user_id))
        )

    # -------------------------------------------------------------------------
    # Patient State Projection
    # -------------------------------------------------------------------------

    def update_patient_state(
        self,
        tenant_id: uuid.UUID,
        patient_key: str,
        snapshot: Optional[Dict[str, Any]] = None,
        system_response: Optional[Dict[str, Any]] = None,
        last_submission: Optional[Dict[str, Any]] = None,
        flags: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update patient_state projection document (NON-BLOCKING).

        Uses merge to only update provided fields.
        Returns True if update was queued, False if Firestore is disabled.
        """
        if not self.enabled:
            # Silent skip - don't log every time
            return False

        ref = self._get_patient_state_ref(tenant_id, patient_key)
        if not ref:
            return False

        data: Dict[str, Any] = {
            "patient_key": patient_key,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if snapshot is not None:
            data["snapshot"] = snapshot
        if system_response is not None:
            data["latest_system_response"] = system_response
        if last_submission is not None:
            data["last_submission"] = last_submission
        if flags is not None:
            data["flags"] = flags

        def _do_update():
            ref.set(data, merge=True)
            print(f"[ProjectionService] Updated patient_state: {tenant_id}/{patient_key}")
        
        # Fire and forget - don't block API response
        return self._run_async(_do_update)

    def update_patient_state_from_response(
        self,
        tenant_id: uuid.UUID,
        patient_key: str,
        system_response_id: uuid.UUID,
        proceed_indicator: str,
        execution_mode: Optional[str],
        tasking_summary: Optional[str],
        computed_at: datetime,
    ) -> bool:
        """Update patient_state projection after a new SystemResponse."""
        return self.update_patient_state(
            tenant_id=tenant_id,
            patient_key=patient_key,
            system_response={
                "system_response_id": str(system_response_id),
                "proceed_indicator": proceed_indicator,
                "execution_mode": execution_mode,
                "tasking_summary": tasking_summary,
                "computed_at": computed_at.isoformat(),
            },
            flags={"needs_ack": proceed_indicator in ("yellow", "green")},
        )

    def update_patient_state_from_submission(
        self,
        tenant_id: uuid.UUID,
        patient_key: str,
        submission_id: uuid.UUID,
        user_id: uuid.UUID,
        submitted_at: datetime,
    ) -> bool:
        """Update patient_state projection after a new submission."""
        return self.update_patient_state(
            tenant_id=tenant_id,
            patient_key=patient_key,
            last_submission={
                "submission_id": str(submission_id),
                "user_id": str(user_id),
                "submitted_at": submitted_at.isoformat(),
            },
            flags={"needs_ack": False},
        )

    # -------------------------------------------------------------------------
    # User Inbox Projection
    # -------------------------------------------------------------------------

    def add_assignment_to_inbox(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        assignment_id: uuid.UUID,
        patient_key: str,
        reason_code: Optional[str],
        created_at: datetime,
    ) -> bool:
        """Add an assignment to user's inbox projection (NON-BLOCKING)."""
        if not self.enabled:
            return False

        ref = self._get_user_inbox_ref(tenant_id, user_id)
        if not ref:
            return False

        assignment_entry = {
            "assignment_id": str(assignment_id),
            "patient_key": patient_key,
            "reason_code": reason_code,
            "created_at": created_at.isoformat(),
            "status": "open",
        }

        def _do_update():
            from google.cloud.firestore import ArrayUnion
            ref.set(
                {
                    "open_assignments": ArrayUnion([assignment_entry]),
                    "updated_at": datetime.utcnow().isoformat(),
                },
                merge=True,
            )
            print(f"[ProjectionService] Added assignment to inbox: {user_id}")
        
        return self._run_async(_do_update)

    def remove_assignment_from_inbox(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> bool:
        """Remove a resolved assignment from user's inbox projection (NON-BLOCKING)."""
        if not self.enabled:
            return False

        ref = self._get_user_inbox_ref(tenant_id, user_id)
        if not ref:
            return False

        def _do_update():
            # Get current doc and filter out the assignment
            doc = ref.get()
            if not doc.exists:
                return

            data = doc.to_dict()
            assignments = data.get("open_assignments", [])
            updated = [a for a in assignments if a.get("assignment_id") != str(assignment_id)]

            ref.update(
                {
                    "open_assignments": updated,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            print(f"[ProjectionService] Removed assignment from inbox: {assignment_id}")
        
        return self._run_async(_do_update)
