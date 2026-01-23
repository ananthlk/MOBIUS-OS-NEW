"""
SQLAlchemy models for Mobius OS (PRD §13.2).

These are the authoritative PostgreSQL tables.
"""

from .tenant import Tenant, Role, AppUser, Application, PolicyConfig, AuthProviderLink, UserSession
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
from .activity import Activity, UserActivity
from .appointment import Appointment, AppointmentReminder
from .intake import IntakeForm, InsuranceVerification, IntakeChecklist
from .user_issue import UserReportedIssue
from .detection_config import DetectionConfig
from .scheduling import Provider, ProviderSchedule, TimeSlot, ScheduleException
from .orders import ClinicalOrder, LabOrder, ImagingOrder, MedicationOrder, ReferralOrder
from .billing import PatientInsurance, Charge, Claim, Payment, PatientStatement
from .messages import MessageThread, Message, MessageAttachment, MessageRecipient, MessageTemplate
from .resolution import (
    ResolutionPlan,
    PlanStep,
    StepAnswer,
    PlanNote,
    PlanModification,
    UserRemedy,
)
from .evidence import (
    RawData,
    SourceDocument,
    Evidence,
    FactSourceLink,
    PlanStepFactLink,
)
from .sidecar import (
    UserAlert,
    UserOwnedTask,
    Milestone,
    MilestoneHistory,
    MilestoneSubstep,
)

__all__ = [
    # Tenant/user
    "Tenant",
    "Role",
    "AppUser",
    "Application",
    "PolicyConfig",
    # User Awareness - Auth
    "AuthProviderLink",
    "UserSession",
    # User Awareness - Activities
    "Activity",
    "UserActivity",
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
    # Scheduling
    "Provider",
    "ProviderSchedule",
    "TimeSlot",
    "ScheduleException",
    # Clinical Orders
    "ClinicalOrder",
    "LabOrder",
    "ImagingOrder",
    "MedicationOrder",
    "ReferralOrder",
    # Billing
    "PatientInsurance",
    "Charge",
    "Claim",
    "Payment",
    "PatientStatement",
    # Messaging
    "MessageThread",
    "Message",
    "MessageAttachment",
    "MessageRecipient",
    "MessageTemplate",
    # Resolution Plans
    "ResolutionPlan",
    "PlanStep",
    "StepAnswer",
    "PlanNote",
    "PlanModification",
    "UserRemedy",
    # Evidence (Layers 4-6)
    "RawData",
    "SourceDocument",
    "Evidence",
    "FactSourceLink",
    "PlanStepFactLink",
    # Sidecar
    "UserAlert",
    "UserOwnedTask",
    "Milestone",
    "MilestoneHistory",
    "MilestoneSubstep",
]
