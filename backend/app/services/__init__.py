"""
Backend services for Mobius OS.

- SharedPatientStateCore: shared read/write operations for patient state
- EventLogService: append-only audit events
- ProjectionService: realtime Firestore projection updates
"""

from .patient_state import PatientStateService
from .event_log import EventLogService
from .projection import ProjectionService

__all__ = [
    "PatientStateService",
    "EventLogService",
    "ProjectionService",
]
