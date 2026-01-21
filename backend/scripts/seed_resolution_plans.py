#!/usr/bin/env python3
"""
Seed script for Resolution Plans - ALL PATIENTS.

Creates resolution plans for all patients in the database:
- 50% get "resolved" plans (no active issues - simple confirmation flow)
- 50% get "active" plans with gaps (step-by-step question flow)

Gap types distributed among active plans:
- 40% eligibility issues
- 30% coverage issues  
- 20% attendance issues
- 10% multiple gaps (eligibility + coverage or eligibility + attendance)

Run: python scripts/seed_resolution_plans.py
"""

import sys
import os
import uuid
import random
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models import (
    Tenant,
    AppUser,
    PatientContext,
    PatientSnapshot,
)
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


# Default tenant ID
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# =============================================================================
# Step Templates for Different Gap Types
# =============================================================================

ELIGIBILITY_STEPS = [
    {
        "step_code": "insurance_card_uploaded",
        "step_type": StepType.CONFIRMATION,
        "input_type": InputType.CONFIRMATION,
        "question_text": "Insurance card on file?",
        "factor_type": FactorType.ELIGIBILITY,
        "can_system_answer": True,
        "assignable_activities": ["verify_eligibility", "check_in_patients"],
        "answer_options": [
            {"code": "yes", "label": "Yes - Card uploaded"},
            {"code": "no", "label": "No - Missing"},
        ],
    },
    {
        "step_code": "has_insurance",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Does patient have active insurance?",
        "factor_type": FactorType.ELIGIBILITY,
        "can_system_answer": True,
        "assignable_activities": ["verify_eligibility", "check_in_patients"],
        "answer_options": [
            {"code": "yes", "label": "Yes - Active coverage", "next_step_code": "collect_payer"},
            {"code": "no", "label": "No - Uninsured", "next_step_code": "self_pay_discussion"},
            {"code": "unknown", "label": "Unknown - Need to verify", "next_step_code": "contact_patient"},
        ],
    },
    {
        "step_code": "collect_payer",
        "step_type": StepType.FORM,
        "input_type": InputType.FORM,
        "question_text": "Enter insurance information",
        "factor_type": FactorType.ELIGIBILITY,
        "can_system_answer": True,
        "assignable_activities": ["verify_eligibility", "check_in_patients"],
        "form_fields": [
            {"field": "payer_name", "label": "Payer Name", "type": "select", "required": True},
            {"field": "policy_number", "label": "Policy Number", "type": "text", "required": True},
            {"field": "group_number", "label": "Group Number", "type": "text", "required": False},
        ],
    },
    {
        "step_code": "verify_active",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Is coverage active with valid dates?",
        "factor_type": FactorType.ELIGIBILITY,
        "can_system_answer": True,
        "assignable_activities": ["verify_eligibility"],
        "answer_options": [
            {"code": "active", "label": "Yes - Active coverage"},
            {"code": "expired", "label": "No - Coverage expired"},
            {"code": "check_payer", "label": "Need to verify with payer"},
        ],
    },
]

COVERAGE_STEPS = [
    {
        "step_code": "check_auth_required",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Is prior authorization required for this service?",
        "factor_type": FactorType.COVERAGE,
        "can_system_answer": True,
        "assignable_activities": ["prior_authorization"],  # Only auth specialists
        "answer_options": [
            {"code": "yes", "label": "Yes - Required"},
            {"code": "no", "label": "No - Not required"},
        ],
    },
    {
        "step_code": "check_documentation",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Is medical necessity documented?",
        "factor_type": FactorType.COVERAGE,
        "can_system_answer": True,
        "assignable_activities": ["prior_authorization"],
        "answer_options": [
            {"code": "sufficient", "label": "Yes - Sufficient documentation"},
            {"code": "partial", "label": "Partial - Need more details"},
            {"code": "missing", "label": "No - Documentation missing"},
        ],
    },
    {
        "step_code": "submit_auth",
        "step_type": StepType.ACTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Submit prior authorization request",
        "factor_type": FactorType.COVERAGE,
        "can_system_answer": False,
        "assignable_activities": ["prior_authorization"],
        "answer_options": [
            {"code": "submitted", "label": "Submit to Payer", "next_step_code": "track_status"},
            {"code": "manual", "label": "I'll do this manually", "next_step_code": "track_status"},
            {"code": "need_info", "label": "Need more information"},
        ],
    },
    {
        "step_code": "track_status",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Authorization decision received?",
        "factor_type": FactorType.COVERAGE,
        "can_system_answer": True,
        "assignable_activities": ["prior_authorization"],
        "answer_options": [
            {"code": "approved", "label": "Approved"},
            {"code": "denied", "label": "Denied"},
            {"code": "pending", "label": "Still pending - Follow up"},
        ],
    },
]

