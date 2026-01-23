"""
Mobius OS - Demo Data Seed v2

Simulates what the batch job produces: intelligent, context-aware resolution plans
based on patient history, risk factors, and real-world scenarios.

The batch job analyzes:
- Patient visit history (last visit date, frequency)
- Employment/life changes (job changes affect insurance)
- No-show history (attendance risk)
- Insurance verification history
- Payer-specific requirements
- Clinical documentation status
- And generates appropriate decision trees

This seed script creates realistic demo data that mirrors batch job output.
"""

import uuid
import random
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models.tenant import Tenant, AppUser
from app.models.activity import Activity, UserActivity
from app.models.patient import PatientContext, PatientSnapshot
from app.models.patient_ids import PatientId
from app.models.mock_emr import MockEmrRecord
from app.models.resolution import (
    ResolutionPlan,
    PlanStep,
    StepAnswer,
    PlanNote,
    PlanStatus,
    StepStatus,
    StepType,
    InputType,
    FactorType,
    AnswerMode,
)
from app.models.probability import PaymentProbability, TaskTemplate, TaskInstance
from app.models.evidence import PlanStepFactLink, Evidence, SourceDocument, RawData, FactSourceLink
from app.services.auth_service import AuthService


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_PASSWORD = "demo1234"


# =============================================================================
# REALISTIC PATIENT SCENARIOS
# Each scenario includes context that the batch job would have analyzed
# =============================================================================

