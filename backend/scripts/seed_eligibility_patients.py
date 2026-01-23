#!/usr/bin/env python3
"""
Seed 3 patients with COMPLETED Attendance and IN-PROGRESS Eligibility.

Patient Archetypes:
1. Angela Morris - Mobius success (attendance), simple eligibility (active commercial PPO)
2. Carlos Ramirez - Mobius success (attendance), complex eligibility (expired Medicaid, reinstatement)
3. Denise Walker - Joint success (attendance), escalated eligibility (no coverage, multiple paths)

Attendance Factor: All steps COMPLETED
Eligibility Factor: Options surfaced, decision pending (CURRENT/PENDING)
"""

import sys
import os
import uuid
from datetime import datetime, date, timedelta

os.environ['FLASK_DEBUG'] = '0'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Monkey-patch to disable SQL logging
import app.db.postgres as pg
def silent_get_engine():
    if pg._engine is None:
        from sqlalchemy import create_engine
        from app.config import config
        db_url = config.get_database_url().replace("postgresql://", "postgresql+psycopg://")
        pg._engine = create_engine(db_url, echo=False, pool_pre_ping=True)
    return pg._engine
pg.get_engine = silent_get_engine

from app.db.postgres import get_db_session, init_db
from app.models import PatientContext, PatientSnapshot, Tenant
from app.models.probability import PaymentProbability
from app.models.resolution import (
    ResolutionPlan, PlanStep, StepAnswer,
    PlanStatus, StepStatus, StepType, InputType, FactorType, AnswerMode
)
from app.models.patient_ids import PatientId
from app.models.mock_emr import MockEmrRecord
from app.models.sidecar import Milestone, MilestoneSubstep, MilestoneHistory, UserAlert, UserOwnedTask
from app.models.response import MiniSubmission, SystemResponse
from app.models.event_log import EventLog
from app.models.evidence import PlanStepFactLink, Evidence, SourceDocument, RawData, FactSourceLink


# =============================================================================
# ATTENDANCE L3 STEPS (Factor 1 - COMPLETED for all patients)
# =============================================================================

ATTENDANCE_L3_STEPS = [
    {
        "step_order": 1,
        "step_code": "understanding_visit",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Understanding the Patient's Visit",
        "description": "Determine planning intensity and lead time required for the visit.",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": True,
        "assignable_activities": ["schedule_appointments", "patient_outreach"],
        "answer_options": [
            {"code": "new_visit", "label": "New Visit"},
            {"code": "standard_visit", "label": "Standard Visit"},
            {"code": "high_risk_visit", "label": "High-Risk Visit"},
        ],
    },
    {
        "step_order": 2,
        "step_code": "staying_on_track",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Helping the Patient Stay on Track",
        "description": "Select the appropriate outreach strategy based on responsiveness, preferences, and risk.",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": True,
        "assignable_activities": ["patient_outreach", "schedule_appointments"],
        "answer_options": [
            {"code": "standard_outreach", "label": "Standard Outreach (automated)"},
            {"code": "tailored_outreach", "label": "Tailored Outreach (automated)"},
            {"code": "personalized_outreach", "label": "Personalized Outreach (care team call)"},
            {"code": "reestablish_contact", "label": "Re-establish Contact (shared workflow)"},
        ],
    },
    {
        "step_order": 3,
        "step_code": "clinical_readiness",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Assessing Clinical Readiness",
        "description": "Ensure the planned visit is still appropriate from a safety and stability perspective.",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": True,
        "assignable_activities": ["patient_outreach"],
        "answer_options": [
            {"code": "clinically_stable", "label": "Clinically Stable — Proceed as Planned"},
            {"code": "possible_decompensation", "label": "Possible Decompensation — Care Team Review"},
            {"code": "acute_concern", "label": "Acute Concern — Immediate Escalation"},
            {"code": "insufficient_info", "label": "Insufficient Information — Monitor Closely"},
        ],
    },
    {
        "step_order": 4,
        "step_code": "reducing_risks",
        "step_type": StepType.QUESTION,
        "input_type": InputType.MULTI_CHOICE,
        "question_text": "Reducing Attendance Risks",
        "description": "Identify non-clinical barriers that could prevent attendance.",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": True,
        "assignable_activities": ["patient_outreach", "schedule_appointments"],
        "answer_options": [
            {"code": "no_barriers", "label": "No Material Barriers"},
            {"code": "transportation", "label": "Transportation Barriers"},
            {"code": "social_environmental", "label": "Social & Environmental Barriers"},
            {"code": "medical_emergency", "label": "Medical or Mental Health Emergency"},
            {"code": "scheduling_conflict", "label": "Scheduling Conflicts"},
            {"code": "administrative", "label": "Administrative Barriers"},
            {"code": "readiness_anxiety", "label": "Readiness or Anxiety-Related"},
            {"code": "communication", "label": "Communication Barriers"},
        ],
    },
    {
        "step_order": 5,
        "step_code": "backup_plan",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Creating a Backup Plan",
        "description": "Manage capacity responsibly based on anticipated likelihood of attendance.",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": True,
        "assignable_activities": ["schedule_appointments"],
        "answer_options": [
            {"code": "proceed_scheduled", "label": "Proceed as Scheduled"},
            {"code": "increased_confirmation", "label": "Increased Confirmation Required"},
            {"code": "double_booking", "label": "Double-Booking Approved"},
            {"code": "flexible_slot", "label": "Flexible Slot Management"},
            {"code": "advance_reschedule", "label": "Advance Reschedule Recommended"},
            {"code": "modality_shift", "label": "Modality Shift Planned"},
            {"code": "visit_released", "label": "Visit Released"},
        ],
    },
]