ATTENDANCE_STEPS = [
    {
        "step_code": "check_satisfaction",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Is patient satisfied with care?",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": True,
        "assignable_activities": ["schedule_appointments", "patient_outreach"],
        "answer_options": [
            {"code": "happy", "label": "Happy - No concerns"},
            {"code": "neutral", "label": "Neutral"},
            {"code": "unhappy", "label": "Unhappy - Has concerns"},
            {"code": "unknown", "label": "Unknown - Need to ask"},
        ],
    },
    {
        "step_code": "verify_timing",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Does the appointment time still work?",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": False,
        "assignable_activities": ["schedule_appointments", "patient_outreach"],
        "answer_options": [
            {"code": "yes", "label": "Yes - Time works"},
            {"code": "reschedule", "label": "No - Need to reschedule"},
            {"code": "unknown", "label": "Unknown - Need to confirm"},
        ],
    },
    {
        "step_code": "assess_transportation",
        "step_type": StepType.QUESTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Transportation available?",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": False,
        "assignable_activities": ["schedule_appointments", "patient_outreach"],
        "answer_options": [
            {"code": "yes", "label": "Yes - Has transportation"},
            {"code": "needs_help", "label": "No - Needs assistance"},
            {"code": "unknown", "label": "Unknown - Need to ask"},
        ],
    },
    {
        "step_code": "send_reminder",
        "step_type": StepType.ACTION,
        "input_type": InputType.SINGLE_CHOICE,
        "question_text": "Send appointment reminder",
        "factor_type": FactorType.ATTENDANCE,
        "can_system_answer": True,
        "assignable_activities": ["schedule_appointments"],
        "answer_options": [
            {"code": "send_sms", "label": "Send SMS reminder"},
            {"code": "send_email", "label": "Send email reminder"},
            {"code": "call", "label": "Call patient"},
            {"code": "skip", "label": "Skip - Already contacted"},
        ],
    },
]


def get_users(db, tenant_id):
    """Get some users for assignment."""
    users = db.query(AppUser).filter(AppUser.tenant_id == tenant_id).limit(10).all()
    return users if users else []


def create_resolved_plan(db, patient, tenant_id, users):
    """Create a resolved plan (no active issues)."""
    user = random.choice(users) if users else None
    
    # Randomly pick what was "resolved"
    gap_type = random.choice(["eligibility", "coverage", "attendance"])
    resolution_types = {
        "eligibility": "eligibility_verified",
        "coverage": "coverage_confirmed",
        "attendance": "appointment_confirmed",
    }
    resolution_notes = {
        "eligibility": "Insurance verified - active coverage confirmed",
        "coverage": "Service covered under patient's plan - no auth required",
        "attendance": "Patient confirmed appointment - transportation arranged",
    }
    
    plan = ResolutionPlan(
        patient_context_id=patient.patient_context_id,
        tenant_id=tenant_id,
        gap_types=[gap_type],
        status=PlanStatus.RESOLVED,
        initial_probability=random.uniform(0.4, 0.6),
        current_probability=random.uniform(0.88, 0.98),
        target_probability=0.85,
        resolved_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72)),
        resolved_by=user.user_id if user else None,
        resolution_type=resolution_types[gap_type],
        resolution_notes=resolution_notes[gap_type],
        batch_job_id="seed_all_plans_v1",
    )
    db.add(plan)
    db.flush()
    
    # Add 2-3 completed steps
    steps_template = {
        "eligibility": ELIGIBILITY_STEPS[:3],
        "coverage": COVERAGE_STEPS[:3],
        "attendance": ATTENDANCE_STEPS[:3],
    }[gap_type]
    
    for i, step_data in enumerate(steps_template):
        step = PlanStep(
            plan_id=plan.plan_id,
            step_order=i + 1,
            status=StepStatus.COMPLETED,
            completed_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
            **step_data
        )
        db.add(step)
        db.flush()
        
        # Add answer
        answer_code = step_data["answer_options"][0]["code"] if step_data.get("answer_options") else "confirmed"
        answer = StepAnswer(
            step_id=step.step_id,
            answer_code=answer_code,
            answered_by=user.user_id if user else None,
            answer_mode=random.choice([AnswerMode.AGENTIC, AnswerMode.COPILOT, AnswerMode.USER_DRIVEN]),
        )
        db.add(answer)
    
    return plan


