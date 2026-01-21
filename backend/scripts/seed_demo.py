#!/usr/bin/env python3
"""
DEMO SEED SCRIPT - Executive Demo Ready
========================================

Creates a clean, predictable demo environment with:
- 5 demo users with clear role-based names
- 50 demo patients with scenario-based naming
- Resolution plans matched to user roles

RE-RUN ANYTIME: python scripts/seed_demo.py

This script CLEARS existing demo data and creates fresh data.
"""

import sys
import os
import uuid
import hashlib
from datetime import datetime, date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models import (
    Tenant,
    AppUser,
    Role,
    PatientContext,
    PatientSnapshot,
)
from app.models.patient_ids import PatientId
from app.models.mock_emr import MockEmrRecord
from app.models.resolution import (
    ResolutionPlan,
    PlanStep,
    StepAnswer,
    PlanNote,
    PlanModification,
    PlanStatus,
    StepStatus,
    StepType,
    InputType,
    FactorType,
    AnswerMode,
)
from app.models.activity import Activity, UserActivity
from app.models.probability import UserPreference, TaskInstance, TaskTemplate, PaymentProbability
from app.models.event_log import EventLog
from app.models.user_issue import UserReportedIssue
from app.services.auth_service import AuthService

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEMO_PASSWORD = "demo1234"

# =============================================================================
# DEMO USERS - Clear role-based naming
# =============================================================================

DEMO_USERS = [
    {
        "email": "admin@demo.clinic",
        "display_name": "Alex Admin",
        "first_name": "Alex",
        "preferred_name": "Alex",
        "activities": [
            "verify_eligibility", "check_in_patients", "schedule_appointments",
            "submit_claims", "rework_denials", "prior_authorization",
            "patient_collections", "post_payments", "patient_outreach",
            "document_notes", "coordinate_referrals"
        ],
        "preferences": {
            "tone": "professional",
            "greeting_enabled": True,
            "ai_experience_level": "regular",
            "autonomy_routine_tasks": "automatic",
            "autonomy_sensitive_tasks": "confirm_first",
        },
        "description": "Admin - sees ALL tasks"
    },
    {
        "email": "scheduler@demo.clinic",
        "display_name": "Sam Scheduler",
        "first_name": "Sam",
        "preferred_name": "Sam",
        "activities": ["schedule_appointments", "check_in_patients", "patient_outreach"],
        "preferences": {
            "tone": "friendly",
            "greeting_enabled": True,
            "ai_experience_level": "beginner",
            "autonomy_routine_tasks": "confirm_first",
            "autonomy_sensitive_tasks": "manual",
        },
        "description": "Front Desk - scheduling, check-in, outreach"
    },
    {
        "email": "eligibility@demo.clinic",
        "display_name": "Eli Eligibility",
        "first_name": "Eli",
        "preferred_name": "Eli",
        "activities": ["verify_eligibility", "check_in_patients"],
        "preferences": {
            "tone": "professional",
            "greeting_enabled": True,
            "ai_experience_level": "regular",
            "autonomy_routine_tasks": "automatic",
            "autonomy_sensitive_tasks": "confirm_first",
        },
        "description": "Eligibility Specialist - insurance verification"
    },
    {
        "email": "claims@demo.clinic",
        "display_name": "Claire Claims",
        "first_name": "Claire",
        "preferred_name": "Claire",
        "activities": ["submit_claims", "rework_denials", "post_payments", "patient_collections"],
        "preferences": {
            "tone": "professional",
            "greeting_enabled": True,
            "ai_experience_level": "regular",
            "autonomy_routine_tasks": "automatic",
            "autonomy_sensitive_tasks": "confirm_first",
        },
        "description": "Claims Specialist - billing, denials, collections"
    },
    {
        "email": "clinical@demo.clinic",
        "display_name": "Dr. Casey Clinical",
        "first_name": "Casey",
        "preferred_name": "Dr. Casey",
        "activities": ["prior_authorization", "document_notes", "coordinate_referrals"],
        "preferences": {
            "tone": "concise",
            "greeting_enabled": False,
            "ai_experience_level": "regular",
            "autonomy_routine_tasks": "automatic",
            "autonomy_sensitive_tasks": "confirm_first",
        },
        "description": "Clinical Staff - prior auth, documentation, referrals"
    },
]

# =============================================================================
# DEMO PATIENTS - Scenario-based naming
# =============================================================================

