#!/usr/bin/env python3
"""
Seed ONE patient with properly aligned Layer 1 and Layer 2 data.

This creates a clean example that shows exactly what should be seeded.
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
    ResolutionPlan, PlanStep, 
    PlanStatus, StepStatus, StepType, InputType, FactorType
)
from app.models.patient_ids import PatientId
from app.models.mock_emr import MockEmrRecord
from app.models.sidecar import Milestone, MilestoneSubstep, MilestoneHistory, UserAlert, UserOwnedTask
from app.models.response import MiniSubmission, SystemResponse
from app.models.event_log import EventLog
from app.models.evidence import PlanStepFactLink, Evidence, SourceDocument, RawData, FactSourceLink


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
    from app.models.resolution import StepAnswer, PlanNote
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


def create_test_patient(db, tenant_id):
    """Create a fresh test patient."""
    
    # Create patient context
    patient = PatientContext(
        tenant_id=tenant_id,
        patient_key=f"test_seed_{uuid.uuid4().hex[:8]}",
    )
    db.add(patient)
    db.flush()
    
    # Create patient snapshot (display data)
    snapshot = PatientSnapshot(
        patient_context_id=patient.patient_context_id,
        display_name="Test Patient - Eligibility Issue",
        id_label="MRN",
        id_masked="****TEST",
        verified=True,
        data_complete=True,
    )
    db.add(snapshot)
    
    # Create patient ID (MRN)
    patient_id = PatientId(
        patient_context_id=patient.patient_context_id,
        id_type="mrn",
        id_value=f"TEST-{uuid.uuid4().hex[:6].upper()}",
        is_primary=True,
    )
    db.add(patient_id)
    db.flush()
    
    return patient


def seed_layer1(db, patient_context_id):
    """
    LAYER 1: PaymentProbability
    
    This is the critical bottleneck - what Mini displays.
    It identifies: "What is the PROBLEM with this patient?"
    """
    
    # The 5 Categories (from the architecture):
    # a) Likely to no-show (attendance)
    # b) Likely not eligible for funding (eligibility)  
    # c) Likely not eligible for service (coverage)
    # d) Likely not able to produce a clean claim (errors)
    # e) Likely payor error and need to rework (payor_error -> maps to errors)
    
    # For this example: ELIGIBILITY is the problem
    BOTTLENECK = "eligibility"
    
    prob = PaymentProbability(
        patient_context_id=patient_context_id,
        target_date=date.today() + timedelta(days=7),
        
        # Overall probability of getting paid
        overall_probability=0.45,  # Low - there's a problem
        confidence=0.85,
        
        # Individual factor probabilities
        prob_appointment_attendance=0.90,  # Likely to show up
        prob_eligibility=0.40,             # ← THIS IS LOW - the bottleneck
        prob_coverage=0.85,                # Service likely covered
        prob_no_errors=0.92,               # Claim likely clean
        
        # The bottleneck (must match what we seed in Layer 2)
        lowest_factor=BOTTLENECK,
        lowest_factor_reason="Insurance may have expired - needs verification",
        
        # Problem statement (what Mini displays)
        problem_statement="Does the patient have funding for this care?",
        
        # Problem details (for detailed view)
        problem_details=[{
            "issue": BOTTLENECK,
            "question": "Does the patient have funding for this care?",
            "reason": "Insurance may have expired - needs verification",
            "severity": "high",
        }],
        
        batch_job_id="seed_one_patient",
    )
    db.add(prob)
    db.flush()
    
    print(f"\n  LAYER 1 SEEDED:")
    print(f"    lowest_factor: {BOTTLENECK}")
    print(f"    problem_statement: \"{prob.problem_statement}\"")
    
    return prob, BOTTLENECK


def seed_layer2(db, patient_context_id, tenant_id, bottleneck):
    """
    LAYER 2: ResolutionPlan + Steps
    
    This must ALIGN with Layer 1's bottleneck.
    gap_types must include the same factor as lowest_factor.
    """
    
    # Create resolution plan - gap_types MUST match Layer 1's lowest_factor
    plan = ResolutionPlan(
        patient_context_id=patient_context_id,
        tenant_id=tenant_id,
        gap_types=[bottleneck],  # ← MUST MATCH Layer 1
        status=PlanStatus.ACTIVE,
        initial_probability=0.45,
        current_probability=0.45,
        target_probability=0.85,
        batch_job_id="seed_one_patient",
    )
    db.add(plan)
    db.flush()
    
    # Create steps (Layer 3: Mitigations)
    # These are the specific actions to resolve the eligibility issue
    
    ELIGIBILITY_STEPS = [
        {
            "step_order": 1,
            "step_code": "verify_eligibility_270",
            "step_type": StepType.ACTION,
            "input_type": InputType.SINGLE_CHOICE,
            "question_text": "Run 270 eligibility check",
            "factor_type": FactorType.ELIGIBILITY,
            "can_system_answer": True,  # Mobius can do this
            "assignable_activities": ["verify_eligibility"],
            "assignee_type": "user",  # User's turn - shows action buttons
            "status": StepStatus.CURRENT,
            "answer_options": [
                {"code": "mobius", "label": "Mobius: Run eligibility check via API"},
                {"code": "copilot", "label": "Copilot: I'll review Mobius results"},
                {"code": "manual", "label": "Manual: I'll check myself"},
            ],
        },
        {
            "step_order": 2,
            "step_code": "confirm_coverage",
            "step_type": StepType.QUESTION,
            "input_type": InputType.SINGLE_CHOICE,
            "question_text": "Is the patient's insurance active?",
            "factor_type": FactorType.ELIGIBILITY,
            "can_system_answer": True,
            "assignable_activities": ["verify_eligibility"],
            "assignee_type": "user",  # User's turn
            "status": StepStatus.PENDING,
            "answer_options": [
                {"code": "yes", "label": "Yes - Insurance is active"},
                {"code": "no", "label": "No - Insurance expired/terminated"},
                {"code": "unknown", "label": "Unknown - Need more info"},
            ],
        },
        {
            "step_order": 3,
            "step_code": "contact_patient",
            "step_type": StepType.ACTION,
            "input_type": InputType.SINGLE_CHOICE,
            "question_text": "Contact patient about insurance",
            "factor_type": FactorType.ELIGIBILITY,
            "can_system_answer": True,  # Mobius can send messages
            "assignable_activities": ["patient_outreach"],
            "assignee_type": "mobius",  # System can do this
            "status": StepStatus.PENDING,
            "answer_options": [
                {"code": "send_email", "label": "Mobius: Send email"},
                {"code": "send_sms", "label": "Mobius: Send SMS"},
                {"code": "call", "label": "User: Call patient"},
            ],
        },
    ]
    
    step_objects = []
    for step_data in ELIGIBILITY_STEPS:
        step = PlanStep(plan_id=plan.plan_id, **step_data)
        db.add(step)
        step_objects.append(step)
    
    db.flush()
    
    # Set current step
    current = next((s for s in step_objects if s.status == StepStatus.CURRENT), None)
    if current:
        plan.current_step_id = current.step_id
    
    print(f"\n  LAYER 2 SEEDED:")
    print(f"    gap_types: {plan.gap_types}")
    print(f"    status: {plan.status}")
    print(f"    steps: {len(step_objects)}")
    for s in step_objects:
        print(f"      Step {s.step_order}: {s.step_code} ({s.status})")
    
    return plan


def main():
    print("=" * 70)
    print("SEEDING ONE PATIENT WITH ALIGNED LAYER 1 + LAYER 2")
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
        
        # Clean up all existing patients first
        cleanup_all_patients(db, tenant.tenant_id)
        
        # Create test patient
        print("\n--- Creating Test Patient ---")
        patient = create_test_patient(db, tenant.tenant_id)
        print(f"  patient_context_id: {patient.patient_context_id}")
        
        # Seed Layer 1 (PaymentProbability)
        print("\n--- Seeding Layer 1: PaymentProbability ---")
        prob, bottleneck = seed_layer1(db, patient.patient_context_id)
        
        # Seed Layer 2 (ResolutionPlan) - ALIGNED with Layer 1
        print("\n--- Seeding Layer 2: ResolutionPlan ---")
        plan = seed_layer2(db, patient.patient_context_id, tenant.tenant_id, bottleneck)
        
        db.commit()
        
        print("\n" + "=" * 70)
        print("SUCCESS! Data is now aligned:")
        print(f"  Layer 1 lowest_factor: {bottleneck}")
        print(f"  Layer 2 gap_types: {plan.gap_types}")
        print(f"  MATCH: {'YES' if bottleneck in plan.gap_types else 'NO'}")
        print("=" * 70)
        
        print(f"\nTo verify, run:")
        print(f"  python scripts/inspect_layers.py")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