def create_active_plan(db, patient, tenant_id, users, gap_type):
    """Create an active plan with gaps to resolve."""
    
    # Determine steps based on gap type
    if gap_type == "eligibility":
        steps_template = ELIGIBILITY_STEPS
        gap_types = ["eligibility"]
        initial_prob = random.uniform(0.25, 0.45)
    elif gap_type == "coverage":
        steps_template = COVERAGE_STEPS
        gap_types = ["coverage"]
        initial_prob = random.uniform(0.35, 0.55)
    elif gap_type == "attendance":
        steps_template = ATTENDANCE_STEPS
        gap_types = ["attendance"]
        initial_prob = random.uniform(0.45, 0.65)
    else:  # multiple
        # Combine two gap types
        gap_combo = random.choice([
            ("eligibility", "coverage"),
            ("eligibility", "attendance"),
            ("coverage", "attendance"),
        ])
        gap_types = list(gap_combo)
        steps_template = (
            ELIGIBILITY_STEPS[:2] if "eligibility" in gap_combo else []
        ) + (
            COVERAGE_STEPS[:2] if "coverage" in gap_combo else []
        ) + (
            ATTENDANCE_STEPS[:2] if "attendance" in gap_combo else []
        )
        initial_prob = random.uniform(0.20, 0.40)
    
    plan = ResolutionPlan(
        patient_context_id=patient.patient_context_id,
        tenant_id=tenant_id,
        gap_types=gap_types,
        status=PlanStatus.ACTIVE,
        initial_probability=initial_prob,
        current_probability=initial_prob + random.uniform(0, 0.15),
        target_probability=0.85,
        batch_job_id="seed_all_plans_v1",
    )
    db.add(plan)
    db.flush()
    
    # Determine how many steps are completed (0-2)
    completed_count = random.randint(0, min(2, len(steps_template) - 1))
    current_idx = completed_count
    
    step_objects = []
    for i, step_data in enumerate(steps_template):
        if i < completed_count:
            status = StepStatus.COMPLETED
        elif i == current_idx:
            status = StepStatus.CURRENT
        else:
            status = StepStatus.PENDING
        
        # Add system suggestion for some steps
        system_suggestion = None
        if step_data.get("can_system_answer") and random.random() > 0.4:
            if step_data["step_code"] == "has_insurance":
                payers = ["BlueCross", "Aetna", "United", "Cigna", "Humana", "Medicare", "Medicaid"]
                system_suggestion = {
                    "answer": "yes",
                    "source": "card_detected",
                    "payer": random.choice(payers),
                    "confidence": random.uniform(0.75, 0.95)
                }
            elif step_data["step_code"] == "check_satisfaction":
                system_suggestion = {
                    "answer": "happy",
                    "source": "survey_data",
                    "score": random.uniform(3.5, 4.8)
                }
        
        step = PlanStep(
            plan_id=plan.plan_id,
            step_order=i + 1,
            status=status,
            system_suggestion=system_suggestion,
            completed_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24)) if status == StepStatus.COMPLETED else None,
            **step_data
        )
        db.add(step)
        step_objects.append(step)
    
    db.flush()
    
    # Set current step
    current_step = next((s for s in step_objects if s.status == StepStatus.CURRENT), None)
    if current_step:
        plan.current_step_id = current_step.step_id
    
    # Add answers for completed steps
    user = random.choice(users) if users else None
    for step in step_objects:
        if step.status == StepStatus.COMPLETED:
            # Pick first answer option or a reasonable default
            opts = step.answer_options or []
            answer_code = opts[0]["code"] if opts else "confirmed"
            
            answer = StepAnswer(
                step_id=step.step_id,
                answer_code=answer_code,
                answered_by=user.user_id if user and random.random() > 0.3 else None,
                answer_mode=random.choice([AnswerMode.AGENTIC, AnswerMode.COPILOT]),
            )
            db.add(answer)
    
    return plan