# Patient scenarios with predictable outcomes
PATIENT_SCENARIOS = [
    # ELIGIBILITY ISSUES (10 patients) - For Eli
    {"scenario": "Eligibility Gap", "name": "Maria Santos", "gap_type": "eligibility", "status": "active"},
    {"scenario": "Insurance Expired", "name": "Robert Kim", "gap_type": "eligibility", "status": "active"},
    {"scenario": "Missing Insurance Card", "name": "Jennifer Lee", "gap_type": "eligibility", "status": "active"},
    {"scenario": "Unverified Coverage", "name": "David Chen", "gap_type": "eligibility", "status": "active"},
    {"scenario": "New Patient Eligibility", "name": "Amanda Foster", "gap_type": "eligibility", "status": "active"},
    {"scenario": "Policy Changed", "name": "Thomas Wright", "gap_type": "eligibility", "status": "active"},
    {"scenario": "Secondary Insurance Check", "name": "Lisa Martinez", "gap_type": "eligibility", "status": "active"},
    {"scenario": "Eligibility Verified", "name": "Kevin O'Brien", "gap_type": "eligibility", "status": "resolved"},
    {"scenario": "Coverage Confirmed", "name": "Sarah Thompson", "gap_type": "eligibility", "status": "resolved"},
    {"scenario": "Insurance Updated", "name": "Michael Brown", "gap_type": "eligibility", "status": "resolved"},
    
    # SCHEDULING/ATTENDANCE ISSUES (10 patients) - For Sam
    {"scenario": "Confirm Appointment", "name": "Emily Davis", "gap_type": "attendance", "status": "active"},
    {"scenario": "Transportation Needed", "name": "James Wilson", "gap_type": "attendance", "status": "active"},
    {"scenario": "Reschedule Required", "name": "Patricia Garcia", "gap_type": "attendance", "status": "active"},
    {"scenario": "No Show Risk", "name": "Christopher Taylor", "gap_type": "attendance", "status": "active"},
    {"scenario": "Reminder Needed", "name": "Elizabeth Anderson", "gap_type": "attendance", "status": "active"},
    {"scenario": "Time Conflict", "name": "Daniel Jackson", "gap_type": "attendance", "status": "active"},
    {"scenario": "Follow-up Due", "name": "Michelle White", "gap_type": "attendance", "status": "active"},
    {"scenario": "Appointment Confirmed", "name": "Steven Harris", "gap_type": "attendance", "status": "resolved"},
    {"scenario": "Transport Arranged", "name": "Nancy Martin", "gap_type": "attendance", "status": "resolved"},
    {"scenario": "Rescheduled Complete", "name": "Mark Robinson", "gap_type": "attendance", "status": "resolved"},
    
    # PRIOR AUTH/COVERAGE ISSUES (10 patients) - For Dr. Casey
    {"scenario": "Prior Auth Required", "name": "Karen Lewis", "gap_type": "coverage", "status": "active"},
    {"scenario": "Auth Pending Review", "name": "Brian Walker", "gap_type": "coverage", "status": "active"},
    {"scenario": "Documentation Needed", "name": "Susan Hall", "gap_type": "coverage", "status": "active"},
    {"scenario": "Auth Denied - Appeal", "name": "Richard Allen", "gap_type": "coverage", "status": "active"},
    {"scenario": "Service Not Covered", "name": "Dorothy Young", "gap_type": "coverage", "status": "active"},
    {"scenario": "Peer Review Required", "name": "Charles King", "gap_type": "coverage", "status": "active"},
    {"scenario": "Auth Expiring Soon", "name": "Betty Scott", "gap_type": "coverage", "status": "active"},
    {"scenario": "Auth Approved", "name": "Joseph Green", "gap_type": "coverage", "status": "resolved"},
    {"scenario": "Coverage Verified", "name": "Margaret Adams", "gap_type": "coverage", "status": "resolved"},
    {"scenario": "Auth Complete", "name": "George Baker", "gap_type": "coverage", "status": "resolved"},
    
    # ALL CLEAR - No Issues (10 patients) - Green for everyone
    {"scenario": "All Clear", "name": "Helen Nelson", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Frank Carter", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Ruth Mitchell", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Paul Perez", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Anna Roberts", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Edward Turner", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Gloria Phillips", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Raymond Campbell", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Deborah Parker", "gap_type": None, "status": "resolved"},
    {"scenario": "All Clear", "name": "Larry Evans", "gap_type": None, "status": "resolved"},
    
    # MIXED/COMPLEX SCENARIOS (10 patients) - Multiple issues
    {"scenario": "Eligibility + Attendance", "name": "Virginia Edwards", "gap_type": "multi_elig_attend", "status": "active"},
    {"scenario": "Eligibility + Auth", "name": "Jeffrey Collins", "gap_type": "multi_elig_auth", "status": "active"},
    {"scenario": "Full Workflow Demo", "name": "Carolyn Stewart", "gap_type": "multi_all", "status": "active"},
    {"scenario": "Auth + Attendance", "name": "Dennis Sanchez", "gap_type": "multi_auth_attend", "status": "active"},
    {"scenario": "Complex Case", "name": "Janet Morris", "gap_type": "multi_all", "status": "active"},
    {"scenario": "Multi-Step Resolution", "name": "Gregory Rogers", "gap_type": "multi_elig_auth", "status": "active"},
    {"scenario": "Workflow Complete", "name": "Catherine Reed", "gap_type": "multi_all", "status": "resolved"},
    {"scenario": "Complex Resolved", "name": "Henry Cook", "gap_type": "multi_elig_attend", "status": "resolved"},
    {"scenario": "Multi-Issue Cleared", "name": "Diane Morgan", "gap_type": "multi_auth_attend", "status": "resolved"},
    {"scenario": "Full Review Done", "name": "Peter Bell", "gap_type": "multi_all", "status": "resolved"},
]

