#!/usr/bin/env python3
"""
=============================================================================
GOLD STANDARD SEED SCRIPT - Canonical Data Contract for Batch Jobs
=============================================================================

This script defines the AUTHORITATIVE data structure for the L1-L4 hierarchy.
Any batch job that creates patient data MUST follow the patterns defined here.

PATIENTS (12 Demo):
  - 3 Attendance factor patients (Maria, James, Tanya)
  - 3 Eligibility factor patients (Angela, Carlos, Denise)
  - 6 Green/Resolved patients (Patricia, Robert, Linda, Michael, Jennifer, David)

DATA HIERARCHY CONTRACT:

  L1: PaymentProbability
      - overall_probability (0.0-1.0)
      - prob_appointment_attendance, prob_eligibility, prob_coverage, prob_no_errors
      - lowest_factor ("attendance", "eligibility", or "none")
      - lowest_factor_reason (human-readable theme)
      - problem_statement (actionable description)
      - Agentic fields: agentic_confidence, recommended_mode, recommendation_reason, agentic_actions

  L2: ResolutionPlan
      - gap_types: list of factors being addressed
      - status: PlanStatus (ACTIVE, COMPLETED, etc.)
      - factor_mode: FactorType (MOBIUS, TOGETHER, MANUAL)
      - current_step_id: links to active PlanStep

  L3: PlanSteps (per factor type)
      - Attendance: 5 categories (understanding_visit, staying_on_track, clinical_readiness, barriers, escalation)
      - Eligibility: 4 categories (verify_coverage, identify_options, execute_resolution, confirm_resolution)
      - Each step has: question, description, input_type, answer_options, system_suggestion, assignable_activities
      - Steps linked to Evidence via PlanStepFactLink

  L4: Evidence
      - factor_type: which probability factor this evidence relates to
      - fact_type: category of fact (visit_history, insurance_status, barriers, etc.)
      - fact_summary: human-readable summary
      - fact_data: structured JSONB data
      - impact_direction: positive, negative, or neutral
      - impact_weight: 0.0-1.0 influence on probability

USAGE:
  # Seed production database via Cloud SQL proxy
  DATABASE_MODE=cloud python scripts/seed_production_12.py

  # Seed local database
  DATABASE_MODE=local python scripts/seed_production_12.py

BATCH JOB INTEGRATION:
  The ATTENDANCE_STEPS, ELIGIBILITY_STEPS, L4_EVIDENCE, and PATIENT_DEFINITIONS
  constants in this file define the exact data structures that batch jobs should
  produce. The create_patient() function demonstrates the correct creation order
  and relationship linking.
"""

import sys
import os
import uuid
import bcrypt
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
from app.models.evidence import PlanStepFactLink, Evidence
from app.models.event_log import EventLog
from app.models.response import SystemResponse
from app.models.tenant import AppUser, Role
from app.models.activity import Activity, UserActivity


# =============================================================================
# USER DEFINITIONS (5 Demo Users)
# =============================================================================

USER_DEFINITIONS = [
    {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "dev@mobius.local",
        "display_name": "Dev User",
        "first_name": "Dev",
        "role_name": "admin",
        "activities": [
            "verify_eligibility",
            "check_in_patients",
            "schedule_appointments",
            "submit_claims",
            "rework_denials",
            "prior_authorization",
            "patient_collections",
            "post_payments",
            "patient_outreach",
            "document_notes",
            "coordinate_referrals",
        ],
    },
    {
        "user_id": "00000000-0000-0000-0000-000000000010",
        "email": "admin@demo.clinic",
        "display_name": "Alex Admin",
        "first_name": "Alex",
        "role_name": "admin",
        "activities": [
            "verify_eligibility",
            "check_in_patients",
            "schedule_appointments",
            "submit_claims",
            "rework_denials",
            "prior_authorization",
            "patient_collections",
            "post_payments",
            "patient_outreach",
            "document_notes",
            "coordinate_referrals",
        ],
    },
    {
        "user_id": "00000000-0000-0000-0000-000000000011",
        "email": "scheduler@demo.clinic",
        "display_name": "Sam Scheduler",
        "first_name": "Sam",
        "role_name": "staff",
        "activities": [
            "schedule_appointments",
            "check_in_patients",
            "patient_outreach",
        ],
    },
    {
        "user_id": "00000000-0000-0000-0000-000000000012",
        "email": "eligibility@demo.clinic",
        "display_name": "Eli Eligibility",
        "first_name": "Eli",
        "role_name": "staff",
        "activities": [
            "verify_eligibility",
            "check_in_patients",
        ],
    },
    {
        "user_id": "00000000-0000-0000-0000-000000000013",
        "email": "claims@demo.clinic",
        "display_name": "Claire Claims",
        "first_name": "Claire",
        "role_name": "billing_specialist",
        "activities": [
            "submit_claims",
            "rework_denials",
            "post_payments",
            "patient_collections",
        ],
    },
    {
        "user_id": "00000000-0000-0000-0000-000000000014",
        "email": "clinical@demo.clinic",
        "display_name": "Dr. Casey Clinical",
        "first_name": "Casey",
        "role_name": "clinical",
        "activities": [
            "prior_authorization",
            "document_notes",
            "coordinate_referrals",
        ],
    },
]


# =============================================================================
# L3: ATTENDANCE STEP DEFINITIONS (5 Categories)
# =============================================================================

