"""
SQLAlchemy models for Mobius OS (PRD §13.2).

These are the authoritative PostgreSQL tables.
"""

from .tenant import Tenant, Role, AppUser, Application, PolicyConfig
from .patient import PatientIdentityRef, PatientContext, PatientSnapshot
from .response import SystemResponse, MiniSubmission
from .assignment import Assignment
from .event_log import EventLog
from .invocation import Invocation, Session
from .patient_ids import PatientId
from .mock_emr import MockEmrRecord
from .probability import (
    PaymentProbability,
    TaskTemplate,
    TaskStep,
    TaskInstance,
    StepInstance,
    UserPreference,
)
from .appointment import Appointment, AppointmentReminder
from .intake import IntakeForm, InsuranceVerification, IntakeChecklist
from .user_issue import UserReportedIssue
from .detection_config import DetectionConfig

__all__ = [
    # Tenant/user
    "Tenant",
    "Role",
    "AppUser",
    "Application",
    "PolicyConfig",
    # Patient
    "PatientIdentityRef",
    "PatientContext",
    "PatientSnapshot",
    # Patient ID translation layer
    "PatientId",
    # Mock EMR clinical data
    "MockEmrRecord",
    # Response/submission
    "SystemResponse",
    "MiniSubmission",
    # Assignment
    "Assignment",
    # Audit
    "EventLog",
    # Invocation
    "Invocation",
    "Session",
    # Probability and Tasks
    "PaymentProbability",
    "TaskTemplate",
    "TaskStep",
    "TaskInstance",
    "StepInstance",
    "UserPreference",
    # CRM/Scheduler - Appointments
    "Appointment",
    "AppointmentReminder",
    # CRM/Scheduler - Intake
    "IntakeForm",
    "InsuranceVerification",
    "IntakeChecklist",
    # User-reported issues
    "UserReportedIssue",
    # Detection configuration
    "DetectionConfig",
]