def main():
    """Main entry point."""
    print("=" * 60)
    print("Seeding Resolution Plans for ALL Patients")
    print("=" * 60)
    
    # Initialize DB
    init_db()
    db = get_db_session()
    
    try:
        # Get default tenant
        tenant = db.query(Tenant).filter(Tenant.tenant_id == DEFAULT_TENANT_ID).first()
        if not tenant:
            print("\nERROR: No tenant found. Please run seed_data.py first.")
            return
        
        print(f"\nUsing tenant: {tenant.name} (id: {tenant.tenant_id})")
        
        # Get all patients
        patients = db.query(PatientContext).filter(
            PatientContext.tenant_id == tenant.tenant_id
        ).all()
        
        print(f"Found {len(patients)} patients")
        
        if not patients:
            print("ERROR: No patients found. Please run seed_data.py first.")
            return
        
        # Get users for assignment
        users = get_users(db, tenant.tenant_id)
        print(f"Found {len(users)} users for assignment")
        
        # Clear existing plans (optional - comment out to keep existing)
        existing_count = db.query(ResolutionPlan).filter(
            ResolutionPlan.tenant_id == tenant.tenant_id
        ).count()
        
        if existing_count > 0:
            print(f"\nClearing {existing_count} existing resolution plans...")
            db.query(StepAnswer).filter(
                StepAnswer.step_id.in_(
                    db.query(PlanStep.step_id).join(ResolutionPlan).filter(
                        ResolutionPlan.tenant_id == tenant.tenant_id
                    )
                )
            ).delete(synchronize_session=False)
            db.query(PlanNote).filter(
                PlanNote.plan_id.in_(
                    db.query(ResolutionPlan.plan_id).filter(
                        ResolutionPlan.tenant_id == tenant.tenant_id
                    )
                )
            ).delete(synchronize_session=False)
            db.query(PlanStep).filter(
                PlanStep.plan_id.in_(
                    db.query(ResolutionPlan.plan_id).filter(
                        ResolutionPlan.tenant_id == tenant.tenant_id
                    )
                )
            ).delete(synchronize_session=False)
            db.query(ResolutionPlan).filter(
                ResolutionPlan.tenant_id == tenant.tenant_id
            ).delete(synchronize_session=False)
            db.commit()
            print("  Cleared existing plans.")
        
        # Shuffle patients for random distribution
        random.shuffle(patients)
        
        # Split 50/50
        half = len(patients) // 2
        resolved_patients = patients[:half]
        active_patients = patients[half:]
        
        print(f"\nCreating plans:")
        print(f"  - {len(resolved_patients)} resolved (no issues)")
        print(f"  - {len(active_patients)} active (with gaps)")
        
        # Create resolved plans (50%)
        print("\n--- Creating Resolved Plans ---")
        resolved_count = 0
        for i, patient in enumerate(resolved_patients):
            create_resolved_plan(db, patient, tenant.tenant_id, users)
            resolved_count += 1
            if (i + 1) % 100 == 0:
                db.commit()
                print(f"  Created {i + 1}/{len(resolved_patients)} resolved plans...")
        
        db.commit()
        print(f"  Created {resolved_count} resolved plans")
        
        # Create active plans (50%) with gap type distribution:
        # 40% eligibility, 30% coverage, 20% attendance, 10% multiple
        print("\n--- Creating Active Plans ---")
        active_count = 0
        gap_distribution = (
            ["eligibility"] * 40 +
            ["coverage"] * 30 +
            ["attendance"] * 20 +
            ["multiple"] * 10
        )
        
        for i, patient in enumerate(active_patients):
            gap_type = random.choice(gap_distribution)
            create_active_plan(db, patient, tenant.tenant_id, users, gap_type)
            active_count += 1
            if (i + 1) % 100 == 0:
                db.commit()
                print(f"  Created {i + 1}/{len(active_patients)} active plans...")
        
        db.commit()
        print(f"  Created {active_count} active plans")
        
        print("\n" + "=" * 60)
        print("Seeding complete!")
        print("=" * 60)
        
        # Summary
        plan_count = db.query(ResolutionPlan).filter(
            ResolutionPlan.tenant_id == tenant.tenant_id
        ).count()
        
        resolved_plans = db.query(ResolutionPlan).filter(
            ResolutionPlan.tenant_id == tenant.tenant_id,
            ResolutionPlan.status == PlanStatus.RESOLVED
        ).count()
        
        active_plans = db.query(ResolutionPlan).filter(
            ResolutionPlan.tenant_id == tenant.tenant_id,
            ResolutionPlan.status == PlanStatus.ACTIVE
        ).count()
        
        step_count = db.query(PlanStep).count()
        answer_count = db.query(StepAnswer).count()
        
        print(f"\nDatabase Summary:")
        print(f"  Total Resolution Plans: {plan_count}")
        print(f"    - Resolved (50%): {resolved_plans}")
        print(f"    - Active (50%): {active_plans}")
        print(f"  Plan Steps: {step_count}")
        print(f"  Step Answers: {answer_count}")
        
        print(f"\nPatients with active gaps will show step-by-step questions.")
        print(f"Patients with resolved plans will show simple confirmation.")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