# =============================================================================
# ELIGIBILITY L3 STEPS (Factor 2 - IN PROGRESS for all patients)
# =============================================================================

ELIGIBILITY_L3_STEPS = [
    {
        "step_order": 1,
        "step_code": "coverage_discovery",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Coverage Discovery",
        "description": "What coverage sources were identified for this patient?",
        "factor_type": FactorType.ELIGIBILITY,
        "can_system_answer": True,
        "assignable_activities": ["verify_eligibility"],
        "answer_options": [
            {"code": "commercial_ppo", "label": "Commercial PPO"},
            {"code": "commercial_hmo", "label": "Commercial HMO"},
            {"code": "managed_medicaid", "label": "Managed Medicaid"},
            {"code": "traditional_medicaid", "label": "Traditional Medicaid"},
            {"code": "medicare", "label": "Medicare"},
            {"code": "dual_eligible", "label": "Dual Eligible (Medicare + Medicaid)"},
            {"code": "no_coverage", "label": "No Coverage Discovered"},
        ],
    },
    {
        "step_order": 2,
        "step_code": "coverage_status",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Coverage Status",
        "description": "What is the current status of the identified coverage?",
        "factor_type": FactorType.ELIGIBILITY,
        "can_system_answer": True,
        "assignable_activities": ["verify_eligibility"],
        "answer_options": [
            {"code": "active_stable", "label": "Active — Stable"},
            {"code": "active_at_risk", "label": "Active — At Risk (churn risk)"},
            {"code": "expired_reinstatable", "label": "Expired — Reinstatable"},
            {"code": "expired_not_reinstatable", "label": "Expired — Not Reinstatable"},
            {"code": "pending_enrollment", "label": "Pending Enrollment"},
            {"code": "not_active", "label": "Not Active"},
        ],
    },
    {
        "step_order": 3,
        "step_code": "coverage_path_selection",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Select Coverage Path",
        "description": "Choose the best path to secure coverage for this patient.",
        "factor_type": FactorType.ELIGIBILITY,
        "can_system_answer": False,  # User must decide
        "assignable_activities": ["verify_eligibility", "check_in_patients"],
        "answer_options": [
            {"code": "use_primary_insurance", "label": "Use Primary Insurance"},
            {"code": "reinstate_coverage", "label": "Reinstate Existing Coverage"},
            {"code": "enroll_medicaid", "label": "Explore Public Insurance (Medicaid)"},
            {"code": "enroll_marketplace", "label": "Explore Marketplace Insurance"},
            {"code": "state_local_program", "label": "State or Local Program Funding"},
            {"code": "charity_care", "label": "Charity Care / Financial Assistance"},
            {"code": "emergency_path", "label": "Emergency / Mandated Care Path"},
            {"code": "self_pay", "label": "Self-Pay Path"},
        ],
    },
    {
        "step_order": 4,
        "step_code": "coverage_escalation",
        "step_type": StepType.ACTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Escalation & Case Documentation",
        "description": "Document findings and determine escalation path.",
        "factor_type": FactorType.ELIGIBILITY,
        "can_system_answer": False,  # User decision required
        "assignable_activities": ["verify_eligibility", "patient_outreach"],
        "answer_options": [
            {"code": "no_escalation", "label": "No escalation needed — proceed with selected path"},
            {"code": "develop_case_escalate", "label": "Develop case file and escalate"},
            {"code": "escalate_clinical", "label": "Escalate to clinical leadership"},
            {"code": "escalate_admin", "label": "Escalate to administrative leadership"},
            {"code": "schedule_care_conference", "label": "Schedule care conference"},
        ],
    },
]


# =============================================================================
# L4 EVIDENCE LIBRARY
# =============================================================================