# =============================================================================
# STEP TEMPLATES - Properly assigned to activities
# =============================================================================

ELIGIBILITY_STEPS = [
    {
        "step_code": "check_insurance_card",
        "question_text": "Is insurance card on file?",
        "step_type": StepType.CONFIRMATION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.ELIGIBILITY,
        "assignable_activities": ["verify_eligibility", "check_in_patients"],
        "answer_options": [
            {"code": "yes", "label": "Yes - Card on file"},
            {"code": "no", "label": "No - Need to collect"},
        ],
    },
    {
        "step_code": "verify_active_coverage",
        "question_text": "Is coverage currently active?",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.ELIGIBILITY,
        "assignable_activities": ["verify_eligibility"],
        "answer_options": [
            {"code": "active", "label": "Yes - Active coverage"},
            {"code": "expired", "label": "No - Coverage expired"},
            {"code": "pending", "label": "Pending verification"},
        ],
    },
    {
        "step_code": "confirm_benefits",
        "question_text": "Are benefits confirmed for this visit type?",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.ELIGIBILITY,
        "assignable_activities": ["verify_eligibility"],
        "answer_options": [
            {"code": "confirmed", "label": "Yes - Benefits confirmed"},
            {"code": "not_covered", "label": "No - Not covered"},
            {"code": "check_payer", "label": "Need to verify with payer"},
        ],
    },
]

ATTENDANCE_STEPS = [
    {
        "step_code": "confirm_appointment",
        "question_text": "Has patient confirmed their appointment?",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.ATTENDANCE,
        "assignable_activities": ["schedule_appointments", "patient_outreach"],
        "answer_options": [
            {"code": "confirmed", "label": "Yes - Confirmed"},
            {"code": "no_response", "label": "No response yet"},
            {"code": "needs_reschedule", "label": "Needs to reschedule"},
        ],
    },
    {
        "step_code": "check_transportation",
        "question_text": "Does patient have transportation?",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.ATTENDANCE,
        "assignable_activities": ["schedule_appointments", "patient_outreach"],
        "answer_options": [
            {"code": "yes", "label": "Yes - Has transportation"},
            {"code": "needs_help", "label": "No - Needs assistance"},
            {"code": "unknown", "label": "Unknown - Need to ask"},
        ],
    },
    {
        "step_code": "send_reminder",
        "question_text": "Send appointment reminder?",
        "step_type": StepType.ACTION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.ATTENDANCE,
        "assignable_activities": ["schedule_appointments"],
        "answer_options": [
            {"code": "send_sms", "label": "Send SMS reminder"},
            {"code": "send_email", "label": "Send email reminder"},
            {"code": "call", "label": "Call patient"},
            {"code": "skip", "label": "Already contacted"},
        ],
    },
]