ATTENDANCE_STEPS = [
    {
        "order": 1,
        "code": "understanding_visit",
        "question": "Understanding the Patient's Visit",
        "description": "Determine planning intensity and lead time required for the visit.",
        "can_auto": True,
        "input_type": InputType.SINGLE_CHOICE,
        "assignable_activities": ["schedule_appointments", "patient_outreach"],
        "answer_options": [
            {"code": "new_visit", "label": "New Visit"},
            {"code": "standard_visit", "label": "Standard Visit"},
            {"code": "high_risk_visit", "label": "High-Risk Visit"},
        ],
    },
    {
        "order": 2,
        "code": "staying_on_track",
        "question": "Helping the Patient Stay on Track",
        "description": "Select the appropriate outreach strategy based on responsiveness, preferences, and risk.",
        "can_auto": True,
        "input_type": InputType.SINGLE_CHOICE,
        "assignable_activities": ["patient_outreach", "schedule_appointments"],
        "answer_options": [
            {"code": "standard_outreach", "label": "Standard Outreach (automated)"},
            {"code": "tailored_outreach", "label": "Tailored Outreach (automated)"},
            {"code": "personalized_outreach", "label": "Personalized Outreach (care team call)"},
            {"code": "reestablish_contact", "label": "Re-establish Contact (shared workflow)"},
        ],
    },
    {
        "order": 3,
        "code": "clinical_readiness",
        "question": "Assessing Clinical Readiness",
        "description": "Ensure the planned visit is still appropriate from a safety and stability perspective.",
        "can_auto": True,
        "input_type": InputType.SINGLE_CHOICE,
        "assignable_activities": ["patient_outreach"],
        "answer_options": [
            {"code": "clinically_stable", "label": "Clinically Stable - Proceed as Planned"},
            {"code": "possible_decompensation", "label": "Possible Decompensation - Care Team Review"},
            {"code": "acute_concern", "label": "Acute Concern - Immediate Escalation"},
            {"code": "insufficient_info", "label": "Insufficient Information - Monitor Closely"},
        ],
    },
    {
        "order": 4,
        "code": "reducing_risks",
        "question": "Reducing Attendance Risks",
        "description": "Identify non-clinical barriers that could prevent attendance.",
        "can_auto": True,
        "input_type": InputType.MULTI_CHOICE,
        "assignable_activities": ["patient_outreach", "schedule_appointments"],
        "answer_options": [
            {"code": "no_barriers", "label": "No Material Barriers"},
            {"code": "transportation", "label": "Transportation Barriers"},
            {"code": "social_environmental", "label": "Social & Environmental Barriers"},
            {"code": "scheduling_conflict", "label": "Scheduling Conflicts"},
            {"code": "readiness_anxiety", "label": "Readiness or Anxiety-Related"},
            {"code": "communication", "label": "Communication Barriers"},
        ],
    },
    {
        "order": 5,
        "code": "backup_plan",
        "question": "Creating a Backup Plan",
        "description": "Manage capacity responsibly based on anticipated likelihood of attendance.",
        "can_auto": True,
        "input_type": InputType.SINGLE_CHOICE,
        "assignable_activities": ["schedule_appointments"],
        "answer_options": [
            {"code": "proceed_scheduled", "label": "Proceed as Scheduled"},
            {"code": "increased_confirmation", "label": "Increased Confirmation Required"},
            {"code": "double_booking", "label": "Double-Booking Approved"},
            {"code": "advance_reschedule", "label": "Advance Reschedule Recommended"},
            {"code": "modality_shift", "label": "Modality Shift Planned"},
            {"code": "visit_released", "label": "Visit Released"},
        ],
    },
]


# =============================================================================
# L3: ELIGIBILITY STEP DEFINITIONS (5 Categories)
# =============================================================================

ELIGIBILITY_STEPS = [
    {
        "order": 1,
        "code": "verify_coverage",
        "question": "Verifying Current Coverage Status",
        "description": "Determine if patient has active insurance coverage on file.",
        "can_auto": True,
        "input_type": InputType.SINGLE_CHOICE,
        "assignable_activities": ["verify_eligibility", "check_in_patients"],
        "answer_options": [
            {"code": "active_verified", "label": "Active Coverage Verified"},
            {"code": "expired_coverage", "label": "Coverage Expired"},
            {"code": "no_insurance_on_file", "label": "No Insurance on File"},
            {"code": "pending_verification", "label": "Pending Verification"},
        ],
    },
    {
        "order": 2,
        "code": "identify_gaps",
        "question": "Identifying Coverage Gaps",
        "description": "Analyze what specific coverage issues need to be addressed.",
        "can_auto": True,
        "input_type": InputType.MULTI_CHOICE,
        "assignable_activities": ["verify_eligibility"],
        "answer_options": [
            {"code": "no_gaps", "label": "No Coverage Gaps"},
            {"code": "missing_card", "label": "Missing Insurance Card"},
            {"code": "lapsed_premium", "label": "Lapsed Premium Payment"},
            {"code": "job_change", "label": "Possible Job/Coverage Change"},
            {"code": "coordination_needed", "label": "Coordination of Benefits Needed"},
        ],
    },
    {
        "order": 3,
        "code": "explore_options",
        "question": "Exploring Coverage Options",
        "description": "Identify alternative coverage paths if current coverage is insufficient.",
        "can_auto": False,
        "input_type": InputType.SINGLE_CHOICE,
        "assignable_activities": ["verify_eligibility", "patient_outreach"],
        "answer_options": [
            {"code": "reinstate_current", "label": "Reinstate Current Coverage"},
            {"code": "new_employer", "label": "Check New Employer Coverage"},
            {"code": "marketplace", "label": "Explore Marketplace Options"},
            {"code": "medicaid_screen", "label": "Screen for Medicaid/Medicare"},
            {"code": "self_pay", "label": "Discuss Self-Pay Options"},
            {"code": "charity_care", "label": "Explore Charity Care"},
        ],
    },
    {
        "order": 4,
        "code": "initiate_action",
        "question": "Initiating Coverage Action",
        "description": "Take action to resolve coverage issues.",
        "can_auto": False,
        "input_type": InputType.SINGLE_CHOICE,
        "assignable_activities": ["verify_eligibility", "patient_outreach"],
        "answer_options": [
            {"code": "contact_patient", "label": "Contact Patient for Info"},
            {"code": "contact_payer", "label": "Contact Payer Directly"},
            {"code": "submit_application", "label": "Submit Coverage Application"},
            {"code": "send_portal_request", "label": "Send Portal Request"},
            {"code": "schedule_callback", "label": "Schedule Patient Callback"},
        ],
    },
    {
        "order": 5,
        "code": "confirm_eligibility",
        "question": "Confirming Eligibility",
        "description": "Final verification that coverage is active and sufficient.",
        "can_auto": True,
        "input_type": InputType.SINGLE_CHOICE,
        "assignable_activities": ["verify_eligibility"],
        "answer_options": [
            {"code": "fully_verified", "label": "Fully Verified - Ready for Visit"},
            {"code": "partial_coverage", "label": "Partial Coverage - Patient Aware"},
            {"code": "self_pay_confirmed", "label": "Self-Pay Confirmed"},
            {"code": "pending_resolution", "label": "Pending Resolution - Monitor"},
        ],
    },
]