L4_EVIDENCE = {
    # =========================================================================
    # ATTENDANCE EVIDENCE (for completed attendance steps)
    # =========================================================================
    
    # Standard Visit Evidence
    "prior_completed_visits": {
        "fact_type": "visit_history",
        "fact_summary": "Prior completed visits of same type",
        "fact_data": {"visit_count": 12, "same_type_count": 8},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "stable_attendance_history": {
        "fact_type": "attendance_history",
        "fact_summary": "Stable attendance history with consistent pattern",
        "fact_data": {"attendance_rate": 0.95, "pattern": "consistent"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "no_recent_noshow": {
        "fact_type": "attendance_history",
        "fact_summary": "No recent no-shows or late cancellations",
        "fact_data": {"noshow_count_6mo": 0, "late_cancel_count_6mo": 0},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "valid_contact_info": {
        "fact_type": "contact",
        "fact_summary": "Valid contact information on file",
        "fact_data": {"phone_valid": True, "email_valid": True, "address_valid": True},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "prior_responsiveness": {
        "fact_type": "outreach_history",
        "fact_summary": "Prior responsiveness to automated reminders",
        "fact_data": {"response_rate": 0.90, "preferred_channel": "sms"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "no_crisis_indicators": {
        "fact_type": "clinical",
        "fact_summary": "No recent crisis indicators",
        "fact_data": {"crisis_flags": [], "last_assessment": "2026-01-01"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "no_barriers_identified": {
        "fact_type": "logistics",
        "fact_summary": "No unresolved barriers on record",
        "fact_data": {"barriers": [], "last_check": "2026-01-20"},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "high_attendance_likelihood": {
        "fact_type": "prediction",
        "fact_summary": "Attendance likelihood high",
        "fact_data": {"predicted_attendance": 0.92, "confidence": 0.85},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    
    # New Visit Evidence
    "no_prior_visits": {
        "fact_type": "visit_history",
        "fact_summary": "No prior completed visits for this service or clinic",
        "fact_data": {"visit_count": 0, "is_new_patient": True},
        "impact_direction": "neutral",
        "impact_weight": 0.3,
    },
    "stated_preferences": {
        "fact_type": "preferences",
        "fact_summary": "Patient-stated communication preferences",
        "fact_data": {"preferred_channel": "sms", "preferred_time": "after_5pm", "cadence": "2_days_before"},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "scheduling_conflict_identified": {
        "fact_type": "scheduling",
        "fact_summary": "Variable work schedule creates conflicts",
        "fact_data": {"work_type": "shift_work", "schedule": "variable"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "moderate_attendance_risk": {
        "fact_type": "prediction",
        "fact_summary": "Moderate attendance risk identified",
        "fact_data": {"predicted_attendance": 0.65, "risk_level": "moderate"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    
    # High-Risk Visit Evidence
    "recent_noshow_history": {
        "fact_type": "attendance_history",
        "fact_summary": "Recent no-show or late cancellation history",
        "fact_data": {"noshow_count_6mo": 3, "late_cancel_count_6mo": 2},
        "impact_direction": "negative",
        "impact_weight": 0.6,
    },
    "clinical_vulnerability": {
        "fact_type": "clinical",
        "fact_summary": "Clinical vulnerability noted",
        "fact_data": {"vulnerability_type": "mental_health", "notes": "Requires relationship-based outreach"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "transportation_barrier": {
        "fact_type": "logistics",
        "fact_summary": "No reliable transportation available",
        "fact_data": {"has_transport": False, "barrier_type": "transportation"},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "anxiety_barrier": {
        "fact_type": "behavioral",
        "fact_summary": "Expressed hesitation or avoidance",
        "fact_data": {"hesitation_type": "anxiety", "noted_date": "2026-01-12"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "telehealth_acceptable": {
        "fact_type": "clinical",
        "fact_summary": "Telehealth clinically acceptable",
        "fact_data": {"telehealth_appropriate": True, "clinical_approval": True},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    
    # =========================================================================
    # ELIGIBILITY EVIDENCE (for in-progress eligibility steps)
    # =========================================================================
    
    # Commercial PPO - Active
    "commercial_ppo_discovered": {
        "fact_type": "coverage_discovery",
        "fact_summary": "Commercial PPO coverage discovered from EMR",
        "fact_data": {"payer": "BlueCross BlueShield", "plan_type": "PPO", "source": "emr"},
        "impact_direction": "positive",
        "impact_weight": 0.6,
    },
    "coverage_active_stable": {
        "fact_type": "eligibility_status",
        "fact_summary": "Coverage is active and stable",
        "fact_data": {"status": "active", "last_verified": "2026-01-20", "risk_level": "low"},
        "impact_direction": "positive",
        "impact_weight": 0.7,
    },
    "primary_insurance_path": {
        "fact_type": "coverage_path",
        "fact_summary": "Primary insurance path available - straightforward",
        "fact_data": {"path": "use_primary", "complexity": "low", "action_required": "confirm"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    
    # Managed Medicaid - Expired/Reinstatable
    "medicaid_discovered": {
        "fact_type": "coverage_discovery",
        "fact_summary": "Managed Medicaid coverage discovered via external check",
        "fact_data": {"payer": "Molina Healthcare", "plan_type": "Managed Medicaid", "source": "external_270"},
        "impact_direction": "neutral",
        "impact_weight": 0.4,
    },
    "coverage_expired_reinstatable": {
        "fact_type": "eligibility_status",
        "fact_summary": "Coverage expired but reinstatable within 90 days",
        "fact_data": {"status": "expired", "expiry_date": "2025-12-15", "reinstatement_window": "90_days", "risk": "high_churn"},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "reinstatement_path": {
        "fact_type": "coverage_path",
        "fact_summary": "Reinstatement pathway available - requires action",
        "fact_data": {"path": "reinstate", "steps": ["contact_medicaid", "submit_renewal", "verify"], "timeline": "2-4 weeks"},
        "impact_direction": "neutral",
        "impact_weight": 0.4,
    },
    "medicaid_enrollment_path": {
        "fact_type": "coverage_path",
        "fact_summary": "Medicaid re-enrollment pathway as backup",
        "fact_data": {"path": "new_enrollment", "eligibility_likely": True, "timeline": "4-6 weeks"},
        "impact_direction": "neutral",
        "impact_weight": 0.3,
    },
    
    # No Coverage - Multiple Paths
    "no_coverage_discovered": {
        "fact_type": "coverage_discovery",
        "fact_summary": "No active coverage discovered after exhaustive search",
        "fact_data": {"sources_checked": ["emr", "270_api", "patient_interview"], "coverage_found": False},
        "impact_direction": "negative",
        "impact_weight": 0.7,
    },
    "coverage_not_active": {
        "fact_type": "eligibility_status",
        "fact_summary": "No active coverage - patient uninsured",
        "fact_data": {"status": "not_active", "last_coverage": "2025-06-01", "reason": "job_loss"},
        "impact_direction": "negative",
        "impact_weight": 0.6,
    },
    "medicaid_eligibility_likely": {
        "fact_type": "coverage_path",
        "fact_summary": "Patient likely eligible for Medicaid based on income",
        "fact_data": {"path": "medicaid_enrollment", "income_eligible": True, "disability_eligible": "possible"},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "state_program_path": {
        "fact_type": "coverage_path",
        "fact_summary": "State/local program funding may be available",
        "fact_data": {"path": "state_program", "programs": ["county_behavioral_health", "state_crisis_fund"]},
        "impact_direction": "neutral",
        "impact_weight": 0.3,
    },
    "emergency_path_available": {
        "fact_type": "coverage_path",
        "fact_summary": "Emergency/mandated care path if condition worsens",
        "fact_data": {"path": "emergency", "trigger": "clinical_decompensation", "coverage": "emtala"},
        "impact_direction": "neutral",
        "impact_weight": 0.2,
    },
    "escalation_required": {
        "fact_type": "workflow",
        "fact_summary": "Escalation to clinical and administrative leadership required",
        "fact_data": {"escalation_reason": "complex_coverage_case", "flagged_to": ["clinical_lead", "admin_lead"]},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
}


# =============================================================================
# PATIENT PROFILES
# =============================================================================

PATIENT_PROFILES = {
    # =========================================================================
    # GROUP 1: ATTENDANCE IN PROGRESS (3 patients)
    # =========================================================================
    "maria": {
        "name": "Maria Gonzalez",
        "mrn_suffix": "MARIA01",
        "profile": "Established, stable, predictable",
        "theme": "Fully automatable (all Mobius)",
        "group": "attendance_in_progress",
        "probability": {
            "overall": 0.92,
            "attendance": 0.95,
            "eligibility": 0.90,
            "coverage": 0.92,
            "errors": 0.94,
            "agentic_confidence": 0.95,
            "recommended_mode": "mobius",
            "recommendation_reason": "Stable patient with consistent history. All steps can be automated.",
        },
        "attendance_steps": [
            {"code": "understanding_visit", "answer": "standard_visit", "assignee": "mobius", "status": "current"},
            {"code": "staying_on_track", "answer": "standard_outreach", "assignee": "mobius", "status": "pending"},
            {"code": "clinical_readiness", "answer": "clinically_stable", "assignee": "mobius", "status": "pending"},
            {"code": "reducing_risks", "answer": "no_barriers", "assignee": "mobius", "status": "pending"},
            {"code": "backup_plan", "answer": "proceed_scheduled", "assignee": "mobius", "status": "pending"},
        ],
        "eligibility_steps": [],  # No eligibility steps yet
        "attendance_evidence": {
            "understanding_visit": ["prior_completed_visits", "stable_attendance_history", "no_recent_noshow"],
            "staying_on_track": ["valid_contact_info", "prior_responsiveness"],
            "clinical_readiness": ["no_crisis_indicators"],
            "reducing_risks": ["no_barriers_identified"],
            "backup_plan": ["high_attendance_likelihood"],
        },
        "eligibility_evidence": {},
    },
    "james": {
        "name": "James Walker",
        "mrn_suffix": "JAMES01",
        "profile": "New, complex, but reachable",
        "theme": "Automation with review (Mobius + User)",
        "group": "attendance_in_progress",
        "probability": {
            "overall": 0.72,
            "attendance": 0.68,
            "eligibility": 0.85,
            "coverage": 0.80,
            "errors": 0.88,
            "agentic_confidence": 0.72,
            "recommended_mode": "together",
            "recommendation_reason": "New patient with some complexity. Recommend collaborative review for clinical steps.",
        },
        "attendance_steps": [
            {"code": "understanding_visit", "answer": "new_visit", "assignee": "mobius", "status": "current"},
            {"code": "staying_on_track", "answer": "tailored_outreach", "assignee": "mobius", "status": "pending"},
            {"code": "clinical_readiness", "answer": "possible_decompensation", "assignee": "user", "status": "pending"},
            {"code": "reducing_risks", "answer": "scheduling_conflict", "assignee": "user", "status": "pending"},
            {"code": "backup_plan", "answer": "increased_confirmation", "assignee": "mobius", "status": "pending"},
        ],
        "eligibility_steps": [],  # No eligibility steps yet
        "attendance_evidence": {
            "understanding_visit": ["no_prior_visits"],
            "staying_on_track": ["stated_preferences", "valid_contact_info"],
            "clinical_readiness": ["no_crisis_indicators"],
            "reducing_risks": ["scheduling_conflict_identified"],
            "backup_plan": ["moderate_attendance_risk"],
        },
        "eligibility_evidence": {},
    },
    "tanya": {
        "name": "Tanya Brooks",
        "mrn_suffix": "TANYA01",
        "profile": "High-risk, disengaging, safety-sensitive",
        "theme": "Human-led, system-supported (all User)",
        "group": "attendance_in_progress",
        "probability": {
            "overall": 0.45,
            "attendance": 0.35,
            "eligibility": 0.88,
            "coverage": 0.85,
            "errors": 0.90,
            "agentic_confidence": 0.35,
            "recommended_mode": "manual",
            "recommendation_reason": "High-risk patient requiring human judgment. Clinical vulnerability and disengagement patterns detected.",
        },
        "attendance_steps": [
            {"code": "understanding_visit", "answer": "high_risk_visit", "assignee": "user", "status": "current"},
            {"code": "staying_on_track", "answer": "personalized_outreach", "assignee": "user", "status": "pending"},
            {"code": "clinical_readiness", "answer": "possible_decompensation", "assignee": "user", "status": "pending"},
            {"code": "reducing_risks", "answer": ["transportation", "readiness_anxiety"], "assignee": "user", "status": "pending"},
            {"code": "backup_plan", "answer": "modality_shift", "assignee": "user", "status": "pending"},
        ],
        "eligibility_steps": [],  # No eligibility steps yet
        "attendance_evidence": {
            "understanding_visit": ["recent_noshow_history", "clinical_vulnerability"],
            "staying_on_track": ["valid_contact_info"],
            "clinical_readiness": ["clinical_vulnerability"],
            "reducing_risks": ["transportation_barrier", "anxiety_barrier"],
            "backup_plan": ["telehealth_acceptable"],
        },
        "eligibility_evidence": {},
    },
    
    # =========================================================================
    # GROUP 2: ATTENDANCE COMPLETED, ELIGIBILITY IN PROGRESS (3 patients)
    # =========================================================================
    "angela": {
        "name": "Angela Morris",
        "mrn_suffix": "ANGELA01",
        "profile": "Established patient, simple eligibility",
        "theme": "Mobius success → Simple eligibility decision",
        "group": "eligibility_in_progress",
        "probability": {
            "overall": 0.85,
            "attendance": 0.95,  # High - visit readiness complete
            "eligibility": 0.75,  # Medium - needs path confirmation
            "coverage": 0.88,
            "errors": 0.92,
            "agentic_confidence": 0.92,
            "recommended_mode": "mobius",
            "recommendation_reason": "Active commercial PPO confirmed. Straightforward path - recommend automated execution.",
        },
        "attendance_steps": [
            {"code": "understanding_visit", "answer": "standard_visit", "assignee": "mobius", "status": "answered"},
            {"code": "staying_on_track", "answer": "standard_outreach", "assignee": "mobius", "status": "answered"},
            {"code": "clinical_readiness", "answer": "clinically_stable", "assignee": "mobius", "status": "answered"},
            {"code": "reducing_risks", "answer": "no_barriers", "assignee": "mobius", "status": "answered"},
            {"code": "backup_plan", "answer": "proceed_scheduled", "assignee": "mobius", "status": "answered"},
        ],
        "eligibility_steps": [
            {"code": "coverage_discovery", "answer": "commercial_ppo", "assignee": "mobius", "status": "answered"},
            {"code": "coverage_status", "answer": "active_stable", "assignee": "mobius", "status": "answered"},
            {"code": "coverage_path_selection", "answer": None, "assignee": "user", "status": "current"},
            {"code": "coverage_escalation", "answer": None, "assignee": "user", "status": "pending"},
        ],
        "attendance_evidence": {
            "understanding_visit": ["prior_completed_visits", "stable_attendance_history"],
            "staying_on_track": ["valid_contact_info", "prior_responsiveness"],
            "clinical_readiness": ["no_crisis_indicators"],
            "reducing_risks": ["no_barriers_identified"],
            "backup_plan": ["high_attendance_likelihood"],
        },
        "eligibility_evidence": {
            "coverage_discovery": ["commercial_ppo_discovered"],
            "coverage_status": ["coverage_active_stable"],
            "coverage_path_selection": ["primary_insurance_path"],
        },
    },
    "carlos": {
        "name": "Carlos Ramirez",
        "mrn_suffix": "CARLOS01",
        "profile": "New patient, complex eligibility (reinstatement needed)",
        "theme": "Mobius success → Parallel eligibility paths",
        "group": "eligibility_in_progress",
        "probability": {
            "overall": 0.62,
            "attendance": 0.88,  # Good - visit readiness complete
            "eligibility": 0.45,  # Low - expired coverage, needs action
            "coverage": 0.70,
            "errors": 0.85,
            "agentic_confidence": 0.65,
            "recommended_mode": "together",
            "recommendation_reason": "Medicaid reinstatement possible but requires coordination. Parallel paths available - recommend collaborative approach.",
        },
        "attendance_steps": [
            {"code": "understanding_visit", "answer": "new_visit", "assignee": "mobius", "status": "answered"},
            {"code": "staying_on_track", "answer": "tailored_outreach", "assignee": "mobius", "status": "answered"},
            {"code": "clinical_readiness", "answer": "clinically_stable", "assignee": "mobius", "status": "answered"},
            {"code": "reducing_risks", "answer": "scheduling_conflict", "assignee": "mobius", "status": "answered"},
            {"code": "backup_plan", "answer": "increased_confirmation", "assignee": "mobius", "status": "answered"},
        ],
        "eligibility_steps": [
            {"code": "coverage_discovery", "answer": "managed_medicaid", "assignee": "mobius", "status": "answered"},
            {"code": "coverage_status", "answer": "expired_reinstatable", "assignee": "mobius", "status": "answered"},
            {"code": "coverage_path_selection", "answer": None, "assignee": "user", "status": "current"},
            {"code": "coverage_escalation", "answer": None, "assignee": "user", "status": "pending"},
        ],
        "attendance_evidence": {
            "understanding_visit": ["no_prior_visits"],
            "staying_on_track": ["stated_preferences", "valid_contact_info"],
            "clinical_readiness": ["no_crisis_indicators"],
            "reducing_risks": ["scheduling_conflict_identified"],
            "backup_plan": ["moderate_attendance_risk"],
        },
        "eligibility_evidence": {
            "coverage_discovery": ["medicaid_discovered"],
            "coverage_status": ["coverage_expired_reinstatable"],
            "coverage_path_selection": ["reinstatement_path", "medicaid_enrollment_path"],
        },
    },
    "denise": {
        "name": "Denise Walker",
        "mrn_suffix": "DENISE01",
        "profile": "High-risk patient, no coverage (escalation required)",
        "theme": "Joint success → Escalated eligibility",
        "group": "eligibility_in_progress",
        "probability": {
            "overall": 0.38,
            "attendance": 0.72,  # Moderate - joint completion
            "eligibility": 0.20,  # Very low - no coverage
            "coverage": 0.30,
            "errors": 0.80,
            "agentic_confidence": 0.25,
            "recommended_mode": "manual",
            "recommendation_reason": "No coverage found. Complex case requiring leadership escalation and multi-path evaluation.",
        },
        "attendance_steps": [
            {"code": "understanding_visit", "answer": "high_risk_visit", "assignee": "user", "status": "answered"},
            {"code": "staying_on_track", "answer": "personalized_outreach", "assignee": "user", "status": "answered"},
            {"code": "clinical_readiness", "answer": "possible_decompensation", "assignee": "user", "status": "answered"},
            {"code": "reducing_risks", "answer": ["transportation", "readiness_anxiety"], "assignee": "user", "status": "answered"},
            {"code": "backup_plan", "answer": "modality_shift", "assignee": "user", "status": "answered"},
        ],
        "eligibility_steps": [
            {"code": "coverage_discovery", "answer": "no_coverage", "assignee": "mobius", "status": "answered"},
            {"code": "coverage_status", "answer": "not_active", "assignee": "mobius", "status": "answered"},
            {"code": "coverage_path_selection", "answer": None, "assignee": "user", "status": "current"},
            {"code": "coverage_escalation", "answer": None, "assignee": "user", "status": "pending"},
        ],
        "attendance_evidence": {
            "understanding_visit": ["recent_noshow_history", "clinical_vulnerability"],
            "staying_on_track": ["valid_contact_info"],
            "clinical_readiness": ["clinical_vulnerability"],
            "reducing_risks": ["transportation_barrier", "anxiety_barrier"],
            "backup_plan": ["telehealth_acceptable"],
        },
        "eligibility_evidence": {
            "coverage_discovery": ["no_coverage_discovered"],
            "coverage_status": ["coverage_not_active"],
            "coverage_path_selection": ["medicaid_eligibility_likely", "state_program_path", "emergency_path_available", "escalation_required"],
        },
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def cleanup_all_patients(db, tenant_id):
    """Delete all existing patient data to start fresh."""
    print("\n--- Cleaning up existing data ---")
    
    # Clear event logs and responses first (FK to patient_context)
    db.query(EventLog).delete()
    db.query(MiniSubmission).delete()
    db.query(SystemResponse).delete()
    
    # Clear sidecar data (FK dependencies)
    db.query(UserOwnedTask).delete()
    db.query(UserAlert).delete()
    db.query(MilestoneHistory).delete()
    db.query(MilestoneSubstep).delete()
    db.query(Milestone).delete()
    
    # Clear resolution plan data
    from app.models.resolution import StepAnswer, PlanNote, UserRemedy
    db.query(UserRemedy).delete()
    db.query(StepAnswer).delete()
    db.query(PlanNote).delete()
    db.query(PlanStepFactLink).delete()
    db.query(PlanStep).delete()
    db.query(ResolutionPlan).delete()
    
    # Clear evidence data
    db.query(FactSourceLink).delete()
    db.query(Evidence).delete()
    db.query(SourceDocument).delete()
    db.query(RawData).delete()
    
    # Clear probability/task data
    from app.models.probability import TaskInstance
    db.query(PaymentProbability).delete()
    db.query(TaskInstance).delete()
    
    # Clear patient data
    db.query(MockEmrRecord).delete()
    db.query(PatientId).delete()
    db.query(PatientSnapshot).delete()
    db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).delete()
    
    db.flush()
    print("  ✓ All existing patient data deleted")


def create_patient(db, tenant_id, profile_key):
    """Create a patient with attendance and/or eligibility steps based on profile group."""
    profile = PATIENT_PROFILES[profile_key]
    group = profile.get("group", "eligibility_in_progress")
    
    print(f"\n--- Creating Patient: {profile['name']} ---")
    print(f"    Profile: {profile['profile']}")
    print(f"    Theme: {profile['theme']}")
    
    # Create patient context
    patient = PatientContext(
        tenant_id=tenant_id,
        patient_key=f"demo_{profile_key}_{uuid.uuid4().hex[:6]}",
    )
    db.add(patient)
    db.flush()
    
    # Create patient snapshot
    snapshot = PatientSnapshot(
        patient_context_id=patient.patient_context_id,
        display_name=profile["name"],
        id_label="MRN",
        id_masked=f"****{profile['mrn_suffix']}",
        verified=True,
        data_complete=True,
    )
    db.add(snapshot)
    
    # Create patient ID
    patient_id = PatientId(
        patient_context_id=patient.patient_context_id,
        id_type="mrn",
        id_value=f"MRN-{profile['mrn_suffix']}",
        is_primary=True,
    )
    db.add(patient_id)
    db.flush()
    
    # Determine lowest factor based on group
    if group == "attendance_in_progress":
        lowest_factor = "attendance"
        problem_statement = f"Preparing {profile['name'].split()[0]} for their visit"
        gap_types = ["attendance"]
    else:
        lowest_factor = "eligibility"
        problem_statement = f"Securing coverage for {profile['name'].split()[0]}"
        gap_types = ["attendance", "eligibility"]
    
    # Create payment probability (Layer 1)
    prob_data = profile["probability"]
    prob = PaymentProbability(
        patient_context_id=patient.patient_context_id,
        target_date=date.today() + timedelta(days=7),
        overall_probability=prob_data["overall"],
        confidence=0.85,
        prob_appointment_attendance=prob_data["attendance"],
        prob_eligibility=prob_data["eligibility"],
        prob_coverage=prob_data["coverage"],
        prob_no_errors=prob_data["errors"],
        lowest_factor=lowest_factor,
        lowest_factor_reason=f"{profile['theme']}",
        problem_statement=problem_statement,
        # Mobius readiness fields
        agentic_confidence=prob_data.get("agentic_confidence", 0.5),
        recommended_mode=prob_data.get("recommended_mode", "together"),
        recommendation_reason=prob_data.get("recommendation_reason", ""),
        batch_job_id="seed_demo_patients",
    )
    db.add(prob)
    db.flush()
    
    mode_icon = "🤖" if prob_data.get("recommended_mode") == "mobius" else ("🤝" if prob_data.get("recommended_mode") == "together" else "👤")
    print(f"    ✓ PaymentProbability: overall={prob_data['overall']}, {lowest_factor}={prob_data[lowest_factor]}")
    print(f"    ✓ Mobius Readiness: {prob_data.get('agentic_confidence', 0.5):.0%} → {mode_icon} {prob_data.get('recommended_mode', 'together')}")
    
    # Create resolution plan (Layer 2)
    plan = ResolutionPlan(
        patient_context_id=patient.patient_context_id,
        tenant_id=tenant_id,
        gap_types=gap_types,
        status=PlanStatus.ACTIVE,
        initial_probability=prob_data["overall"],
        current_probability=prob_data["overall"],
        target_probability=0.90,
        batch_job_id="seed_demo_patients",
    )
    db.add(plan)
    db.flush()
    
    # Track current step for plan
    current_step_id = None
    
    # Create ATTENDANCE steps
    attendance_completed = group == "eligibility_in_progress"
    print(f"    ATTENDANCE FACTOR ({'Completed' if attendance_completed else 'In Progress'}):")
    
    for step_profile in profile["attendance_steps"]:
        step_def = next(s for s in ATTENDANCE_L3_STEPS if s["step_code"] == step_profile["code"])
        
        # Determine status based on group
        if attendance_completed:
            step_status = StepStatus.ANSWERED
        else:
            status = step_profile.get("status", "pending")
            if status == "answered":
                step_status = StepStatus.ANSWERED
            elif status == "current":
                step_status = StepStatus.CURRENT
            else:
                step_status = StepStatus.PENDING
        
        step = PlanStep(
            plan_id=plan.plan_id,
            step_order=step_def["step_order"],
            step_code=step_def["step_code"],
            step_type=step_def["step_type"],
            input_type=step_def["input_type"],
            question_text=step_def["question_text"],
            description=step_def.get("description"),
            factor_type=step_def["factor_type"],
            can_system_answer=step_def["can_system_answer"],
            assignable_activities=step_def["assignable_activities"],
            answer_options=step_def["answer_options"],
            assignee_type=step_profile["assignee"],
            status=step_status,
        )
        db.add(step)
        db.flush()
        
        if step_status == StepStatus.CURRENT:
            current_step_id = step.step_id
        
        # Create answer if step is answered
        if step_status == StepStatus.ANSWERED:
            answer_value = step_profile["answer"]
            if isinstance(answer_value, list):
                answer_code = ",".join(answer_value)
            else:
                answer_code = answer_value
            
            answer = StepAnswer(
                step_id=step.step_id,
                answer_code=answer_code,
                answer_mode=AnswerMode.AGENTIC if step_profile["assignee"] == "mobius" else AnswerMode.USER_DRIVEN,
            )
            db.add(answer)
        
        # Create evidence links
        evidence_keys = profile["attendance_evidence"].get(step_profile["code"], [])
        for i, ev_key in enumerate(evidence_keys):
            if ev_key not in L4_EVIDENCE:
                continue
            ev_def = L4_EVIDENCE[ev_key]
            evidence = Evidence(
                patient_context_id=patient.patient_context_id,
                factor_type="attendance",
                fact_type=ev_def["fact_type"],
                fact_summary=ev_def["fact_summary"],
                fact_data=ev_def["fact_data"],
                impact_direction=ev_def["impact_direction"],
                impact_weight=ev_def["impact_weight"],
            )
            db.add(evidence)
            db.flush()
            link = PlanStepFactLink(plan_step_id=step.step_id, fact_id=evidence.evidence_id, display_order=i)
            db.add(link)
        
        assignee_icon = "🤖" if step_profile["assignee"] == "mobius" else "👤"
        if step_status == StepStatus.ANSWERED:
            answer_value = step_profile["answer"]
            if isinstance(answer_value, list):
                answer_display = ",".join(answer_value)
            else:
                answer_display = answer_value
            print(f"      ✓ {step_def['step_code']} [{assignee_icon}] → {answer_display}")
        elif step_status == StepStatus.CURRENT:
            print(f"      ► {step_def['step_code']} [{assignee_icon}] → (current)")
        else:
            print(f"      ○ {step_def['step_code']} [{assignee_icon}] → (pending)")
    
    # Create ELIGIBILITY steps (only for eligibility_in_progress group)
    if profile["eligibility_steps"]:
        print(f"    ELIGIBILITY FACTOR (In Progress):")
        for step_profile in profile["eligibility_steps"]:
            step_def = next(s for s in ELIGIBILITY_L3_STEPS if s["step_code"] == step_profile["code"])
            
            # Determine status
            status = step_profile.get("status", "pending")
            if status == "answered":
                step_status = StepStatus.ANSWERED
            elif status == "current":
                step_status = StepStatus.CURRENT
            else:
                step_status = StepStatus.PENDING
            
            step = PlanStep(
                plan_id=plan.plan_id,
                step_order=step_def["step_order"] + 10,  # Offset to come after attendance
                step_code=step_def["step_code"],
                step_type=step_def["step_type"],
                input_type=step_def["input_type"],
                question_text=step_def["question_text"],
                description=step_def.get("description"),
                factor_type=step_def["factor_type"],
                can_system_answer=step_def["can_system_answer"],
                assignable_activities=step_def["assignable_activities"],
                answer_options=step_def["answer_options"],
                assignee_type=step_profile["assignee"],
                status=step_status,
            )
            db.add(step)
            db.flush()
            
            if step_status == StepStatus.CURRENT:
                current_step_id = step.step_id
            
            # Create answer if step is answered
            if status == "answered" and step_profile["answer"]:
                answer = StepAnswer(
                    step_id=step.step_id,
                    answer_code=step_profile["answer"],
                    answer_mode=AnswerMode.AGENTIC if step_profile["assignee"] == "mobius" else AnswerMode.USER_DRIVEN,
                )
                db.add(answer)
            
            # Create evidence links
            evidence_keys = profile["eligibility_evidence"].get(step_profile["code"], [])
            for i, ev_key in enumerate(evidence_keys):
                if ev_key not in L4_EVIDENCE:
                    continue
                ev_def = L4_EVIDENCE[ev_key]
                evidence = Evidence(
                    patient_context_id=patient.patient_context_id,
                    factor_type="eligibility",
                    fact_type=ev_def["fact_type"],
                    fact_summary=ev_def["fact_summary"],
                    fact_data=ev_def["fact_data"],
                    impact_direction=ev_def["impact_direction"],
                    impact_weight=ev_def["impact_weight"],
                )
                db.add(evidence)
                db.flush()
                link = PlanStepFactLink(plan_step_id=step.step_id, fact_id=evidence.evidence_id, display_order=i)
                db.add(link)
            
            assignee_icon = "🤖" if step_profile["assignee"] == "mobius" else "👤"
            status_icon = "✓" if step_status == StepStatus.ANSWERED else ("►" if step_status == StepStatus.CURRENT else "○")
            answer_display = step_profile["answer"] if step_profile["answer"] else "(pending)"
            print(f"      {status_icon} {step_def['step_code']} [{assignee_icon}] → {answer_display}")
    
    db.flush()
    
    # Set current step on plan
    if current_step_id:
        plan.current_step_id = current_step_id
    
    return patient


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("SEEDING 6 DEMO PATIENTS")
    print("=" * 70)
    print("GROUP 1: Attendance In Progress (3 patients)")
    print("GROUP 2: Attendance Completed + Eligibility In Progress (3 patients)")
    print("=" * 70)
    
    init_db()
    db = get_db_session()
    
    try:
        # Get tenant
        tenant = db.query(Tenant).first()
        if not tenant:
            print("ERROR: No tenant found!")
            return
        
        print(f"\nTenant: {tenant.name}")
        
        # Clean up all existing patients
        cleanup_all_patients(db, tenant.tenant_id)
        
        # Create all 6 patients
        patients = []
        all_keys = ["maria", "james", "tanya", "angela", "carlos", "denise"]
        for profile_key in all_keys:
            patient = create_patient(db, tenant.tenant_id, profile_key)
            patients.append(patient)
        
        db.commit()
        
        print("\n" + "=" * 70)
        print("SUCCESS! Created 6 demo patients:")
        print("=" * 70)
        
        print("\n  GROUP 1: ATTENDANCE IN PROGRESS")
        print("  " + "-" * 40)
        for key in ["maria", "james", "tanya"]:
            profile = PATIENT_PROFILES[key]
            print(f"    • {profile['name']}")
            print(f"      Attendance: ► IN PROGRESS")
            print(f"      Theme: {profile['theme']}")
        
        print("\n  GROUP 2: ELIGIBILITY IN PROGRESS")
        print("  " + "-" * 40)
        for key in ["angela", "carlos", "denise"]:
            profile = PATIENT_PROFILES[key]
            print(f"    • {profile['name']}")
            print(f"      Attendance: ✓ COMPLETED")
            print(f"      Eligibility: ► IN PROGRESS")
            print(f"      Theme: {profile['theme']}")
        
        print("\n" + "=" * 70)
        print("To verify, open Sidecar and navigate to each patient.")
        print("=" * 70)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