COVERAGE_STEPS = [
    {
        "step_code": "check_auth_required",
        "question_text": "Is prior authorization required?",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.COVERAGE,
        "assignable_activities": ["prior_authorization"],  # ONLY prior auth specialists
        "answer_options": [
            {"code": "yes", "label": "Yes - Auth required"},
            {"code": "no", "label": "No - Not required"},
            {"code": "check", "label": "Need to verify"},
        ],
    },
    {
        "step_code": "check_documentation",
        "question_text": "Is clinical documentation sufficient?",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.COVERAGE,
        "assignable_activities": ["prior_authorization", "document_notes"],
        "answer_options": [
            {"code": "sufficient", "label": "Yes - Documentation complete"},
            {"code": "partial", "label": "Partial - Need more details"},
            {"code": "missing", "label": "No - Documentation missing"},
        ],
    },
    {
        "step_code": "submit_auth",
        "question_text": "Submit authorization request?",
        "step_type": StepType.ACTION,
        "input_type": InputType.SINGLE_CHOICE,
        "factor_type": FactorType.COVERAGE,
        "assignable_activities": ["prior_authorization"],
        "answer_options": [
            {"code": "submit", "label": "Submit to payer"},
            {"code": "manual", "label": "Submit manually"},
            {"code": "hold", "label": "Hold - need more info"},
        ],
    },
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def generate_mrn(index: int) -> str:
    """Generate a demo MRN."""
    return f"DEMO-{10000 + index:05d}"

def generate_dob(index: int) -> date:
    """Generate a realistic DOB."""
    base_year = 1950 + (index % 50)
    month = (index % 12) + 1
    day = (index % 28) + 1
    return date(base_year, month, day)

def get_blood_type(index: int) -> str:
    """Get a blood type."""
    types = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    return types[index % len(types)]


# =============================================================================
# SEEDING FUNCTIONS
# =============================================================================

def clear_demo_data(session):
    """Clear all existing demo data using TRUNCATE CASCADE."""
    print("\n1. Clearing existing data...")
    
    # Use raw SQL with TRUNCATE CASCADE to handle all FK constraints
    tables_to_clear = [
        # Resolution plan tables
        "step_answer",
        "plan_note",
        "plan_modification",
        "plan_step",
        "resolution_plan",
        # Task tables
        "task_instance",
        # Probability tables
        "payment_probability",
        # Event/issue tables
        "event_log",
        "user_reported_issue",
        "system_response",
        "mini_submission",
        # Patient tables
        "mock_emr",
        "patient_ids",
        "patient_snapshot",
        "patient_context",
        # User tables (careful - keep activities and roles)
        "user_activity",
        "user_preference",
        "user_session",
        "app_user",
    ]
    
    from sqlalchemy import text
    
    for table in tables_to_clear:
        try:
            session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        except Exception as e:
            # Table might not exist, that's OK
            print(f"   (skipped {table}: {e})")
            session.rollback()
    
    session.commit()
    print("   Cleared all demo data.")


def seed_activities(session):
    """Ensure all activities exist."""
    print("\n2. Ensuring activities exist...")
    
    activities_data = [
        {"activity_code": "verify_eligibility", "label": "Verify Eligibility", "description": "Check patient insurance coverage", "display_order": 1},
        {"activity_code": "check_in_patients", "label": "Check In Patients", "description": "Patient check-in and registration", "display_order": 2},
        {"activity_code": "schedule_appointments", "label": "Schedule Appointments", "description": "Schedule and manage appointments", "display_order": 3},
        {"activity_code": "submit_claims", "label": "Submit Claims", "description": "Submit insurance claims", "display_order": 4},
        {"activity_code": "rework_denials", "label": "Rework Denials", "description": "Appeal denied claims", "display_order": 5},
        {"activity_code": "prior_authorization", "label": "Prior Authorization", "description": "Handle prior auth requests", "display_order": 6},
        {"activity_code": "patient_collections", "label": "Patient Collections", "description": "Manage patient balances", "display_order": 7},
        {"activity_code": "post_payments", "label": "Post Payments", "description": "Post payments to accounts", "display_order": 8},
        {"activity_code": "patient_outreach", "label": "Patient Outreach", "description": "Contact patients for follow-up", "display_order": 9},
        {"activity_code": "document_notes", "label": "Document Notes", "description": "Clinical documentation", "display_order": 10},
        {"activity_code": "coordinate_referrals", "label": "Coordinate Referrals", "description": "Manage patient referrals", "display_order": 11},
    ]
    
    for act_data in activities_data:
        existing = session.query(Activity).filter(
            Activity.activity_code == act_data["activity_code"]
        ).first()
        
        if not existing:
            activity = Activity(**act_data)
            session.add(activity)
    
    session.commit()
    print(f"   Ensured {len(activities_data)} activities exist.")


def seed_demo_users(session, tenant_id):
    """Create demo users with role-based activities."""
    print("\n3. Creating demo users...")
    
    auth_service = AuthService()
    
    # Get or create default role
    default_role = session.query(Role).filter(Role.name == "User").first()
    if not default_role:
        default_role = Role(
            name="User",
        )
        session.add(default_role)
        session.commit()
    
    created_users = []
    for user_data in DEMO_USERS:
        # Create user
        user = AppUser(
            tenant_id=tenant_id,
            email=user_data["email"],
            display_name=user_data["display_name"],
            first_name=user_data["first_name"],
            preferred_name=user_data["preferred_name"],
            timezone="America/New_York",
            password_hash=auth_service.hash_password(DEMO_PASSWORD),
            onboarding_completed_at=datetime.utcnow(),  # This sets is_onboarded=True
        )
        session.add(user)
        session.flush()
        
        # Add preferences
        prefs = user_data["preferences"]
        preference = UserPreference(
            user_id=user.user_id,
            tone=prefs["tone"],
            greeting_enabled=prefs["greeting_enabled"],
            ai_experience_level=prefs["ai_experience_level"],
            autonomy_routine_tasks=prefs["autonomy_routine_tasks"],
            autonomy_sensitive_tasks=prefs["autonomy_sensitive_tasks"],
        )
        session.add(preference)
        
        # Add activities
        for i, activity_code in enumerate(user_data["activities"]):
            activity = session.query(Activity).filter(
                Activity.activity_code == activity_code
            ).first()
            if activity:
                user_activity = UserActivity(
                    user_id=user.user_id,
                    activity_id=activity.activity_id,
                    is_primary=(i == 0),
                )
                session.add(user_activity)
        
        created_users.append(user)
        print(f"   + {user_data['display_name']} ({user_data['email']}) - {user_data['description']}")
    
    session.commit()
    return created_users


def seed_demo_patients(session, tenant_id):
    """Create demo patients with scenario-based names."""
    print("\n4. Creating demo patients...")
    
    created_patients = []
    for i, scenario in enumerate(PATIENT_SCENARIOS):
        # Create patient key and display name
        patient_key = f"demo_{i+1:03d}"
        display_name = f"Demo - {scenario['scenario']} - {scenario['name']}"
        mrn = generate_mrn(i)
        dob = generate_dob(i)
        
        # Create PatientContext
        context = PatientContext(
            tenant_id=tenant_id,
            patient_key=patient_key,
        )
        session.add(context)
        session.flush()
        
        # Create PatientSnapshot
        snapshot = PatientSnapshot(
            patient_context_id=context.patient_context_id,
            display_name=display_name,
            id_label="MRN",
            id_masked=f"****{mrn[-4:]}",
            snapshot_version=1,
            dob=dob,
        )
        session.add(snapshot)
        
        # Create PatientId (for crosswalk/lookup) - use lowercase 'mrn' to match queries
        patient_id_rec = PatientId(
            patient_context_id=context.patient_context_id,
            id_type="mrn",  # lowercase to match mock_emr.py queries
            id_value=mrn,
            source_system="demo_emr",
        )
        session.add(patient_id_rec)
        
        # Create MockEmrRecord
        emr = MockEmrRecord(
            patient_context_id=context.patient_context_id,
            allergies=["None reported"] if i % 3 == 0 else ["Penicillin"],
            medications=[{"name": "Lisinopril", "dose": "10mg", "frequency": "QD"}] if i % 2 == 0 else [],
            blood_type=get_blood_type(i),
            emergency_contact_name="Emergency Contact",
            emergency_contact_phone="555-0100",
            emergency_contact_relation="Spouse",
            vitals={
                "bp": f"{110 + (i % 30)}/{70 + (i % 20)}",
                "hr": 65 + (i % 25),
                "temp": 98.6,
                "weight_lbs": 140 + (i % 60),
            },
        )
        session.add(emr)
        
        created_patients.append({
            "context": context,
            "scenario": scenario,
            "display_name": display_name,
        })
        
        if (i + 1) % 10 == 0:
            print(f"   Created {i + 1}/{len(PATIENT_SCENARIOS)} patients...")
    
    session.commit()
    print(f"   Created {len(created_patients)} demo patients.")
    return created_patients


def get_steps_for_gap_type(gap_type: str) -> list:
    """Get appropriate steps for a gap type."""
    if gap_type == "eligibility":
        return ELIGIBILITY_STEPS[:2]  # 2 eligibility steps
    elif gap_type == "attendance":
        return ATTENDANCE_STEPS[:2]  # 2 attendance steps
    elif gap_type == "coverage":
        return COVERAGE_STEPS[:2]  # 2 coverage steps
    elif gap_type == "multi_elig_attend":
        return ELIGIBILITY_STEPS[:1] + ATTENDANCE_STEPS[:1]
    elif gap_type == "multi_elig_auth":
        return ELIGIBILITY_STEPS[:1] + COVERAGE_STEPS[:1]
    elif gap_type == "multi_auth_attend":
        return COVERAGE_STEPS[:1] + ATTENDANCE_STEPS[:1]
    elif gap_type == "multi_all":
        return ELIGIBILITY_STEPS[:1] + COVERAGE_STEPS[:1] + ATTENDANCE_STEPS[:1]
    else:
        return []


def seed_resolution_plans(session, patients, users, tenant_id):
    """Create resolution plans for demo patients."""
    print("\n5. Creating resolution plans...")
    
    user_map = {u.email: u for u in users}
    
    for patient_data in patients:
        context = patient_data["context"]
        scenario = patient_data["scenario"]
        gap_type = scenario["gap_type"]
        status = scenario["status"]
        
        # Determine gap types list
        if gap_type is None:
            gap_types = ["general"]
        elif gap_type.startswith("multi_"):
            parts = gap_type.replace("multi_", "").split("_")
            gap_types = [p.replace("elig", "eligibility").replace("auth", "coverage").replace("attend", "attendance") for p in parts]
        else:
            gap_types = [gap_type]
        
        # Create resolution plan
        plan = ResolutionPlan(
            patient_context_id=context.patient_context_id,
            tenant_id=tenant_id,
            gap_types=gap_types,
            status=PlanStatus.RESOLVED if status == "resolved" else PlanStatus.ACTIVE,
            initial_probability=0.45 if status == "active" else 0.92,
            current_probability=0.55 if status == "active" else 0.95,
            target_probability=0.85,
            batch_job_id="demo_seed_v1",
        )
        
        if status == "resolved":
            plan.resolved_at = datetime.utcnow() - timedelta(hours=2)
            plan.resolution_type = "verified_complete"
            plan.resolution_notes = f"All checks passed for {scenario['scenario']}"
        
        session.add(plan)
        session.flush()
        
        # Add steps if active
        if status == "active" and gap_type:
            steps = get_steps_for_gap_type(gap_type)
            scenario_name = scenario["scenario"]
            
            for i, step_data in enumerate(steps):
                # First step's question should match the problem_statement for Mini/Sidecar consistency
                # This ensures what Mini shows matches what Sidecar shows as the first bottleneck
                if i == 0:
                    # Generate problem statement matching PaymentProbability logic
                    action_map = {
                        "eligibility": "Verify eligibility",
                        "coverage": "Check coverage",
                        "attendance": "Confirm attendance",
                    }
                    action = action_map.get(step_data["factor_type"], "Review")
                    question_text = f"{action} - {scenario_name}"
                else:
                    question_text = step_data["question_text"]
                
                step = PlanStep(
                    plan_id=plan.plan_id,
                    step_order=i + 1,
                    step_code=step_data["step_code"],
                    step_type=step_data["step_type"],
                    input_type=step_data["input_type"],
                    question_text=question_text,
                    factor_type=step_data["factor_type"],
                    answer_options=step_data["answer_options"],
                    assignable_activities=step_data["assignable_activities"],
                    status=StepStatus.CURRENT if i == 0 else StepStatus.PENDING,
                    can_system_answer=True,
                )
                session.add(step)
                session.flush()
                
                if i == 0:
                    plan.current_step_id = step.step_id
        elif status == "resolved" and gap_type:
            # Add completed steps for resolved plans
            steps = get_steps_for_gap_type(gap_type)
            scenario_name = scenario["scenario"]
            
            for i, step_data in enumerate(steps):
                # First step's question should match the problem_statement for consistency
                if i == 0:
                    action_map = {
                        "eligibility": "Verify eligibility",
                        "coverage": "Check coverage",
                        "attendance": "Confirm attendance",
                    }
                    action = action_map.get(step_data["factor_type"], "Review")
                    question_text = f"{action} - {scenario_name}"
                else:
                    question_text = step_data["question_text"]
                
                step = PlanStep(
                    plan_id=plan.plan_id,
                    step_order=i + 1,
                    step_code=step_data["step_code"],
                    step_type=step_data["step_type"],
                    input_type=step_data["input_type"],
                    question_text=question_text,
                    factor_type=step_data["factor_type"],
                    answer_options=step_data["answer_options"],
                    assignable_activities=step_data["assignable_activities"],
                    status=StepStatus.COMPLETED,
                    completed_at=datetime.utcnow() - timedelta(hours=3),
                    can_system_answer=True,
                )
                session.add(step)
    
    session.commit()
    print(f"   Created resolution plans for {len(patients)} patients.")


def seed_payment_probabilities(session, patients, tenant_id):
    """
    Create PaymentProbability records for demo patients.
    
    Color logic:
    - GREEN: >= 85% probability (resolved, no issues)
    - YELLOW: 60-84% probability (minor issues)
    - RED: < 60% probability (complex/critical issues)
    """
    print("\n6. Creating payment probabilities...")
    
    import random
    
    for patient_data in patients:
        context = patient_data["context"]
        scenario = patient_data["scenario"]
        gap_type = scenario["gap_type"]
        status = scenario["status"]
        scenario_name = scenario["scenario"]
        
        # Determine probability based on scenario complexity
        if status == "resolved" and gap_type is None:
            # All Clear - High probability (green)
            overall_prob = random.uniform(0.92, 0.98)
            lowest_factor = None
            lowest_reason = None
            problem_statement = None
            
        elif status == "resolved":
            # Resolved with prior issues - Good probability (green)
            overall_prob = random.uniform(0.86, 0.94)
            lowest_factor = None
            lowest_reason = None
            problem_statement = None
            
        elif gap_type and gap_type.startswith("multi_"):
            # Multi-issue/Complex - Low probability (red)
            overall_prob = random.uniform(0.35, 0.52)
            lowest_factor = "eligibility"
            lowest_reason = "Multiple issues require attention"
            problem_statement = f"Complex case - {scenario_name}"
            
        elif gap_type == "eligibility":
            # Eligibility issues - Medium-low probability (yellow/red)
            overall_prob = random.uniform(0.48, 0.72)
            lowest_factor = "eligibility"
            lowest_reason = scenario_name
            problem_statement = f"Verify eligibility - {scenario_name}"
            
        elif gap_type == "attendance":
            # Attendance issues - Medium probability (yellow)
            overall_prob = random.uniform(0.62, 0.78)
            lowest_factor = "attendance"
            lowest_reason = scenario_name
            problem_statement = f"Confirm attendance - {scenario_name}"
            
        elif gap_type == "coverage":
            # Coverage/Prior Auth issues - Medium-low probability (yellow/red)
            overall_prob = random.uniform(0.45, 0.68)
            lowest_factor = "coverage"
            lowest_reason = scenario_name
            problem_statement = f"Check coverage - {scenario_name}"
            
        else:
            # Default - Medium probability
            overall_prob = random.uniform(0.70, 0.85)
            lowest_factor = None
            lowest_reason = None
            problem_statement = None
        
        # Calculate micro-probabilities based on lowest factor
        prob_eligibility = overall_prob if lowest_factor != "eligibility" else overall_prob * 0.85
        prob_coverage = overall_prob if lowest_factor != "coverage" else overall_prob * 0.88
        prob_attendance = overall_prob if lowest_factor != "attendance" else overall_prob * 0.90
        prob_no_errors = random.uniform(0.88, 0.98)  # Usually high
        
        # Confidence based on status
        confidence = 0.92 if status == "resolved" else random.uniform(0.75, 0.88)
        
        # Create PaymentProbability record
        prob_record = PaymentProbability(
            patient_context_id=context.patient_context_id,
            target_date=date.today() + timedelta(days=random.randint(1, 14)),
            overall_probability=round(overall_prob, 3),
            confidence=round(confidence, 3),
            prob_appointment_attendance=round(prob_attendance, 3),
            prob_eligibility=round(prob_eligibility, 3),
            prob_coverage=round(prob_coverage, 3),
            prob_no_errors=round(prob_no_errors, 3),
            lowest_factor=lowest_factor,
            lowest_factor_reason=lowest_reason,
            problem_statement=problem_statement,
            batch_job_id="demo_seed_v1",
        )
        session.add(prob_record)
    
    session.commit()
    
    # Summary by color
    green_count = sum(1 for p in patients if p["scenario"]["status"] == "resolved")
    yellow_count = sum(1 for p in patients 
                       if p["scenario"]["status"] == "active" 
                       and p["scenario"]["gap_type"] in ["attendance", "eligibility", "coverage"]
                       and not (p["scenario"]["gap_type"] or "").startswith("multi_"))
    red_count = sum(1 for p in patients 
                    if p["scenario"]["status"] == "active" 
                    and (p["scenario"]["gap_type"] or "").startswith("multi_"))
    
    print(f"   Created {len(patients)} payment probability records:")
    print(f"     🟢 Green (≥85%): ~{green_count} patients (resolved)")
    print(f"     🟡 Yellow (60-84%): ~{yellow_count} patients (minor issues)")
    print(f"     🔴 Red (<60%): ~{red_count} patients (complex issues)")


def print_demo_summary():
    """Print demo credentials and summary."""
    print("\n" + "=" * 60)
    print("DEMO ENVIRONMENT READY")
    print("=" * 60)
    
    print("\n📋 DEMO USERS (password: demo1234)")
    print("-" * 50)
    for user in DEMO_USERS:
        print(f"  {user['email']}")
        print(f"    Name: {user['display_name']}")
        print(f"    Role: {user['description']}")
        print()
    
    print("\n📊 PATIENT SCENARIOS")
    print("-" * 50)
    
    # Count scenarios
    active_elig = sum(1 for s in PATIENT_SCENARIOS if s["gap_type"] == "eligibility" and s["status"] == "active")
    active_attend = sum(1 for s in PATIENT_SCENARIOS if s["gap_type"] == "attendance" and s["status"] == "active")
    active_coverage = sum(1 for s in PATIENT_SCENARIOS if s["gap_type"] == "coverage" and s["status"] == "active")
    active_multi = sum(1 for s in PATIENT_SCENARIOS if s["gap_type"] and s["gap_type"].startswith("multi_") and s["status"] == "active")
    resolved = sum(1 for s in PATIENT_SCENARIOS if s["status"] == "resolved")
    
    print(f"  Eligibility Issues (for Eli):     {active_elig} active")
    print(f"  Scheduling Issues (for Sam):      {active_attend} active")
    print(f"  Prior Auth Issues (for Dr. Casey): {active_coverage} active")
    print(f"  Complex/Multi-Issue Cases:        {active_multi} active")
    print(f"  All Clear (green):                {resolved} resolved")
    print(f"  TOTAL:                            {len(PATIENT_SCENARIOS)} patients")
    
    print("\n🎯 DEMO TIPS")
    print("-" * 50)
    print("  1. Login as different users to see role-based filtering")
    print("  2. 'Alex Admin' sees ALL tasks")
    print("  3. 'Eli Eligibility' only sees eligibility tasks")
    print("  4. 'Sam Scheduler' only sees scheduling tasks")
    print("  5. 'Dr. Casey Clinical' only sees prior auth tasks")
    print("  6. Search for 'Demo - All Clear' to show resolved patients")
    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("MOBIUS OS - DEMO DATA SEED")
    print("=" * 60)
    print("\nThis script creates a clean demo environment.")
    print("All existing data will be cleared and replaced.\n")
    
    # Initialize DB
    init_db()
    
    with get_db_session() as session:
        # Ensure tenant exists
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
        
        # Clear and seed
        clear_demo_data(session)
        seed_activities(session)
        users = seed_demo_users(session, tenant.tenant_id)
        patients = seed_demo_patients(session, tenant.tenant_id)
        seed_resolution_plans(session, patients, users, tenant.tenant_id)
        seed_payment_probabilities(session, patients, tenant.tenant_id)
    
    print_demo_summary()
    print("\n✅ Demo seed complete! Ready for your executive demo.\n")


if __name__ == "__main__":
    main()
