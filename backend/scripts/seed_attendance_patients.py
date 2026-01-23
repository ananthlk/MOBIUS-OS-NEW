#!/usr/bin/env python3
"""
Seed 3 Attendance Factor patients with L3/L4 structure.

Patient Archetypes:
1. Maria Gonzalez - Fully automatable (all Mobius)
2. James Walker - Automation with review (Mobius + some user)
3. Tanya Brooks - Human-led, system-supported (all user)

L3 Categories (5 steps per patient):
- Understanding the Patient's Visit
- Helping the Patient Stay on Track
- Assessing Clinical Readiness
- Reducing Attendance Risks
- Creating a Backup Plan

L4 Facts: Evidence records linked via PlanStepFactLink
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
# ATTENDANCE L3 STEPS DEFINITION
# =============================================================================

ATTENDANCE_L3_STEPS = [
    # L3 Category 1: Understanding the Patient's Visit
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
    # L3 Category 2: Helping the Patient Stay on Track
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
    # L3 Category 3: Assessing Clinical Readiness
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
    # L3 Category 4: Reducing Attendance Risks
    {
        "step_order": 4,
        "step_code": "reducing_risks",
        "step_type": StepType.QUESTION,
        "input_type": InputType.MULTI_CHOICE,  # Can select multiple barriers
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
    # L3 Category 5: Creating a Backup Plan
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
# L4 EVIDENCE LIBRARY
# =============================================================================

L4_EVIDENCE = {
    # Understanding Visit - New Visit
    "no_prior_visits": {
        "fact_type": "visit_history",
        "fact_summary": "No prior completed visits for this service or clinic",
        "fact_data": {"visit_count": 0, "is_new_patient": True},
        "impact_direction": "neutral",
        "impact_weight": 0.3,
    },
    "first_visit_after_gap": {
        "fact_type": "visit_history",
        "fact_summary": "First visit after long gap (6+ months)",
        "fact_data": {"months_since_last": 8, "gap_threshold": 6},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "limited_attendance_history": {
        "fact_type": "attendance_history",
        "fact_summary": "Limited attendance history available",
        "fact_data": {"data_points": 1, "confidence": "low"},
        "impact_direction": "neutral",
        "impact_weight": 0.2,
    },
    "intake_incomplete": {
        "fact_type": "documentation",
        "fact_summary": "Intake or documentation not previously completed",
        "fact_data": {"intake_complete": False, "forms_pending": ["consent", "history"]},
        "impact_direction": "negative",
        "impact_weight": 0.3,
    },
    
    # Understanding Visit - Standard Visit
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
    "no_new_complexity": {
        "fact_type": "clinical",
        "fact_summary": "No new complexity identified",
        "fact_data": {"complexity_flags": [], "risk_score": "low"},
        "impact_direction": "positive",
        "impact_weight": 0.3,
    },
    
    # Understanding Visit - High-Risk Visit
    "recent_noshow_history": {
        "fact_type": "attendance_history",
        "fact_summary": "Recent no-show or late cancellation history",
        "fact_data": {"noshow_count_6mo": 3, "late_cancel_count_6mo": 2},
        "impact_direction": "negative",
        "impact_weight": 0.6,
    },
    "long_gap_since_visit": {
        "fact_type": "visit_history",
        "fact_summary": "Long gap since last successful visit (4+ months)",
        "fact_data": {"months_since_last": 4, "last_visit_date": "2025-09-15"},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "high_complexity": {
        "fact_type": "clinical",
        "fact_summary": "High medical, behavioral, or administrative complexity",
        "fact_data": {"complexity_score": "high", "flags": ["behavioral", "administrative"]},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "prior_logistics_friction": {
        "fact_type": "logistics",
        "fact_summary": "Prior payer or logistics friction documented",
        "fact_data": {"transport_issues": True, "payer_issues": False},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "care_team_risk_flag": {
        "fact_type": "clinical",
        "fact_summary": "Care team–initiated risk flag",
        "fact_data": {"flagged_by": "case_manager", "flag_date": "2026-01-15"},
        "impact_direction": "negative",
        "impact_weight": 0.6,
    },
    
    # Staying on Track - Standard Outreach
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
    "no_channel_preferences": {
        "fact_type": "preferences",
        "fact_summary": "No stated channel or timing preferences",
        "fact_data": {"has_preferences": False},
        "impact_direction": "neutral",
        "impact_weight": 0.1,
    },
    
    # Staying on Track - Tailored Outreach
    "stated_preferences": {
        "fact_type": "preferences",
        "fact_summary": "Patient-stated communication preferences",
        "fact_data": {"preferred_channel": "sms", "preferred_time": "after_5pm", "cadence": "2_days_before"},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "delayed_responsiveness": {
        "fact_type": "outreach_history",
        "fact_summary": "Prior delayed but eventual responsiveness",
        "fact_data": {"avg_response_time_hours": 48, "eventual_response_rate": 0.85},
        "impact_direction": "neutral",
        "impact_weight": 0.3,
    },
    "earlier_reminders_needed": {
        "fact_type": "outreach_history",
        "fact_summary": "Complexity requires earlier reminders",
        "fact_data": {"recommended_lead_time_days": 5},
        "impact_direction": "neutral",
        "impact_weight": 0.2,
    },
    
    # Staying on Track - Personalized Outreach
    "poor_automated_response": {
        "fact_type": "outreach_history",
        "fact_summary": "Poor response to automated outreach historically",
        "fact_data": {"automated_response_rate": 0.20, "attempts": 8},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "clinical_vulnerability": {
        "fact_type": "clinical",
        "fact_summary": "Clinical vulnerability noted",
        "fact_data": {"vulnerability_type": "mental_health", "notes": "Requires relationship-based outreach"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "care_team_outreach_request": {
        "fact_type": "clinical",
        "fact_summary": "Care team requests direct outreach",
        "fact_data": {"requested_by": "clinician", "reason": "relationship_matters"},
        "impact_direction": "neutral",
        "impact_weight": 0.5,
    },
    
    # Staying on Track - Re-establish Contact
    "invalid_contact_info": {
        "fact_type": "contact",
        "fact_summary": "Missing, invalid, or conflicting contact information",
        "fact_data": {"phone_valid": False, "email_valid": False, "issues": ["disconnected", "bounced"]},
        "impact_direction": "negative",
        "impact_weight": 0.6,
    },
    "no_response_after_attempts": {
        "fact_type": "outreach_history",
        "fact_summary": "No response after defined automated attempts",
        "fact_data": {"attempts": 5, "last_attempt_date": "2026-01-10"},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    
    # Clinical Readiness - Clinically Stable
    "no_crisis_indicators": {
        "fact_type": "clinical",
        "fact_summary": "No recent crisis indicators",
        "fact_data": {"crisis_flags": [], "last_assessment": "2026-01-01"},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "no_care_team_alerts": {
        "fact_type": "clinical",
        "fact_summary": "No care team alerts",
        "fact_data": {"active_alerts": 0},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "coherent_communications": {
        "fact_type": "communication",
        "fact_summary": "Patient communications coherent and consistent",
        "fact_data": {"communication_quality": "good", "tone": "stable"},
        "impact_direction": "positive",
        "impact_weight": 0.3,
    },
    "no_recent_ed_events": {
        "fact_type": "clinical",
        "fact_summary": "No recent ED/IP events",
        "fact_data": {"ed_visits_90d": 0, "ip_admits_90d": 0},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    
    # Clinical Readiness - Possible Decompensation
    "missed_recent_appointments": {
        "fact_type": "attendance_history",
        "fact_summary": "Missed recent appointments",
        "fact_data": {"missed_count_30d": 2, "pattern": "increasing"},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "communication_tone_change": {
        "fact_type": "communication",
        "fact_summary": "Sudden change in communication tone or behavior",
        "fact_data": {"tone_change": "withdrawn", "detected_date": "2026-01-18"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "medication_change": {
        "fact_type": "clinical",
        "fact_summary": "Recent medication change requiring monitoring",
        "fact_data": {"medication": "antidepressant", "change_type": "new", "date": "2026-01-10"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "missed_intake_steps": {
        "fact_type": "documentation",
        "fact_summary": "Missed intake steps",
        "fact_data": {"pending_steps": ["initial_assessment", "care_plan_review"]},
        "impact_direction": "negative",
        "impact_weight": 0.3,
    },
    
    # Reducing Risks - Transportation
    "no_ride_available": {
        "fact_type": "logistics",
        "fact_summary": "No ride available",
        "fact_data": {"has_transport": False, "barrier_type": "transportation"},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "missed_prior_rides": {
        "fact_type": "logistics",
        "fact_summary": "Missed prior rides / transport issues",
        "fact_data": {"missed_rides": 2, "last_issue": "2025-11-20"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "distance_constraints": {
        "fact_type": "logistics",
        "fact_summary": "Distance or timing constraints",
        "fact_data": {"distance_miles": 25, "location": "rural"},
        "impact_direction": "negative",
        "impact_weight": 0.3,
    },
    
    # Reducing Risks - Scheduling Conflict
    "work_schedule_conflict": {
        "fact_type": "scheduling",
        "fact_summary": "Variable work schedule creates conflicts",
        "fact_data": {"work_type": "shift_work", "schedule": "variable"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    
    # Reducing Risks - Readiness/Anxiety
    "expressed_hesitation": {
        "fact_type": "behavioral",
        "fact_summary": "Expressed hesitation or avoidance",
        "fact_data": {"hesitation_type": "anxiety", "noted_date": "2026-01-12"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "prior_disengagement": {
        "fact_type": "behavioral",
        "fact_summary": "Prior disengagement patterns",
        "fact_data": {"disengagement_episodes": 2, "pattern": "avoidance"},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    
    # Reducing Risks - No Barriers
    "no_barriers_identified": {
        "fact_type": "logistics",
        "fact_summary": "No unresolved barriers on record",
        "fact_data": {"barriers": [], "last_check": "2026-01-20"},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    
    # Backup Plan - Proceed as Scheduled
    "high_attendance_likelihood": {
        "fact_type": "prediction",
        "fact_summary": "Attendance likelihood high",
        "fact_data": {"predicted_attendance": 0.92, "confidence": 0.85},
        "impact_direction": "positive",
        "impact_weight": 0.5,
    },
    "stable_outreach_signals": {
        "fact_type": "outreach_history",
        "fact_summary": "Stable outreach and readiness signals",
        "fact_data": {"confirmation_received": True, "engagement_score": "high"},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    
    # Backup Plan - Increased Confirmation
    "moderate_attendance_risk": {
        "fact_type": "prediction",
        "fact_summary": "Moderate attendance risk identified",
        "fact_data": {"predicted_attendance": 0.65, "risk_level": "moderate"},
        "impact_direction": "negative",
        "impact_weight": 0.4,
    },
    "barriers_manageable": {
        "fact_type": "logistics",
        "fact_summary": "Barriers identified but manageable",
        "fact_data": {"barrier_status": "manageable", "mitigation_plan": "in_progress"},
        "impact_direction": "neutral",
        "impact_weight": 0.3,
    },
    
    # Backup Plan - Modality Shift
    "in_person_unlikely": {
        "fact_type": "prediction",
        "fact_summary": "In-person attendance unlikely",
        "fact_data": {"in_person_likelihood": 0.30, "barriers": ["transportation", "anxiety"]},
        "impact_direction": "negative",
        "impact_weight": 0.5,
    },
    "telehealth_acceptable": {
        "fact_type": "clinical",
        "fact_summary": "Telehealth clinically acceptable",
        "fact_data": {"telehealth_appropriate": True, "clinical_approval": True},
        "impact_direction": "positive",
        "impact_weight": 0.4,
    },
    "patient_telehealth_access": {
        "fact_type": "technology",
        "fact_summary": "Patient has telehealth access and consent",
        "fact_data": {"has_device": True, "has_internet": True, "consent_on_file": True},
        "impact_direction": "positive",
        "impact_weight": 0.3,
    },
}


# =============================================================================
# PATIENT PROFILES
# =============================================================================

PATIENT_PROFILES = {
    "maria": {
        "name": "Maria Gonzalez",
        "mrn_suffix": "MARIA01",
        "profile": "Established, stable, predictable",
        "theme": "Fully automatable",
        "probability": {
            "overall": 0.92,
            "attendance": 0.95,
            "eligibility": 0.90,
            "coverage": 0.92,
            "errors": 0.94,
        },
        "steps": [
            {"code": "understanding_visit", "answer": "standard_visit", "assignee": "mobius", "status": "current"},
            {"code": "staying_on_track", "answer": "standard_outreach", "assignee": "mobius", "status": "pending"},
            {"code": "clinical_readiness", "answer": "clinically_stable", "assignee": "mobius", "status": "pending"},
            {"code": "reducing_risks", "answer": "no_barriers", "assignee": "mobius", "status": "pending"},
            {"code": "backup_plan", "answer": "proceed_scheduled", "assignee": "mobius", "status": "pending"},
        ],
        "evidence": {
            "understanding_visit": ["prior_completed_visits", "stable_attendance_history", "no_recent_noshow", "no_new_complexity"],
            "staying_on_track": ["valid_contact_info", "prior_responsiveness"],
            "clinical_readiness": ["no_crisis_indicators", "no_care_team_alerts", "no_recent_ed_events"],
            "reducing_risks": ["no_barriers_identified"],
            "backup_plan": ["high_attendance_likelihood", "stable_outreach_signals"],
        },
    },
    "james": {
        "name": "James Walker",
        "mrn_suffix": "JAMES01",
        "profile": "New, complex, but reachable",
        "theme": "Automation with review",
        "probability": {
            "overall": 0.72,
            "attendance": 0.68,
            "eligibility": 0.85,
            "coverage": 0.80,
            "errors": 0.88,
        },
        "steps": [
            {"code": "understanding_visit", "answer": "new_visit", "assignee": "mobius", "status": "current"},
            {"code": "staying_on_track", "answer": "tailored_outreach", "assignee": "mobius", "status": "pending"},
            {"code": "clinical_readiness", "answer": "possible_decompensation", "assignee": "user", "status": "pending"},
            {"code": "reducing_risks", "answer": "scheduling_conflict", "assignee": "user", "status": "pending"},
            {"code": "backup_plan", "answer": "increased_confirmation", "assignee": "mobius", "status": "pending"},
        ],
        "evidence": {
            "understanding_visit": ["no_prior_visits", "limited_attendance_history"],
            "staying_on_track": ["stated_preferences", "delayed_responsiveness"],
            "clinical_readiness": ["medication_change", "missed_intake_steps"],
            "reducing_risks": ["work_schedule_conflict"],
            "backup_plan": ["moderate_attendance_risk", "barriers_manageable"],
        },
    },
    "tanya": {
        "name": "Tanya Brooks",
        "mrn_suffix": "TANYA01",
        "profile": "High-risk, disengaging, safety-sensitive",
        "theme": "Human-led, system-supported",
        "probability": {
            "overall": 0.45,
            "attendance": 0.35,
            "eligibility": 0.88,
            "coverage": 0.85,
            "errors": 0.90,
        },
        "steps": [
            {"code": "understanding_visit", "answer": "high_risk_visit", "assignee": "user", "status": "current"},
            {"code": "staying_on_track", "answer": "personalized_outreach", "assignee": "user", "status": "pending"},
            {"code": "clinical_readiness", "answer": "possible_decompensation", "assignee": "user", "status": "pending"},
            {"code": "reducing_risks", "answer": ["transportation", "readiness_anxiety"], "assignee": "user", "status": "pending"},
            {"code": "backup_plan", "answer": "modality_shift", "assignee": "user", "status": "pending"},
        ],
        "evidence": {
            "understanding_visit": ["recent_noshow_history", "long_gap_since_visit", "high_complexity", "care_team_risk_flag"],
            "staying_on_track": ["poor_automated_response", "clinical_vulnerability", "care_team_outreach_request"],
            "clinical_readiness": ["missed_recent_appointments", "communication_tone_change"],
            "reducing_risks": ["no_ride_available", "missed_prior_rides", "expressed_hesitation", "prior_disengagement"],
            "backup_plan": ["in_person_unlikely", "telehealth_acceptable", "patient_telehealth_access"],
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
    """Create a patient with full L3/L4 data."""
    profile = PATIENT_PROFILES[profile_key]
    
    print(f"\n--- Creating Patient: {profile['name']} ---")
    print(f"    Profile: {profile['profile']}")
    print(f"    Theme: {profile['theme']}")
    
    # Create patient context
    patient = PatientContext(
        tenant_id=tenant_id,
        patient_key=f"attend_{profile_key}_{uuid.uuid4().hex[:6]}",
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
        lowest_factor="attendance",
        lowest_factor_reason=f"Attendance assessment: {profile['theme']}",
        problem_statement=f"Preparing {profile['name'].split()[0]} for their visit",
        batch_job_id="seed_attendance_patients",
    )
    db.add(prob)
    db.flush()
    
    print(f"    ✓ PaymentProbability: overall={prob_data['overall']}, attendance={prob_data['attendance']}")
    
    # Create resolution plan (Layer 2)
    plan = ResolutionPlan(
        patient_context_id=patient.patient_context_id,
        tenant_id=tenant_id,
        gap_types=["attendance"],
        status=PlanStatus.ACTIVE,
        initial_probability=prob_data["overall"],
        current_probability=prob_data["overall"],
        target_probability=0.90,
        batch_job_id="seed_attendance_patients",
    )
    db.add(plan)
    db.flush()
    
    # Create steps (Layer 3) with evidence (Layer 4)
    step_objects = []
    current_step_id = None
    
    for step_profile in profile["steps"]:
        # Find the step definition
        step_def = next(s for s in ATTENDANCE_L3_STEPS if s["step_code"] == step_profile["code"])
        
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
        step_objects.append(step)
        
        if step_status == StepStatus.CURRENT:
            current_step_id = step.step_id
        
        # Create answer if step is answered
        if status == "answered":
            answer_value = step_profile["answer"]
            # Handle multi-choice (list) or single choice (string)
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
        
        # Create evidence (Layer 4) and link to step
        evidence_keys = profile["evidence"].get(step_profile["code"], [])
        for i, ev_key in enumerate(evidence_keys):
            if ev_key not in L4_EVIDENCE:
                print(f"    ⚠ Evidence key not found: {ev_key}")
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
            
            # Link evidence to step
            link = PlanStepFactLink(
                plan_step_id=step.step_id,
                fact_id=evidence.evidence_id,
                display_order=i,
            )
            db.add(link)
    
    db.flush()
    
    # Set current step on plan
    if current_step_id:
        plan.current_step_id = current_step_id
    
    print(f"    ✓ ResolutionPlan with {len(step_objects)} steps")
    for step in step_objects:
        assignee_icon = "🤖" if step.assignee_type == "mobius" else "👤"
        status_icon = "✓" if step.status == StepStatus.ANSWERED else ("►" if step.status == StepStatus.CURRENT else "○")
        print(f"      {status_icon} {step.step_code} [{assignee_icon} {step.assignee_type}]")
    
    return patient


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("SEEDING ATTENDANCE PATIENTS WITH L3/L4 STRUCTURE")
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
        
        # Create all 3 patients
        patients = []
        for profile_key in ["maria", "james", "tanya"]:
            patient = create_patient(db, tenant.tenant_id, profile_key)
            patients.append(patient)
        
        db.commit()
        
        print("\n" + "=" * 70)
        print("SUCCESS! Created 3 attendance patients:")
        print("=" * 70)
        for i, (key, profile) in enumerate(PATIENT_PROFILES.items()):
            print(f"\n  {i+1}. {profile['name']}")
            print(f"     Profile: {profile['profile']}")
            print(f"     Theme: {profile['theme']}")
        
        print("\n" + "=" * 70)
        print("To verify, open Sidecar and navigate to each patient.")
        print("=" * 70)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