PATIENT_SCENARIOS = [
    # =========================================================================
    # ELIGIBILITY SCENARIOS
    # =========================================================================
    {
        "scenario_id": "elig_no_insurance_info",
        "scenario_name": "No Insurance on File",
        "patient_name": "Maria Santos",
        "description": "New patient, no insurance information collected yet",
        "batch_context": {
            "is_new_patient": True,
            "last_visit": None,
            "insurance_on_file": False,
            "previous_payer": None,
        },
        "gap_types": ["eligibility"],
        "status": "active",
        "probability_profile": {"overall": 0.35, "eligibility": 0.20, "coverage": 0.70, "attendance": 0.85, "errors": 0.90},
        # Batch recommendation
        "agentic_confidence": 0.82,
        "recommended_mode": "mobius",
        "recommendation_reason": "High success rate for insurance lookup, multiple automated options available",
        "agentic_actions": ["search_history", "check_medicaid", "send_portal"],
        "steps": [
            {
                "question": "No insurance information on file - how should we proceed?",
                "code": "no_insurance_triage",
                "factor": "eligibility",
                "options": [
                    {"code": "patient_has_info", "label": "Patient has insurance - collect info"},
                    {"code": "search_history", "label": "Search patient history for prior coverage"},
                    {"code": "check_medicaid", "label": "Check Medicaid/Medicare eligibility"},
                    {"code": "self_pay", "label": "Patient is self-pay"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Search external databases for coverage",
            },
            {
                "question": "Contact patient to collect insurance information?",
                "code": "contact_for_insurance",
                "factor": "eligibility",
                "options": [
                    {"code": "send_portal", "label": "Send portal message"},
                    {"code": "send_sms", "label": "Send SMS request"},
                    {"code": "call_patient", "label": "Call patient directly"},
                    {"code": "wait_checkin", "label": "Collect at check-in"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Send automated insurance request via portal/SMS",
            },
        ],
    },
    {
        "scenario_id": "elig_expired_coverage",
        "scenario_name": "Insurance Expired",
        "patient_name": "Robert Kim",
        "description": "Coverage expired 2 weeks ago, patient may have renewed",
        "batch_context": {
            "is_new_patient": False,
            "last_visit": "45 days ago",
            "insurance_on_file": True,
            "coverage_end_date": "2 weeks ago",
            "payer": "Blue Cross",
            "likely_reason": "Annual renewal period",
        },
        "gap_types": ["eligibility"],
        "status": "active",
        "probability_profile": {"overall": 0.48, "eligibility": 0.30, "coverage": 0.78, "attendance": 0.88, "errors": 0.92},
        # Batch recommendation
        "agentic_confidence": 0.75,
        "recommended_mode": "mobius",
        "recommendation_reason": "Can verify renewal status via 270/271, high automation potential",
        "agentic_actions": ["run_eligibility_check"],
        "steps": [
            {
                "question": "Insurance coverage expired 2 weeks ago - has patient renewed?",
                "code": "check_renewal",
                "factor": "eligibility",
                "options": [
                    {"code": "yes_renewed", "label": "Yes - Patient renewed coverage"},
                    {"code": "no_not_renewed", "label": "No - Coverage lapsed"},
                    {"code": "unknown", "label": "Unknown - Need to verify with patient"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Run 270/271 to check current eligibility status",
            },
            {
                "question": "If coverage lapsed, explore alternative options?",
                "code": "coverage_alternatives",
                "factor": "eligibility",
                "options": [
                    {"code": "new_employer", "label": "Check for new employer coverage"},
                    {"code": "marketplace", "label": "Explore marketplace options"},
                    {"code": "medicaid", "label": "Screen for Medicaid eligibility"},
                    {"code": "self_pay", "label": "Discuss self-pay arrangements"},
                ],
                "mobius_can_handle": False,
                "mobius_action": None,
            },
        ],
    },
    {
        "scenario_id": "elig_missing_card",
        "scenario_name": "Missing Insurance Card",
        "patient_name": "Jennifer Lee",
        "description": "Insurance info in system but card not on file, can't verify details",
        "batch_context": {
            "is_new_patient": False,
            "last_visit": "3 months ago",
            "insurance_on_file": True,
            "card_on_file": False,
            "payer": "Aetna",
            "last_verified": "6 months ago",
        },
        "gap_types": ["eligibility"],
        "status": "active",
        "probability_profile": {"overall": 0.55, "eligibility": 0.42, "coverage": 0.80, "attendance": 0.90, "errors": 0.92},
        # Batch recommendation
        "agentic_confidence": 0.78,
        "recommended_mode": "mobius",
        "recommendation_reason": "Can check portal for uploads and send automated card request",
        "agentic_actions": ["check_portal_uploads", "send_card_request", "run_verification"],
        "steps": [
            {
                "question": "Insurance card not on file - need current card to verify coverage",
                "code": "collect_card",
                "factor": "eligibility",
                "options": [
                    {"code": "card_uploaded", "label": "Patient uploaded card to portal"},
                    {"code": "will_bring", "label": "Patient will bring card to visit"},
                    {"code": "request_card", "label": "Send request for card image"},
                    {"code": "verify_without", "label": "Attempt verification with existing info"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Check portal for recent uploads, send card request if none",
            },
            {
                "question": "Run eligibility verification with available information?",
                "code": "run_verification",
                "factor": "eligibility",
                "options": [
                    {"code": "verified_active", "label": "Verified - Coverage is active"},
                    {"code": "verified_inactive", "label": "Verified - Coverage is NOT active"},
                    {"code": "unable_verify", "label": "Unable to verify - need more info"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Run 270/271 eligibility check with Aetna",
            },
        ],
    },
    {
        "scenario_id": "elig_job_change",
        "scenario_name": "Possible Job Change",
        "patient_name": "David Chen",
        "description": "6+ months since last visit, employment status may have changed",
        "batch_context": {
            "is_new_patient": False,
            "last_visit": "8 months ago",
            "insurance_on_file": True,
            "payer": "United Healthcare",
            "employer_coverage": True,
            "risk_flag": "Long gap since last visit - verify current employment/coverage",
        },
        "gap_types": ["eligibility"],
        "status": "active",
        "probability_profile": {"overall": 0.52, "eligibility": 0.38, "coverage": 0.75, "attendance": 0.85, "errors": 0.90},
        # Batch recommendation
        "agentic_confidence": 0.55,
        "recommended_mode": "together",
        "recommendation_reason": "Employment verification may require patient contact, partial automation possible",
        "agentic_actions": ["run_eligibility_check"],
        "steps": [
            {
                "question": "8 months since last visit - confirm insurance is still active?",
                "code": "verify_after_gap",
                "factor": "eligibility",
                "options": [
                    {"code": "same_coverage", "label": "Same coverage - verified active"},
                    {"code": "new_coverage", "label": "Patient has new insurance"},
                    {"code": "no_coverage", "label": "Patient no longer has coverage"},
                    {"code": "need_to_ask", "label": "Need to confirm with patient"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Run eligibility check, flag if different payer responds",
            },
            {
                "question": "Has patient's employment status changed?",
                "code": "employment_check",
                "factor": "eligibility",
                "options": [
                    {"code": "same_employer", "label": "Same employer"},
                    {"code": "new_employer", "label": "New employer - get new insurance info"},
                    {"code": "unemployed", "label": "Currently unemployed - explore options"},
                    {"code": "retired", "label": "Retired - check Medicare eligibility"},
                ],
                "mobius_can_handle": False,
                "mobius_action": None,
            },
        ],
    },
    {
        "scenario_id": "elig_new_patient",
        "scenario_name": "New Patient Intake",
        "patient_name": "Amanda Foster",
        "description": "First visit, need complete insurance verification",
        "batch_context": {
            "is_new_patient": True,
            "registration_complete": False,
            "insurance_provided": True,
            "card_uploaded": True,
            "verification_status": "pending",
        },
        "gap_types": ["eligibility"],
        "status": "active",
        "probability_profile": {"overall": 0.50, "eligibility": 0.35, "coverage": 0.72, "attendance": 0.82, "errors": 0.88},
        # Batch recommendation
        "agentic_confidence": 0.85,
        "recommended_mode": "mobius",
        "recommendation_reason": "Card uploaded, can run full verification automatically",
        "agentic_actions": ["run_verification", "check_benefits"],
        "steps": [
            {
                "question": "New patient - verify insurance eligibility before first visit",
                "code": "new_patient_verify",
                "factor": "eligibility",
                "options": [
                    {"code": "verified_active", "label": "Verified - Coverage active"},
                    {"code": "verified_inactive", "label": "Verified - Coverage NOT active"},
                    {"code": "pending", "label": "Verification in progress"},
                    {"code": "unable", "label": "Unable to verify - need more info"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Run real-time eligibility verification",
            },
            {
                "question": "Confirm benefits cover the scheduled service type?",
                "code": "benefit_check",
                "factor": "eligibility",
                "options": [
                    {"code": "covered", "label": "Yes - Service is covered"},
                    {"code": "not_covered", "label": "No - Service not covered"},
                    {"code": "partial", "label": "Partially covered - copay/coinsurance applies"},
                    {"code": "verify", "label": "Need to verify with payer"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Check benefit details for service type",
            },
        ],
    },
    
    # =========================================================================
    # ATTENDANCE SCENARIOS
    # =========================================================================
    {
        "scenario_id": "attend_no_confirmation",
        "scenario_name": "Awaiting Confirmation",
        "patient_name": "Emily Davis",
        "description": "Appointment in 3 days, patient hasn't confirmed",
        "batch_context": {
            "appointment_date": "3 days from now",
            "confirmation_sent": True,
            "confirmation_received": False,
            "no_show_history": "0 no-shows in past year",
            "preferred_contact": "SMS",
        },
        "gap_types": ["attendance"],
        "status": "active",
        "probability_profile": {"overall": 0.72, "eligibility": 0.92, "coverage": 0.88, "attendance": 0.55, "errors": 0.95},
        # Batch recommendation
        "agentic_confidence": 0.88,
        "recommended_mode": "mobius",
        "recommendation_reason": "Simple reminder, patient prefers SMS, no history of no-shows",
        "agentic_actions": ["send_sms_reminder"],
        "steps": [
            {
                "question": "Appointment in 3 days - patient hasn't confirmed yet",
                "code": "get_confirmation",
                "factor": "attendance",
                "options": [
                    {"code": "confirmed", "label": "Patient confirmed attendance"},
                    {"code": "send_reminder", "label": "Send another reminder"},
                    {"code": "call_patient", "label": "Call patient to confirm"},
                    {"code": "no_response", "label": "No response - flag as at-risk"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Send SMS reminder, await response",
            },
        ],
    },
    {
        "scenario_id": "attend_transport_barrier",
        "scenario_name": "Transportation Needed",
        "patient_name": "James Wilson",
        "description": "Patient flagged transportation as barrier in previous visit",
        "batch_context": {
            "appointment_date": "5 days from now",
            "transportation_barrier": True,
            "previous_transport_issue": "Missed appointment 2 months ago due to transport",
            "medicaid_eligible": True,
            "location": "Rural area - 25 miles from clinic",
        },
        "gap_types": ["attendance"],
        "status": "active",
        "probability_profile": {"overall": 0.62, "eligibility": 0.90, "coverage": 0.85, "attendance": 0.40, "errors": 0.92},
        # Batch recommendation
        "agentic_confidence": 0.72,
        "recommended_mode": "mobius",
        "recommendation_reason": "Patient is Medicaid eligible, can book transport automatically",
        "agentic_actions": ["book_medicaid_transport", "check_transport_status"],
        "steps": [
            {
                "question": "Patient has transportation barrier - arrange transport?",
                "code": "arrange_transport",
                "factor": "attendance",
                "options": [
                    {"code": "medicaid_transport", "label": "Schedule Medicaid transportation"},
                    {"code": "ride_service", "label": "Arrange ride service"},
                    {"code": "family_transport", "label": "Family member will provide transport"},
                    {"code": "telehealth", "label": "Convert to telehealth visit"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Book Medicaid transport (patient is eligible)",
            },
            {
                "question": "Confirm transportation is arranged?",
                "code": "confirm_transport",
                "factor": "attendance",
                "options": [
                    {"code": "confirmed", "label": "Transport confirmed"},
                    {"code": "pending", "label": "Transport request pending"},
                    {"code": "unavailable", "label": "No transport available - reschedule"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Check transport booking status",
            },
        ],
    },
    {
        "scenario_id": "attend_high_noshow_risk",
        "scenario_name": "High No-Show Risk",
        "patient_name": "Patricia Garcia",
        "description": "Patient has history of missed appointments",
        "batch_context": {
            "appointment_date": "2 days from now",
            "no_show_history": "3 no-shows in past 6 months",
            "cancellation_history": "2 late cancellations",
            "risk_score": "High",
            "last_successful_visit": "4 months ago",
        },
        "gap_types": ["attendance"],
        "status": "active",
        "probability_profile": {"overall": 0.58, "eligibility": 0.88, "coverage": 0.85, "attendance": 0.35, "errors": 0.90},
        # Batch recommendation
        "agentic_confidence": 0.35,
        "recommended_mode": "manual",
        "recommendation_reason": "High-risk patient requires personal outreach, automated reminders unlikely to help",
        "agentic_actions": [],
        "steps": [
            {
                "question": "High no-show risk patient - take proactive steps?",
                "code": "noshow_intervention",
                "factor": "attendance",
                "options": [
                    {"code": "personal_call", "label": "Personal call from care team"},
                    {"code": "day_before_reminder", "label": "Day-before reminder call"},
                    {"code": "confirm_barriers", "label": "Ask about barriers to attendance"},
                    {"code": "overbook_slot", "label": "Flag slot for potential overbooking"},
                ],
                "mobius_can_handle": False,
                "mobius_action": None,
            },
            {
                "question": "Has patient confirmed they will attend?",
                "code": "verbal_confirmation",
                "factor": "attendance",
                "options": [
                    {"code": "yes_confirmed", "label": "Yes - Verbally confirmed"},
                    {"code": "tentative", "label": "Tentative - May need to reschedule"},
                    {"code": "no_contact", "label": "Unable to reach patient"},
                ],
                "mobius_can_handle": False,
                "mobius_action": None,
            },
        ],
    },
    {
        "scenario_id": "attend_needs_reschedule",
        "scenario_name": "Reschedule Requested",
        "patient_name": "Christopher Taylor",
        "description": "Patient called to reschedule but hasn't confirmed new time",
        "batch_context": {
            "original_appointment": "Tomorrow",
            "reschedule_requested": True,
            "new_time_offered": True,
            "new_time_confirmed": False,
            "reason": "Work conflict",
        },
        "gap_types": ["attendance"],
        "status": "active",
        "probability_profile": {"overall": 0.68, "eligibility": 0.90, "coverage": 0.88, "attendance": 0.48, "errors": 0.94},
        # Batch recommendation
        "agentic_confidence": 0.80,
        "recommended_mode": "mobius",
        "recommendation_reason": "Can send scheduling link automatically",
        "agentic_actions": ["send_scheduling_link"],
        "steps": [
            {
                "question": "Patient requested reschedule - confirm new appointment time",
                "code": "confirm_reschedule",
                "factor": "attendance",
                "options": [
                    {"code": "confirmed_new", "label": "New time confirmed"},
                    {"code": "offer_times", "label": "Send available time slots"},
                    {"code": "call_schedule", "label": "Call to schedule"},
                    {"code": "patient_callback", "label": "Patient will call back"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Send scheduling link with available slots",
            },
        ],
    },
    
    # =========================================================================
    # AUTHORIZATION/COVERAGE SCENARIOS
    # =========================================================================
    {
        "scenario_id": "auth_required_not_started",
        "scenario_name": "Prior Auth Required",
        "patient_name": "Karen Lewis",
        "description": "Service requires prior auth, not yet submitted",
        "batch_context": {
            "service_type": "MRI - Lumbar Spine",
            "payer": "Cigna",
            "auth_required": True,
            "auth_submitted": False,
            "clinical_docs_ready": True,
            "appointment_date": "10 days from now",
        },
        "gap_types": ["coverage"],
        "status": "active",
        "probability_profile": {"overall": 0.55, "eligibility": 0.90, "coverage": 0.32, "attendance": 0.88, "errors": 0.92},
        # Batch recommendation
        "agentic_confidence": 0.85,
        "recommended_mode": "mobius",
        "recommendation_reason": "Clinical docs ready, can auto-submit to Cigna portal",
        "agentic_actions": ["submit_auth", "review_docs"],
        "steps": [
            {
                "question": "Prior authorization required for MRI - submit now?",
                "code": "submit_auth",
                "factor": "coverage",
                "options": [
                    {"code": "submit_now", "label": "Submit authorization request"},
                    {"code": "need_docs", "label": "Need additional documentation first"},
                    {"code": "check_alt", "label": "Check if auth can be avoided"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Auto-submit to Cigna portal with clinical docs",
            },
            {
                "question": "Clinical documentation sufficient for authorization?",
                "code": "check_docs",
                "factor": "coverage",
                "options": [
                    {"code": "sufficient", "label": "Yes - Documentation complete"},
                    {"code": "need_notes", "label": "Need additional clinical notes"},
                    {"code": "need_results", "label": "Need prior test results"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Review chart for required documentation",
            },
        ],
    },
    {
        "scenario_id": "auth_pending_review",
        "scenario_name": "Auth Pending Review",
        "patient_name": "Brian Walker",
        "description": "Authorization submitted 5 days ago, still pending",
        "batch_context": {
            "service_type": "Physical Therapy - 12 visits",
            "payer": "United Healthcare",
            "auth_submitted": True,
            "submission_date": "5 days ago",
            "status": "Pending clinical review",
            "typical_turnaround": "3-5 business days",
            "appointment_date": "7 days from now",
        },
        "gap_types": ["coverage"],
        "status": "active",
        "probability_profile": {"overall": 0.62, "eligibility": 0.92, "coverage": 0.45, "attendance": 0.90, "errors": 0.94},
        # Batch recommendation
        "agentic_confidence": 0.70,
        "recommended_mode": "mobius",
        "recommendation_reason": "Can check portal status automatically",
        "agentic_actions": ["check_portal_status"],
        "steps": [
            {
                "question": "Authorization pending for 5 days - follow up with payer?",
                "code": "followup_auth",
                "factor": "coverage",
                "options": [
                    {"code": "check_status", "label": "Check status on payer portal"},
                    {"code": "call_payer", "label": "Call payer for update"},
                    {"code": "wait", "label": "Wait - still within normal timeframe"},
                    {"code": "escalate", "label": "Escalate - appointment is soon"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Check UHC portal for current auth status",
            },
        ],
    },
    {
        "scenario_id": "auth_denied",
        "scenario_name": "Authorization Denied",
        "patient_name": "Susan Hall",
        "description": "Auth denied for insufficient documentation",
        "batch_context": {
            "service_type": "Knee Arthroscopy",
            "payer": "Anthem",
            "auth_status": "Denied",
            "denial_reason": "Insufficient documentation of conservative treatment",
            "appeal_deadline": "30 days from denial",
            "days_since_denial": 5,
        },
        "gap_types": ["coverage"],
        "status": "active",
        "probability_profile": {"overall": 0.45, "eligibility": 0.88, "coverage": 0.25, "attendance": 0.85, "errors": 0.90},
        # Batch recommendation
        "agentic_confidence": 0.45,
        "recommended_mode": "together",
        "recommendation_reason": "Denial requires clinical judgment for appeal strategy, can compile docs",
        "agentic_actions": ["compile_docs"],
        "steps": [
            {
                "question": "Authorization denied - insufficient documentation. Appeal?",
                "code": "denial_response",
                "factor": "coverage",
                "options": [
                    {"code": "appeal", "label": "Submit appeal with additional docs"},
                    {"code": "peer_to_peer", "label": "Request peer-to-peer review"},
                    {"code": "gather_docs", "label": "Gather more documentation first"},
                    {"code": "alternative", "label": "Explore alternative treatment"},
                ],
                "mobius_can_handle": False,
                "mobius_action": None,
            },
            {
                "question": "What additional documentation is needed for appeal?",
                "code": "appeal_docs",
                "factor": "coverage",
                "options": [
                    {"code": "pt_notes", "label": "Physical therapy notes showing failed conservative tx"},
                    {"code": "imaging", "label": "Updated imaging results"},
                    {"code": "letter", "label": "Letter of medical necessity"},
                    {"code": "all_above", "label": "All of the above"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Compile documentation package from chart",
            },
        ],
    },
    {
        "scenario_id": "auth_expiring",
        "scenario_name": "Auth Expiring Soon",
        "patient_name": "Richard Allen",
        "description": "Existing authorization expires in 5 days",
        "batch_context": {
            "service_type": "Chemotherapy - Cycle 4 of 6",
            "payer": "Medicare",
            "auth_status": "Approved",
            "auth_expiration": "5 days from now",
            "visits_remaining": 2,
            "renewal_needed": True,
        },
        "gap_types": ["coverage"],
        "status": "active",
        "probability_profile": {"overall": 0.70, "eligibility": 0.95, "coverage": 0.55, "attendance": 0.92, "errors": 0.94},
        # Batch recommendation
        "agentic_confidence": 0.82,
        "recommended_mode": "mobius",
        "recommendation_reason": "Renewal is straightforward, can submit to Medicare automatically",
        "agentic_actions": ["submit_renewal"],
        "steps": [
            {
                "question": "Authorization expires in 5 days - submit renewal?",
                "code": "auth_renewal",
                "factor": "coverage",
                "options": [
                    {"code": "submit_renewal", "label": "Submit renewal request now"},
                    {"code": "check_needed", "label": "Verify renewal is needed"},
                    {"code": "expedite", "label": "Request expedited review"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Submit renewal to Medicare with treatment notes",
            },
        ],
    },
    
    # =========================================================================
    # COMPLEX MULTI-FACTOR SCENARIOS
    # =========================================================================
    {
        "scenario_id": "complex_elig_attend",
        "scenario_name": "Eligibility + No-Show Risk",
        "patient_name": "Virginia Edwards",
        "description": "Insurance needs verification AND patient has no-show history",
        "batch_context": {
            "last_visit": "6 months ago",
            "insurance_verified": False,
            "no_show_count": 2,
            "risk_factors": ["Long gap since visit", "Previous no-shows", "Unverified insurance"],
        },
        "gap_types": ["eligibility", "attendance"],
        "status": "active",
        "probability_profile": {"overall": 0.42, "eligibility": 0.38, "coverage": 0.82, "attendance": 0.45, "errors": 0.90},
        # Batch recommendation
        "agentic_confidence": 0.52,
        "recommended_mode": "together",
        "recommendation_reason": "Multi-factor case, can verify insurance but attendance needs personal touch",
        "agentic_actions": ["run_eligibility_check", "send_confirmation"],
        "steps": [
            {
                "question": "Multiple issues: Insurance unverified + no-show history. Priority?",
                "code": "multi_triage",
                "factor": "eligibility",
                "options": [
                    {"code": "verify_first", "label": "Verify insurance first"},
                    {"code": "confirm_first", "label": "Confirm attendance first"},
                    {"code": "both_parallel", "label": "Address both simultaneously"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Run eligibility check while sending confirmation",
            },
            {
                "question": "Verify insurance is still active after 6-month gap?",
                "code": "verify_gap",
                "factor": "eligibility",
                "options": [
                    {"code": "active", "label": "Verified - Still active"},
                    {"code": "changed", "label": "Insurance has changed"},
                    {"code": "lapsed", "label": "Coverage has lapsed"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Run 270/271 eligibility verification",
            },
            {
                "question": "Patient has 2 previous no-shows - confirm attendance?",
                "code": "confirm_noshow_risk",
                "factor": "attendance",
                "options": [
                    {"code": "confirmed", "label": "Patient confirmed attendance"},
                    {"code": "call_needed", "label": "Need personal call to confirm"},
                    {"code": "no_response", "label": "No response to reminders"},
                ],
                "mobius_can_handle": False,
                "mobius_action": None,
            },
        ],
    },
    {
        "scenario_id": "complex_all_factors",
        "scenario_name": "Complex Case - Multiple Issues",
        "patient_name": "Janet Morris",
        "description": "New insurance, needs prior auth, transportation barrier",
        "batch_context": {
            "insurance_change": "New employer insurance as of last month",
            "service_requires_auth": True,
            "auth_status": "Not started",
            "transportation_barrier": True,
            "appointment_in": "14 days",
            "complexity_score": "High",
        },
        "gap_types": ["eligibility", "coverage", "attendance"],
        "status": "active",
        "probability_profile": {"overall": 0.32, "eligibility": 0.40, "coverage": 0.30, "attendance": 0.42, "errors": 0.88},
        # Batch recommendation
        "agentic_confidence": 0.38,
        "recommended_mode": "manual",
        "recommendation_reason": "Complex multi-factor case requires human coordination and judgment",
        "agentic_actions": ["verify_coverage"],
        "steps": [
            {
                "question": "Complex case with 3 issues - verify new insurance first",
                "code": "verify_new_insurance",
                "factor": "eligibility",
                "options": [
                    {"code": "verified", "label": "New insurance verified active"},
                    {"code": "need_card", "label": "Need new insurance card"},
                    {"code": "pending", "label": "Verification pending"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Verify new employer coverage",
            },
            {
                "question": "Prior authorization required - submit with new insurance?",
                "code": "auth_new_insurance",
                "factor": "coverage",
                "options": [
                    {"code": "submit", "label": "Submit auth request"},
                    {"code": "wait_verify", "label": "Wait for insurance verification first"},
                    {"code": "check_required", "label": "Verify auth is required by new payer"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Check new payer's auth requirements",
            },
            {
                "question": "Patient needs transportation assistance",
                "code": "arrange_transport_complex",
                "factor": "attendance",
                "options": [
                    {"code": "arrange", "label": "Arrange transportation"},
                    {"code": "telehealth", "label": "Offer telehealth alternative"},
                    {"code": "reschedule", "label": "Reschedule to accommodate"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Check transport eligibility with new insurance",
            },
        ],
    },
    
    # =========================================================================
    # RESOLVED SCENARIOS (GREEN - All Clear)
    # =========================================================================
    {
        "scenario_id": "resolved_verified",
        "scenario_name": "Eligibility Verified",
        "patient_name": "Kevin O'Brien",
        "description": "All eligibility checks passed",
        "batch_context": {
            "insurance_verified": True,
            "coverage_active": True,
            "benefits_confirmed": True,
        },
        "gap_types": ["eligibility"],
        "status": "resolved",
        "probability_profile": {"overall": 0.92, "eligibility": 0.95, "coverage": 0.90, "attendance": 0.88, "errors": 0.94},
        # No recommendation needed - already resolved
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [
            {
                "question": "Insurance eligibility verified - coverage active",
                "code": "verified_complete",
                "factor": "eligibility",
                "options": [
                    {"code": "confirmed", "label": "Confirmed"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Verification complete",
            },
        ],
    },
    {
        "scenario_id": "resolved_all_clear",
        "scenario_name": "All Clear",
        "patient_name": "Sarah Thompson",
        "description": "No issues detected - ready for visit",
        "batch_context": {
            "insurance_verified": True,
            "no_auth_required": True,
            "appointment_confirmed": True,
            "no_barriers": True,
        },
        "gap_types": [],
        "status": "resolved",
        "probability_profile": {"overall": 0.95, "eligibility": 0.96, "coverage": 0.94, "attendance": 0.92, "errors": 0.97},
        # No recommendation needed - already resolved
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [],
    },
    {
        "scenario_id": "resolved_auth_approved",
        "scenario_name": "Auth Approved",
        "patient_name": "Michael Brown",
        "description": "Prior authorization approved",
        "batch_context": {
            "auth_status": "Approved",
            "approval_date": "3 days ago",
            "valid_until": "90 days from now",
        },
        "gap_types": ["coverage"],
        "status": "resolved",
        "probability_profile": {"overall": 0.94, "eligibility": 0.92, "coverage": 0.96, "attendance": 0.90, "errors": 0.95},
        # No recommendation needed - already resolved
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [
            {
                "question": "Prior authorization approved",
                "code": "auth_approved",
                "factor": "coverage",
                "options": [
                    {"code": "confirmed", "label": "Confirmed"},
                ],
                "mobius_can_handle": True,
                "mobius_action": "Auth verified in system",
            },
        ],
    },
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_mrn(index: int) -> str:
    """Generate a demo MRN."""
    return f"DEMO-{10000 + index}"


def generate_dob(index: int) -> date:
    """Generate a demo DOB."""
    base_year = 1950 + (index % 50)
    month = (index % 12) + 1
    day = (index % 28) + 1
    return date(base_year, month, day)


def get_problem_statement(scenario: Dict) -> Optional[str]:
    """
    Generate problem_statement from scenario.
    This is what Mini displays and must match first PlanStep question.
    """
    if scenario["status"] == "resolved":
        return None
    
    if not scenario.get("steps"):
        return None
    
    # First step's question IS the problem statement
    return scenario["steps"][0]["question"]


def get_problem_details(scenario: Dict) -> Optional[List[Dict]]:
    """Generate problem_details from scenario."""
    if scenario["status"] == "resolved":
        return None
    
    gap_types = scenario.get("gap_types", [])
    if not gap_types:
        return None
    
    profile = scenario["probability_profile"]
    details = []
    
    for factor in gap_types:
        prob = profile.get(factor, 0.5)
        severity = "high" if prob < 0.5 else "medium" if prob < 0.7 else "low"
        
        details.append({
            "issue": factor,
            "probability": prob,
            "severity": severity,
            "description": scenario.get("description", ""),
        })
    
    return sorted(details, key=lambda x: x["probability"])


# =============================================================================
# SEED FUNCTIONS
# =============================================================================

def clear_demo_data(session):
    """Clear existing demo data."""
    print("\n1. Clearing existing demo data...")
    
    # Import models for cleanup
    from app.models.sidecar import UserOwnedTask, UserAlert, Milestone, MilestoneHistory, MilestoneSubstep
    from app.models.event_log import EventLog
    from app.models.response import SystemResponse, MiniSubmission
    
    # Clear event logs and responses first (FK to patient_context)
    session.query(EventLog).delete()
    session.query(MiniSubmission).delete()
    session.query(SystemResponse).delete()
    
    # Clear sidecar data (FK dependencies)
    session.query(UserOwnedTask).delete()
    session.query(UserAlert).delete()
    session.query(MilestoneHistory).delete()
    session.query(MilestoneSubstep).delete()
    session.query(Milestone).delete()
    
    # Clear resolution plan data
    session.query(StepAnswer).delete()
    session.query(PlanNote).delete()
    session.query(PlanStepFactLink).delete()  # Delete fact links before steps
    session.query(PlanStep).delete()
    session.query(ResolutionPlan).delete()
    
    # Clear evidence data
    session.query(FactSourceLink).delete()
    session.query(Evidence).delete()
    session.query(SourceDocument).delete()
    session.query(RawData).delete()
    
    # Clear probability/task data
    session.query(PaymentProbability).delete()
    session.query(TaskInstance).delete()
    
    # Clear patient data
    session.query(MockEmrRecord).delete()
    session.query(PatientId).delete()
    session.query(PatientSnapshot).delete()
    session.query(PatientContext).filter(
        PatientContext.tenant_id == DEFAULT_TENANT_ID
    ).delete()
    
    session.commit()
    print("   Cleared existing data.")


def seed_patients(session, tenant_id) -> List[Dict]:
    """Create patients with snapshots and IDs."""
    print("\n2. Creating patients...")
    
    created = []
    for i, scenario in enumerate(PATIENT_SCENARIOS):
        patient_key = f"demo_{i:03d}"
        display_name = f"Demo - {scenario['scenario_name']} - {scenario['patient_name']}"
        mrn = generate_mrn(i)
        dob = generate_dob(i)
        
        # PatientContext
        context = PatientContext(
            tenant_id=tenant_id,
            patient_key=patient_key,
        )
        session.add(context)
        session.flush()
        
        # PatientSnapshot
        snapshot = PatientSnapshot(
            patient_context_id=context.patient_context_id,
            display_name=display_name,
            id_label="MRN",
            id_masked=f"****{mrn[-4:]}",
            snapshot_version=1,
            dob=dob,
            verified=scenario["status"] == "resolved",
            needs_review=scenario["status"] == "active",
        )
        session.add(snapshot)
        
        # PatientId
        patient_id = PatientId(
            patient_context_id=context.patient_context_id,
            id_type="mrn",
            id_value=mrn,
            source_system="demo_emr",
        )
        session.add(patient_id)
        
        # MockEmrRecord
        emr = MockEmrRecord(
            patient_context_id=context.patient_context_id,
            allergies=["Penicillin"] if i % 3 != 0 else ["None reported"],
            medications=[{"name": "Lisinopril", "dose": "10mg", "frequency": "QD"}] if i % 2 == 0 else [],
            blood_type=["A+", "B+", "O+", "AB+", "A-", "B-", "O-", "AB-"][i % 8],
            vitals={
                "bp": f"{110 + (i % 30)}/{70 + (i % 20)}",
                "hr": 65 + (i % 25),
                "temp": 98.6,
                "weight_lbs": 140 + (i % 60),
            },
        )
        session.add(emr)
        
        created.append({
            "context": context,
            "scenario": scenario,
            "mrn": mrn,
            "patient_key": patient_key,
        })
    
    session.commit()
    print(f"   Created {len(created)} patients.")
    return created


def seed_payment_probabilities(session, patients):
    """Create PaymentProbability records."""
    print("\n3. Creating payment probabilities...")
    
    for patient_data in patients:
        context = patient_data["context"]
        scenario = patient_data["scenario"]
        profile = scenario["probability_profile"]
        
        # Get lowest factor
        gap_types = scenario.get("gap_types", [])
        lowest_factor = None
        lowest_reason = None
        
        if gap_types:
            lowest_factor = min(gap_types, key=lambda f: profile.get(f, 1.0))
            lowest_reason = scenario["scenario_name"]
        
        prob = PaymentProbability(
            patient_context_id=context.patient_context_id,
            target_date=date.today() + timedelta(days=random.randint(1, 14)),
            overall_probability=profile["overall"],
            confidence=random.uniform(0.78, 0.92),
            prob_eligibility=profile["eligibility"],
            prob_coverage=profile["coverage"],
            prob_appointment_attendance=profile["attendance"],
            prob_no_errors=profile["errors"],
            lowest_factor=lowest_factor,
            lowest_factor_reason=lowest_reason,
            problem_statement=get_problem_statement(scenario),
            problem_details=get_problem_details(scenario),
            batch_job_id="demo_seed_v2",
            # Batch recommendation fields
            agentic_confidence=scenario.get("agentic_confidence"),
            recommended_mode=scenario.get("recommended_mode"),
            recommendation_reason=scenario.get("recommendation_reason"),
            agentic_actions=scenario.get("agentic_actions"),
        )
        session.add(prob)
    
    session.commit()
    print(f"   Created {len(patients)} payment probabilities.")


def seed_resolution_plans(session, patients, tenant_id):
    """Create ResolutionPlans with PlanSteps."""
    print("\n4. Creating resolution plans...")
    
    plans_created = 0
    steps_created = 0
    
    for patient_data in patients:
        context = patient_data["context"]
        scenario = patient_data["scenario"]
        gap_types = scenario.get("gap_types", [])
        status = scenario["status"]
        steps_data = scenario.get("steps", [])
        
        # Create plan even for resolved (for history)
        plan = ResolutionPlan(
            patient_context_id=context.patient_context_id,
            tenant_id=tenant_id,
            gap_types=gap_types if gap_types else ["general"],
            status=PlanStatus.RESOLVED if status == "resolved" else PlanStatus.ACTIVE,
            initial_probability=scenario["probability_profile"]["overall"],
            current_probability=scenario["probability_profile"]["overall"],
            target_probability=0.85,
            batch_job_id="demo_seed_v2",
        )
        
        if status == "resolved":
            plan.resolved_at = datetime.utcnow() - timedelta(hours=random.randint(2, 48))
            plan.resolution_type = "verified_complete"
            plan.resolution_notes = f"All checks passed for {scenario['scenario_name']}"
        
        session.add(plan)
        session.flush()
        plans_created += 1
        
        # Create PlanSteps
        first_step_id = None
        
        for i, step_data in enumerate(steps_data):
            step_status = StepStatus.RESOLVED if status == "resolved" else (
                StepStatus.CURRENT if i == 0 else StepStatus.PENDING
            )
            
            # Build answer options
            answer_options = [
                {"code": opt["code"], "label": opt["label"]}
                for opt in step_data.get("options", [])
            ]
            
            # System suggestion
            system_suggestion = None
            if step_data.get("mobius_can_handle") and step_data.get("mobius_action"):
                system_suggestion = {
                    "source": step_data["mobius_action"],
                    "confidence": random.uniform(0.85, 0.95),
                }
            
            step = PlanStep(
                plan_id=plan.plan_id,
                step_order=i + 1,
                step_code=step_data["code"],
                step_type=StepType.QUESTION,
                input_type=InputType.SINGLE_CHOICE,
                question_text=step_data["question"],
                factor_type=step_data.get("factor", "general"),
                answer_options=answer_options,
                assignable_activities=[f"handle_{step_data.get('factor', 'general')}"],
                status=step_status,
                can_system_answer=step_data.get("mobius_can_handle", False),
                system_suggestion=system_suggestion,
                completed_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24)) if status == "resolved" else None,
                resolved_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24)) if status == "resolved" else None,
            )
            session.add(step)
            session.flush()
            steps_created += 1
            
            if i == 0:
                first_step_id = step.step_id
        
        if status == "active" and first_step_id:
            plan.current_step_id = first_step_id
    
    session.commit()
    print(f"   Created {plans_created} plans with {steps_created} steps.")


def print_summary(session):
    """Print summary and consistency check."""
    print("\n" + "=" * 70)
    print("SEED COMPLETE - DATA CONSISTENCY CHECK")
    print("=" * 70)
    
    # Get active patients
    active_plans = session.query(ResolutionPlan).filter(
        ResolutionPlan.status == PlanStatus.ACTIVE
    ).all()
    
    print(f"\nChecking {len(active_plans)} active patients for Mini/Sidecar consistency:\n")
    
    all_match = True
    for plan in active_plans[:10]:  # Check first 10
        prob = session.query(PaymentProbability).filter(
            PaymentProbability.patient_context_id == plan.patient_context_id
        ).first()
        
        first_step = session.query(PlanStep).filter(
            PlanStep.plan_id == plan.plan_id,
            PlanStep.step_order == 1
        ).first()
        
        snapshot = session.query(PatientSnapshot).filter(
            PatientSnapshot.patient_context_id == plan.patient_context_id
        ).first()
        
        mini_shows = prob.problem_statement if prob else "N/A"
        sidecar_shows = first_step.question_text if first_step else "N/A"
        matches = mini_shows == sidecar_shows
        
        if not matches:
            all_match = False
        
        status = "✓" if matches else "✗"
        print(f"  {status} {snapshot.display_name[:50] if snapshot else 'Unknown'}")
        if not matches:
            print(f"      Mini:    {mini_shows[:60]}")
            print(f"      Sidecar: {sidecar_shows[:60]}")
    
    print("\n" + "-" * 70)
    if all_match:
        print("✓ All patients have consistent Mini/Sidecar data!")
    else:
        print("✗ Some patients have mismatched data - check above")
    
    # Summary counts
    patient_count = session.query(PatientContext).filter(
        PatientContext.tenant_id == DEFAULT_TENANT_ID
    ).count()
    
    print(f"\nTotal patients: {patient_count}")
    print(f"Active plans: {len(active_plans)}")
    print(f"Resolved plans: {patient_count - len(active_plans)}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("MOBIUS OS - DEMO DATA SEED v2")
    print("=" * 70)
    print("\nCreating realistic batch-job-style data with proper relationships.")
    
    init_db()
    
    with get_db_session() as session:
        tenant = session.query(Tenant).filter(
            Tenant.tenant_id == DEFAULT_TENANT_ID
        ).first()
        
        if not tenant:
            tenant = Tenant(
                tenant_id=DEFAULT_TENANT_ID,
                name="Demo Clinic",
                domain="demo.clinic",
            )
            session.add(tenant)
            session.commit()
        
        clear_demo_data(session)
        patients = seed_patients(session, tenant.tenant_id)
        seed_payment_probabilities(session, patients)
        seed_resolution_plans(session, patients, tenant.tenant_id)
        print_summary(session)
    
    print("\n✅ Demo seed v2 complete!\n")


if __name__ == "__main__":
    main()
