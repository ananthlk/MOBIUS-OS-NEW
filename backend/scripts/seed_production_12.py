#!/usr/bin/env python3
"""
Production Seed Script - 12 Demo Patients

Creates the 12 curated demo patients for production:
- 3 Attendance factor patients (Maria, James, Tanya)
- 3 Eligibility factor patients (Angela, Carlos, Denise)
- 6 Green/Resolved patients (Patricia, Robert, Linda, Michael, Jennifer, David)

Usage:
  DATABASE_MODE=cloud python scripts/seed_production_12.py
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
from app.models.evidence import PlanStepFactLink, Evidence


# =============================================================================
# PATIENT DEFINITIONS
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
    },
]


# =============================================================================
# STEP DEFINITIONS BY FACTOR
# =============================================================================

ATTENDANCE_STEPS = [
    {"order": 1, "code": "understanding_visit", "question": "Understanding the Patient's Visit", "can_auto": True},
    {"order": 2, "code": "staying_on_track", "question": "Helping the Patient Stay on Track", "can_auto": True},
    {"order": 3, "code": "clinical_readiness", "question": "Assessing Clinical Readiness", "can_auto": True},
    {"order": 4, "code": "reducing_risks", "question": "Reducing Attendance Risks", "can_auto": True},
    {"order": 5, "code": "backup_plan", "question": "Creating a Backup Plan", "can_auto": True},
]

ELIGIBILITY_STEPS = [
    {"order": 1, "code": "verify_coverage", "question": "Verifying Current Coverage Status", "can_auto": True},
    {"order": 2, "code": "identify_gaps", "question": "Identifying Coverage Gaps", "can_auto": True},
    {"order": 3, "code": "explore_options", "question": "Exploring Coverage Options", "can_auto": False},
    {"order": 4, "code": "initiate_action", "question": "Initiating Coverage Action", "can_auto": False},
    {"order": 5, "code": "confirm_eligibility", "question": "Confirming Eligibility", "can_auto": True},
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
    from app.models.mock_emr import MockEmrRecord
    
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
        db.query(PlanStep).filter(PlanStep.plan_id.in_(plan_ids)).delete(synchronize_session=False)
        db.query(ResolutionPlan).filter(ResolutionPlan.plan_id.in_(plan_ids)).delete(synchronize_session=False)
    
    db.query(Evidence).filter(Evidence.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(PaymentProbability).filter(PaymentProbability.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(TaskInstance).filter(TaskInstance.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(MockEmrRecord).filter(MockEmrRecord.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(PatientId).filter(PatientId.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(PatientSnapshot).filter(PatientSnapshot.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    db.query(PatientContext).filter(PatientContext.patient_context_id.in_(patient_ids)).delete(synchronize_session=False)
    
    db.flush()
    print(f"  ✓ Cleaned up {len(patient_ids)} existing patients")


def create_patient(db, tenant_id, patient_def):
    """Create a single patient with all related data."""
    
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
    
    # Create probability
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
    )
    db.add(prob)
    db.flush()
    
    # Create resolution plan if active
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
        
        first_step_id = None
        for i, step_def in enumerate(steps_def):
            status = StepStatus.CURRENT if i == 0 else StepStatus.PENDING
            
            step = PlanStep(
                plan_id=plan.plan_id,
                step_order=step_def["order"],
                step_code=step_def["code"],
                step_type=StepType.QUESTION,
                input_type=InputType.SINGLE_CHOICE,
                question_text=step_def["question"],
                factor_type=factor_type,
                can_system_answer=step_def["can_auto"],
                assignee_type=patient_def["assignee"],
                status=status,
            )
            db.add(step)
            db.flush()
            
            if i == 0:
                first_step_id = step.step_id
        
        if first_step_id:
            plan.current_step_id = first_step_id
    
    db.flush()
    return patient


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("PRODUCTION SEED - 12 DEMO PATIENTS")
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
            print(f"\n✓ Created tenant: {tenant.name}")
        else:
            print(f"\nTenant: {tenant.name}")
        
        # Clean up existing
        cleanup_existing(db, tenant.tenant_id)
        
        # Create patients
        print("\n--- Creating 12 Patients ---")
        
        attendance_count = 0
        eligibility_count = 0
        green_count = 0
        
        for patient_def in PATIENTS:
            patient = create_patient(db, tenant.tenant_id, patient_def)
            
            status_icon = "🟢" if patient_def["status"] == "resolved" else "🔵"
            factor_label = patient_def["factor"] or "resolved"
            print(f"  {status_icon} {patient_def['name']} ({factor_label})")
            
            if patient_def["factor"] == "attendance":
                attendance_count += 1
            elif patient_def["factor"] == "eligibility":
                eligibility_count += 1
            else:
                green_count += 1
        
        db.commit()
        
        print("\n" + "=" * 60)
        print("✓ SUCCESS - 12 PATIENTS CREATED")
        print("=" * 60)
        print(f"\n  Attendance Factor: {attendance_count}")
        print(f"  Eligibility Factor: {eligibility_count}")
        print(f"  Green/Resolved: {green_count}")
        print(f"\n  Total: {attendance_count + eligibility_count + green_count}")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