# =============================================================================
# L4: EVIDENCE LIBRARY
# =============================================================================

L4_EVIDENCE = {
    # Attendance - Understanding Visit
    "prior_completed_visits": {
        "factor_type": "attendance",
        "fact_type": "visit_history",
        "fact_summary": "Prior completed visits of same type",
        "fact_data": {"visit_count": 12, "same_type_count": 8},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "stable_attendance_history": {
        "factor_type": "attendance",
        "fact_type": "attendance_history",
        "fact_summary": "Stable attendance history with consistent pattern",
        "fact_data": {"attendance_rate": 0.95, "pattern": "consistent"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "no_recent_noshow": {
        "factor_type": "attendance",
        "fact_type": "attendance_history",
        "fact_summary": "No recent no-shows in past 6 months",
        "fact_data": {"noshow_count": 0, "period_months": 6},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "no_prior_visits": {
        "factor_type": "attendance",
        "fact_type": "visit_history",
        "fact_summary": "No prior completed visits for this service",
        "fact_data": {"visit_count": 0, "is_new_patient": True},
        "impact_direction": "neutral",
        "impact_weight": 0.3,
    },
    "recent_noshow_history": {
        "factor_type": "attendance",
        "fact_type": "attendance_history",
        "fact_summary": "Recent no-show history detected",
        "fact_data": {"noshow_count": 3, "period_months": 6},
        "impact_direction": "negative",
        "impact_weight": 0.6,
    },
    "long_gap_since_visit": {
        "factor_type": "attendance",
        "fact_type": "visit_history",
        "fact_summary": "Long gap since last visit (6+ months)",
        "fact_data": {"months_since_last": 9, "gap_threshold": 6},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    
    # Attendance - Staying on Track
    "valid_contact_info": {
        "factor_type": "attendance",
        "fact_type": "contact_info",
        "fact_summary": "Valid phone and email on file",
        "fact_data": {"phone_valid": True, "email_valid": True},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "prior_responsiveness": {
        "factor_type": "attendance",
        "fact_type": "engagement_history",
        "fact_summary": "Patient responds to automated outreach",
        "fact_data": {"response_rate": 0.85, "preferred_channel": "sms"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "poor_automated_response": {
        "factor_type": "attendance",
        "fact_type": "engagement_history",
        "fact_summary": "Poor response to automated outreach",
        "fact_data": {"response_rate": 0.15, "requires_personal": True},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    
    # Attendance - Clinical Readiness
    "no_crisis_indicators": {
        "factor_type": "attendance",
        "fact_type": "clinical_status",
        "fact_summary": "No crisis indicators present",
        "fact_data": {"crisis_flags": [], "stable": True},
        "impact_direction": "positive",
        "impact_weight": 0.6,
    },
    "medication_change": {
        "factor_type": "attendance",
        "fact_type": "clinical_status",
        "fact_summary": "Recent medication change may affect readiness",
        "fact_data": {"medication_changed": True, "days_ago": 14},
        "impact_direction": "neutral",
        "impact_weight": 0.3,
    },
    "care_team_risk_flag": {
        "factor_type": "attendance",
        "fact_type": "clinical_status",
        "fact_summary": "Care team flagged as high-risk",
        "fact_data": {"risk_level": "high", "flagged_by": "care_team"},
        "impact_direction": "negative",
        "impact_weight": 0.7,
    },
    
    # Attendance - Barriers
    "no_barriers_identified": {
        "factor_type": "attendance",
        "fact_type": "barriers",
        "fact_summary": "No material barriers identified",
        "fact_data": {"barriers": [], "risk_level": "low"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "transportation_barrier": {
        "factor_type": "attendance",
        "fact_type": "barriers",
        "fact_summary": "Transportation barrier identified",
        "fact_data": {"barrier_type": "transportation", "has_ride": False},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "work_schedule_conflict": {
        "factor_type": "attendance",
        "fact_type": "barriers",
        "fact_summary": "Work schedule may conflict with appointment",
        "fact_data": {"barrier_type": "scheduling", "conflict_type": "work"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    
    # Eligibility - Coverage
    "active_commercial_coverage": {
        "factor_type": "eligibility",
        "fact_type": "insurance_status",
        "fact_summary": "Active commercial insurance verified",
        "fact_data": {"payer": "Blue Cross", "plan_type": "PPO", "active": True},
        "impact_direction": "positive",
        "impact_weight": 0.8,
    },
    "medicaid_expired": {
        "factor_type": "eligibility",
        "fact_type": "insurance_status",
        "fact_summary": "Medicaid coverage expired",
        "fact_data": {"payer": "Medicaid", "expiry_date": "2025-12-01", "active": False},
        "impact_direction": "negative",
        "impact_weight": 0.7,
    },
    "no_insurance_on_file": {
        "factor_type": "eligibility",
        "fact_type": "insurance_status",
        "fact_summary": "No insurance information on file",
        "fact_data": {"has_insurance": False, "self_pay": None},
        "impact_direction": "negative",
        "impact_weight": 0.8,
    },
    "reinstatement_eligible": {
        "factor_type": "eligibility",
        "fact_type": "coverage_options",
        "fact_summary": "Patient may be eligible for Medicaid reinstatement",
        "fact_data": {"option": "medicaid_reinstatement", "likelihood": "high"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
}


# =============================================================================
# PATIENT DEFINITIONS (12 Total)
# =============================================================================

PATIENTS = [
    # -------------------------------------------------------------------------
    # ATTENDANCE FACTOR PATIENTS (3)
    # -------------------------------------------------------------------------
    {
        "name": "Maria Gonzalez",
        "mrn": "MARIA01",
        "patient_key": "attend_maria",
        "factor": "attendance",
        "theme": "Fully automatable - all Mobius",
        "probability": {"overall": 0.92, "attendance": 0.95, "eligibility": 0.90, "coverage": 0.92, "errors": 0.94},
        "problem": "Preparing Maria for her visit",
        "status": "active",
        "assignee": "mobius",
        # L1: Agentic Recommendations
        "agentic_confidence": 0.92,
        "recommended_mode": "mobius",
        "recommendation_reason": "High automation potential - stable patient with excellent attendance history",
        "agentic_actions": ["send_reminder", "confirm_via_portal", "verify_contact"],
        # L3: Step answers and evidence
        "steps": [
            {"code": "understanding_visit", "answer": "standard_visit", "assignee": "mobius", "status": "current"},
            {"code": "staying_on_track", "answer": "standard_outreach", "assignee": "mobius", "status": "pending"},
            {"code": "clinical_readiness", "answer": "clinically_stable", "assignee": "mobius", "status": "pending"},
            {"code": "reducing_risks", "answer": "no_barriers", "assignee": "mobius", "status": "pending"},
            {"code": "backup_plan", "answer": "proceed_scheduled", "assignee": "mobius", "status": "pending"},
        ],
        # L4: Evidence per step
        "evidence": {
            "understanding_visit": ["prior_completed_visits", "stable_attendance_history", "no_recent_noshow"],
            "staying_on_track": ["valid_contact_info", "prior_responsiveness"],
            "clinical_readiness": ["no_crisis_indicators"],
            "reducing_risks": ["no_barriers_identified"],
            "backup_plan": ["stable_attendance_history"],
        },
    },
    {
        "name": "James Walker",
        "mrn": "JAMES01",
        "patient_key": "attend_james",
        "factor": "attendance",
        "theme": "Automation with review - Mobius + user",
        "probability": {"overall": 0.72, "attendance": 0.68, "eligibility": 0.85, "coverage": 0.80, "errors": 0.88},
        "problem": "Preparing James for his visit",
        "status": "active",
        "assignee": "mobius",
        # L1: Agentic Recommendations
        "agentic_confidence": 0.68,
        "recommended_mode": "together",
        "recommendation_reason": "Mixed automation - new patient needs some manual review for clinical readiness",
        "agentic_actions": ["send_reminder", "tailored_outreach"],
        # L3: Step answers and evidence
        "steps": [
            {"code": "understanding_visit", "answer": "new_visit", "assignee": "mobius", "status": "current"},
            {"code": "staying_on_track", "answer": "tailored_outreach", "assignee": "mobius", "status": "pending"},
            {"code": "clinical_readiness", "answer": "possible_decompensation", "assignee": "user", "status": "pending"},
            {"code": "reducing_risks", "answer": "scheduling_conflict", "assignee": "user", "status": "pending"},
            {"code": "backup_plan", "answer": "increased_confirmation", "assignee": "mobius", "status": "pending"},
        ],
        # L4: Evidence per step
        "evidence": {
            "understanding_visit": ["no_prior_visits"],
            "staying_on_track": ["valid_contact_info"],
            "clinical_readiness": ["medication_change"],
            "reducing_risks": ["work_schedule_conflict"],
            "backup_plan": [],
        },
    },
    {
        "name": "Tanya Brooks",
        "mrn": "TANYA01",
        "patient_key": "attend_tanya",
        "factor": "attendance",
        "theme": "Human-led, system-supported - all user",
        "probability": {"overall": 0.45, "attendance": 0.35, "eligibility": 0.88, "coverage": 0.85, "errors": 0.90},
        "problem": "Re-engaging Tanya for upcoming appointment",
        "status": "active",
        "assignee": "user",
        # L1: Agentic Recommendations
        "agentic_confidence": 0.35,
        "recommended_mode": "manual",
        "recommendation_reason": "High-risk patient requires personal outreach - poor response to automation",
        "agentic_actions": [],
        # L3: Step answers and evidence
        "steps": [
            {"code": "understanding_visit", "answer": "high_risk_visit", "assignee": "user", "status": "current"},
            {"code": "staying_on_track", "answer": "personalized_outreach", "assignee": "user", "status": "pending"},
            {"code": "clinical_readiness", "answer": "possible_decompensation", "assignee": "user", "status": "pending"},
            {"code": "reducing_risks", "answer": "transportation", "assignee": "user", "status": "pending"},
            {"code": "backup_plan", "answer": "modality_shift", "assignee": "user", "status": "pending"},
        ],
        # L4: Evidence per step
        "evidence": {
            "understanding_visit": ["recent_noshow_history", "long_gap_since_visit", "care_team_risk_flag"],
            "staying_on_track": ["poor_automated_response"],
            "clinical_readiness": ["care_team_risk_flag"],
            "reducing_risks": ["transportation_barrier"],
            "backup_plan": ["recent_noshow_history"],
        },
    },
    
    # -------------------------------------------------------------------------
    # ELIGIBILITY FACTOR PATIENTS (3)
    # -------------------------------------------------------------------------
    {
        "name": "Angela Morris",
        "mrn": "ANGELA01",
        "patient_key": "elig_angela",
        "factor": "eligibility",
        "theme": "Simple eligibility - active commercial PPO",
        "probability": {"overall": 0.88, "attendance": 0.95, "eligibility": 0.82, "coverage": 0.90, "errors": 0.92},
        "problem": "Verifying Angela's insurance coverage",
        "status": "active",
        "assignee": "mobius",
        # L1: Agentic Recommendations
        "agentic_confidence": 0.88,
        "recommended_mode": "mobius",
        "recommendation_reason": "Simple verification - commercial PPO with clean history",
        "agentic_actions": ["run_eligibility_check", "verify_benefits"],
        # L3: Step answers and evidence
        "steps": [
            {"code": "verify_coverage", "answer": "active_verified", "assignee": "mobius", "status": "current"},
            {"code": "identify_gaps", "answer": "no_gaps", "assignee": "mobius", "status": "pending"},
            {"code": "explore_options", "answer": None, "assignee": "mobius", "status": "pending"},
            {"code": "initiate_action", "answer": None, "assignee": "mobius", "status": "pending"},
            {"code": "confirm_eligibility", "answer": "fully_verified", "assignee": "mobius", "status": "pending"},
        ],
        # L4: Evidence per step
        "evidence": {
            "verify_coverage": ["active_commercial_coverage"],
            "identify_gaps": [],
            "explore_options": [],
            "initiate_action": [],
            "confirm_eligibility": ["active_commercial_coverage"],
        },
    },
    {
        "name": "Carlos Ramirez",
        "mrn": "CARLOS01",
        "patient_key": "elig_carlos",
        "factor": "eligibility",
        "theme": "Complex eligibility - Medicaid reinstatement needed",
        "probability": {"overall": 0.55, "attendance": 0.92, "eligibility": 0.38, "coverage": 0.75, "errors": 0.88},
        "problem": "Helping Carlos reinstate Medicaid coverage",
        "status": "active",
        "assignee": "user",
        # L1: Agentic Recommendations
        "agentic_confidence": 0.45,
        "recommended_mode": "together",
        "recommendation_reason": "Medicaid reinstatement requires patient action - system can guide process",
        "agentic_actions": ["check_medicaid_status", "send_portal_request"],
        # L3: Step answers and evidence
        "steps": [
            {"code": "verify_coverage", "answer": "expired_coverage", "assignee": "mobius", "status": "current"},
            {"code": "identify_gaps", "answer": "lapsed_premium", "assignee": "mobius", "status": "pending"},
            {"code": "explore_options", "answer": "medicaid_screen", "assignee": "user", "status": "pending"},
            {"code": "initiate_action", "answer": "contact_patient", "assignee": "user", "status": "pending"},
            {"code": "confirm_eligibility", "answer": "pending_resolution", "assignee": "user", "status": "pending"},
        ],
        # L4: Evidence per step
        "evidence": {
            "verify_coverage": ["medicaid_expired"],
            "identify_gaps": ["medicaid_expired"],
            "explore_options": ["reinstatement_eligible"],
            "initiate_action": ["valid_contact_info"],
            "confirm_eligibility": [],
        },
    },
    {
        "name": "Denise Walker",
        "mrn": "DENISE01",
        "patient_key": "elig_denise",
        "factor": "eligibility",
        "theme": "Escalated eligibility - no coverage, multiple paths",
        "probability": {"overall": 0.42, "attendance": 0.90, "eligibility": 0.25, "coverage": 0.70, "errors": 0.85},
        "problem": "Finding coverage options for Denise",
        "status": "active",
        "assignee": "user",
        # L1: Agentic Recommendations
        "agentic_confidence": 0.30,
        "recommended_mode": "manual",
        "recommendation_reason": "No coverage on file - requires financial counseling and manual exploration",
        "agentic_actions": [],
        # L3: Step answers and evidence
        "steps": [
            {"code": "verify_coverage", "answer": "no_insurance_on_file", "assignee": "user", "status": "current"},
            {"code": "identify_gaps", "answer": "missing_card", "assignee": "user", "status": "pending"},
            {"code": "explore_options", "answer": "charity_care", "assignee": "user", "status": "pending"},
            {"code": "initiate_action", "answer": "schedule_callback", "assignee": "user", "status": "pending"},
            {"code": "confirm_eligibility", "answer": "pending_resolution", "assignee": "user", "status": "pending"},
        ],
        # L4: Evidence per step
        "evidence": {
            "verify_coverage": ["no_insurance_on_file"],
            "identify_gaps": ["no_insurance_on_file"],
            "explore_options": [],
            "initiate_action": [],
            "confirm_eligibility": [],
        },
    },
    
    # -------------------------------------------------------------------------
    # GREEN/RESOLVED PATIENTS (6)
    # -------------------------------------------------------------------------
    {
        "name": "Patricia Chen",
        "mrn": "PATRIC01",
        "patient_key": "green_patricia",
        "factor": None,
        "theme": "All clear - ready for visit",
        "probability": {"overall": 0.95, "attendance": 0.96, "eligibility": 0.94, "coverage": 0.95, "errors": 0.97},
        "problem": None,
        "status": "resolved",
        "assignee": None,
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [],
        "evidence": {},
    },
    {
        "name": "Robert Kim",
        "mrn": "ROBERT01",
        "patient_key": "green_robert",
        "factor": None,
        "theme": "Eligibility verified - all checks passed",
        "probability": {"overall": 0.93, "attendance": 0.92, "eligibility": 0.96, "coverage": 0.93, "errors": 0.95},
        "problem": None,
        "status": "resolved",
        "assignee": None,
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [],
        "evidence": {},
    },
    {
        "name": "Linda Thompson",
        "mrn": "LINDA01",
        "patient_key": "green_linda",
        "factor": None,
        "theme": "Coverage confirmed - auth approved",
        "probability": {"overall": 0.94, "attendance": 0.93, "eligibility": 0.95, "coverage": 0.96, "errors": 0.94},
        "problem": None,
        "status": "resolved",
        "assignee": None,
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [],
        "evidence": {},
    },
    {
        "name": "Michael Davis",
        "mrn": "MICHAE01",
        "patient_key": "green_michael",
        "factor": None,
        "theme": "Attendance confirmed - patient engaged",
        "probability": {"overall": 0.96, "attendance": 0.98, "eligibility": 0.94, "coverage": 0.95, "errors": 0.96},
        "problem": None,
        "status": "resolved",
        "assignee": None,
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [],
        "evidence": {},
    },
    {
        "name": "Jennifer Martinez",
        "mrn": "JENNIF01",
        "patient_key": "green_jennifer",
        "factor": None,
        "theme": "Clean claim ready - documentation complete",
        "probability": {"overall": 0.95, "attendance": 0.94, "eligibility": 0.95, "coverage": 0.94, "errors": 0.98},
        "problem": None,
        "status": "resolved",
        "assignee": None,
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [],
        "evidence": {},
    },
    {
        "name": "David Wilson",
        "mrn": "DAVID01",
        "patient_key": "green_david",
        "factor": None,
        "theme": "All factors resolved - exemplary patient",
        "probability": {"overall": 0.97, "attendance": 0.97, "eligibility": 0.96, "coverage": 0.97, "errors": 0.98},
        "problem": None,
        "status": "resolved",
        "assignee": None,
        "agentic_confidence": None,
        "recommended_mode": None,
        "recommendation_reason": None,
        "agentic_actions": None,
        "steps": [],
        "evidence": {},
    },
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def cleanup_existing(db, tenant_id):
    """Delete existing demo patients."""
    print("\n--- Cleaning up existing data ---")
    
    from app.models.event_log import EventLog
    from app.models.response import MiniSubmission, SystemResponse
    from app.models.sidecar import UserOwnedTask, UserAlert, MilestoneHistory, MilestoneSubstep, Milestone
    from app.models.resolution import StepAnswer, PlanNote, UserRemedy
    from app.models.probability import TaskInstance
    from app.models.evidence import FactSourceLink, SourceDocument, RawData
    
    # Get patient IDs to delete
    patient_keys = [p["patient_key"] for p in PATIENTS]
    patients = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id,
        PatientContext.patient_key.in_(patient_keys)
    ).all()
    
    patient_ids = [p.patient_context_id for p in patients]
    
    if not patient_ids:
        print("  No existing patients to clean up")
        return
    
    # Delete related records
    db.query(EventLog).filter(EventLog.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(MiniSubmission).filter(MiniSubmission.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(SystemResponse).filter(SystemResponse.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    
    # Get plan IDs
    plans = db.query(ResolutionPlan).filter(ResolutionPlan.patient_context_id.in_(patient_ids)).all()
    plan_ids = [p.plan_id for p in plans]
    
    if plan_ids:
        steps = db.query(PlanStep).filter(PlanStep.plan_id.in_(plan_ids)).all()
        step_ids = [s.step_id for s in steps]
        
        if step_ids:
            db.query(StepAnswer).filter(StepAnswer.step_id.in_(step_ids)).delete(synchronize_session=False)
            db.query(PlanStepFactLink).filter(PlanStepFactLink.plan_step_id.in_(step_ids)).delete(synchronize_session=False)
        
        db.query(UserRemedy).filter(UserRemedy.plan_id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(PlanNote).filter(PlanNote.plan_id.in_(plan_ids)).delete(synchronize_session=False)
        
        # Clear current_step_id references before deleting steps
        for plan in plans:
            plan.current_step_id = None
        db.flush()
        
        db.query(PlanStep).filter(PlanStep.plan_id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(ResolutionPlan).filter(ResolutionPlan.plan_id.in_(plan_ids)).delete(synchronize_session=False)
    
    db.query(Evidence).filter(Evidence.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(PaymentProbability).filter(PaymentProbability.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(TaskInstance).filter(TaskInstance.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(PatientId).filter(PatientId.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    
    # Try to delete from mock_emr if it exists
    try:
        from sqlalchemy import text
        db.execute(text("DELETE FROM mock_emr WHERE patient_context_id = ANY(:ids)"), {"ids": patient_ids})
    except Exception:
        pass  # Table may not exist
    db.query(PatientSnapshot).filter(PatientSnapshot.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    
    # Clean up sidecar tables (Milestone, UserAlert, UserOwnedTask)
    milestones = db.query(Milestone).filter(Milestone.patient_context_id.in_(patient_ids)).all()
    milestone_ids = [m.milestone_id for m in milestones]
    if milestone_ids:
        db.query(UserAlert).filter(UserAlert.related_milestone_id.in_(milestone_ids)).update(
            {"related_milestone_id": None}, synchronize_session=False
        )
        db.query(MilestoneHistory).filter(MilestoneHistory.milestone_id.in_(milestone_ids)).delete(synchronize_session=False)
        db.query(MilestoneSubstep).filter(MilestoneSubstep.milestone_id.in_(milestone_ids)).delete(synchronize_session=False)
        db.query(Milestone).filter(Milestone.milestone_id.in_(milestone_ids)).delete(synchronize_session=False)
    
    db.query(UserAlert).filter(UserAlert.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(UserOwnedTask).filter(UserOwnedTask.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(EventLog).filter(EventLog.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(SystemResponse).filter(SystemResponse.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    
    db.query(PatientContext).filter(PatientContext.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    
    db.flush()
    print(f"  Cleaned up {len(patient_ids)} existing patients")


def create_patient(db, tenant_id, patient_def):
    """Create a single patient with all L1-L4 data."""
    
    # Create patient context
    patient = PatientContext(
        tenant_id=tenant_id,
        patient_key=patient_def["patient_key"],
        attention_status="resolved" if patient_def["status"] == "resolved" else None,
        resolved_until=datetime.utcnow() + timedelta(days=30) if patient_def["status"] == "resolved" else None,
    )
    db.add(patient)
    db.flush()
    
    # Create snapshot
    snapshot = PatientSnapshot(
        patient_context_id=patient.patient_context_id,
        display_name=patient_def["name"],
        id_label="MRN",
        id_masked=f"****{patient_def['mrn']}",
        verified=True,
        data_complete=True,
    )
    db.add(snapshot)
    
    # Create patient ID
    patient_id = PatientId(
        patient_context_id=patient.patient_context_id,
        id_type="mrn",
        id_value=f"MRN-{patient_def['mrn']}",
        is_primary=True,
    )
    db.add(patient_id)
    
    # Create L1: PaymentProbability with agentic recommendations
    prob_data = patient_def["probability"]
    prob = PaymentProbability(
        patient_context_id=patient.patient_context_id,
        target_date=date.today() + timedelta(days=7),
        overall_probability=prob_data["overall"],
        confidence=0.88,
        prob_appointment_attendance=prob_data["attendance"],
        prob_eligibility=prob_data["eligibility"],
        prob_coverage=prob_data["coverage"],
        prob_no_errors=prob_data["errors"],
        lowest_factor=patient_def["factor"] or "none",
        lowest_factor_reason=patient_def["theme"],
        problem_statement=patient_def["problem"],
        batch_job_id="production_seed_12",
        # Agentic recommendations
        agentic_confidence=patient_def.get("agentic_confidence"),
        recommended_mode=patient_def.get("recommended_mode"),
        recommendation_reason=patient_def.get("recommendation_reason"),
        agentic_actions=patient_def.get("agentic_actions"),
    )
    db.add(prob)
    db.flush()
    
    # Create L4: Evidence records (for all patients)
    evidence_map = patient_def.get("evidence", {})
    evidence_objects = {}
    for step_code, evidence_keys in evidence_map.items():
        for evidence_key in evidence_keys:
            if evidence_key in L4_EVIDENCE and evidence_key not in evidence_objects:
                ev_def = L4_EVIDENCE[evidence_key]
                evidence = Evidence(
                    patient_context_id=patient.patient_context_id,
                    factor_type=ev_def["factor_type"],
                    fact_type=ev_def["fact_type"],
                    fact_summary=ev_def["fact_summary"],
                    fact_data=ev_def["fact_data"],
                    impact_direction=ev_def["impact_direction"],
                    impact_weight=ev_def["impact_weight"],
                )
                db.add(evidence)
                db.flush()
                evidence_objects[evidence_key] = evidence
    
    # Create L2: ResolutionPlan (if active)
    if patient_def["status"] == "active" and patient_def["factor"]:
        plan = ResolutionPlan(
            patient_context_id=patient.patient_context_id,
            tenant_id=tenant_id,
            gap_types=[patient_def["factor"]],
            status=PlanStatus.ACTIVE,
            initial_probability=prob_data["overall"],
            current_probability=prob_data["overall"],
            target_probability=0.90,
            batch_job_id="production_seed_12",
        )
        db.add(plan)
        db.flush()
        
        # Get step definitions
        steps_def = ATTENDANCE_STEPS if patient_def["factor"] == "attendance" else ELIGIBILITY_STEPS
        factor_type = FactorType.ATTENDANCE if patient_def["factor"] == "attendance" else FactorType.ELIGIBILITY
        
        # Get patient-specific step profiles
        step_profiles = {s["code"]: s for s in patient_def.get("steps", [])}
        
        first_step_id = None
        for step_def in steps_def:
            step_profile = step_profiles.get(step_def["code"], {})
            
            # Determine status from profile or default
            profile_status = step_profile.get("status", "pending")
            if profile_status == "current":
                status = StepStatus.CURRENT
            elif profile_status == "answered":
                status = StepStatus.ANSWERED
            else:
                status = StepStatus.PENDING
            
            # Determine assignee from profile or patient default
            assignee = step_profile.get("assignee", patient_def["assignee"])
            
            # Create L3: PlanStep with answer_options
            step = PlanStep(
                plan_id=plan.plan_id,
                step_order=step_def["order"],
                step_code=step_def["code"],
                step_type=StepType.QUESTION,
                input_type=step_def.get("input_type", InputType.SINGLE_CHOICE),
                question_text=step_def["question"],
                description=step_def.get("description"),
                factor_type=factor_type,
                can_system_answer=step_def["can_auto"],
                assignable_activities=step_def.get("assignable_activities"),
                answer_options=step_def.get("answer_options"),
                assignee_type=assignee,
                status=status,
            )
            db.add(step)
            db.flush()
            
            if status == StepStatus.CURRENT and first_step_id is None:
                first_step_id = step.step_id
            
            # Link L4 evidence to step
            evidence_keys_for_step = evidence_map.get(step_def["code"], [])
            for evidence_key in evidence_keys_for_step:
                if evidence_key in evidence_objects:
                    link = PlanStepFactLink(
                        plan_step_id=step.step_id,
                        fact_id=evidence_objects[evidence_key].evidence_id,
                    )
                    db.add(link)
        
        if first_step_id:
            plan.current_step_id = first_step_id
    
    db.flush()
    return patient


def create_users(db, tenant_id):
    """Create demo users with roles and activities."""
    
    # Generate password hash for demo1234
    password_hash = bcrypt.hashpw(b'demo1234', bcrypt.gensalt()).decode('utf-8')
    
    # Get or create roles
    role_cache = {}
    for user_def in USER_DEFINITIONS:
        role_name = user_def["role_name"]
        if role_name not in role_cache:
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
                db.flush()
            role_cache[role_name] = role
    
    # Ensure all required activities exist
    all_activity_codes = set()
    for user_def in USER_DEFINITIONS:
        all_activity_codes.update(user_def["activities"])
    
    activity_labels = {
        "verify_eligibility": "Verify eligibility",
        "check_in_patients": "Check in patients",
        "schedule_appointments": "Schedule appointments",
        "submit_claims": "Submit claims",
        "rework_denials": "Rework denied claims",
        "prior_authorization": "Handle prior authorizations",
        "patient_collections": "Patient collections",
        "post_payments": "Post payments",
        "patient_outreach": "Patient outreach",
        "document_notes": "Document clinical notes",
        "coordinate_referrals": "Coordinate referrals",
    }
    
    for code in all_activity_codes:
        existing = db.query(Activity).filter(Activity.activity_code == code).first()
        if not existing:
            activity = Activity(
                activity_code=code,
                label=activity_labels.get(code, code.replace("_", " ").title()),
            )
            db.add(activity)
    db.flush()
    
    # Get activity cache
    activity_cache = {}
    activities = db.query(Activity).all()
    for act in activities:
        activity_cache[act.activity_code] = act
    
    # Create users
    created_count = 0
    for user_def in USER_DEFINITIONS:
        user_id = uuid.UUID(user_def["user_id"])
        
        # Check if user exists
        existing = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if existing:
            # Update existing user
            existing.email = user_def["email"]
            existing.display_name = user_def["display_name"]
            existing.first_name = user_def["first_name"]
            existing.role_id = role_cache[user_def["role_name"]].role_id
            existing.password_hash = password_hash  # Set password to demo1234
            user = existing
        else:
            # Create new user
            user = AppUser(
                user_id=user_id,
                tenant_id=tenant_id,
                email=user_def["email"],
                display_name=user_def["display_name"],
                first_name=user_def["first_name"],
                role_id=role_cache[user_def["role_name"]].role_id,
                status="active",
                password_hash=password_hash,  # Set password to demo1234
            )
            db.add(user)
            created_count += 1
        
        db.flush()
        
        # Clear existing activities for this user
        db.query(UserActivity).filter(UserActivity.user_id == user_id).delete(synchronize_session=False)
        
        # Add user activities
        for i, activity_code in enumerate(user_def["activities"]):
            if activity_code in activity_cache:
                user_activity = UserActivity(
                    user_id=user_id,
                    activity_id=activity_cache[activity_code].activity_id,
                    is_primary=(i == 0),  # First activity is primary
                )
                db.add(user_activity)
    
    db.flush()
    return created_count


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("PRODUCTION SEED - 12 DEMO PATIENTS (L1-L4)")
    print("=" * 60)
    
    init_db()
    db = get_db_session()
    
    try:
        # Get or create tenant
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(
                tenant_id=uuid.uuid4(),
                name="Mobius Health System",
                created_at=datetime.utcnow(),
            )
            db.add(tenant)
            db.flush()
            print(f"\nCreated tenant: {tenant.name}")
        else:
            print(f"\nTenant: {tenant.name}")
        
        # Clean up existing patients
        cleanup_existing(db, tenant.tenant_id)
        
        # Create users
        print("\n--- Creating Demo Users ---")
        user_count = create_users(db, tenant.tenant_id)
        for user_def in USER_DEFINITIONS:
            role_icon = "👤" if user_def["role_name"] != "admin" else "👑"
            print(f"  {role_icon} {user_def['display_name']} ({user_def['email']}) - {user_def['role_name']}")
        
        # Create patients
        print("\n--- Creating 12 Patients with L1-L4 Data ---")
        
        attendance_count = 0
        eligibility_count = 0
        green_count = 0
        
        for patient_def in PATIENTS:
            patient = create_patient(db, tenant.tenant_id, patient_def)
            
            status_icon = "🟢" if patient_def["status"] == "resolved" else "🔵"
            factor_label = patient_def["factor"] or "resolved"
            mode_label = f" [{patient_def.get('recommended_mode', 'n/a')}]" if patient_def.get("recommended_mode") else ""
            print(f"  {status_icon} {patient_def['name']} ({factor_label}){mode_label}")
            
            if patient_def["factor"] == "attendance":
                attendance_count += 1
            elif patient_def["factor"] == "eligibility":
                eligibility_count += 1
            else:
                green_count += 1
        
        db.commit()
        
        print("\n" + "=" * 60)
        print("SUCCESS - DEMO DATA SEEDED")
        print("=" * 60)
        print(f"\n  Users: {len(USER_DEFINITIONS)}")
        print(f"    - Admin: 1 (Alex Admin)")
        print(f"    - Staff: 4 (Sam, Eli, Claire, Casey)")
        print(f"\n  Patients: {attendance_count + eligibility_count + green_count}")
        print(f"    - Attendance Factor: {attendance_count}")
        print(f"    - Eligibility Factor: {eligibility_count}")
        print(f"    - Green/Resolved: {green_count}")
        print("\n  Data Layers:")
        print("    L1: PaymentProbability with agentic recommendations")
        print("    L2: ResolutionPlan with factor modes")
        print("    L3: PlanSteps with answer_options")
        print("    L4: Evidence linked via PlanStepFactLink")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
