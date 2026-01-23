#!/usr/bin/env python3
"""
Seed script for payment probability and task data.

Creates:
1. Task templates (reusable task definitions)
2. Sample payment probabilities for existing patients
3. Sample task instances for testing

Run: python scripts/seed_probability_data.py
"""

import sys
import os
import uuid
from datetime import datetime, date, timedelta
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models import (
    Tenant,
    PatientContext,
)
from app.models.probability import (
    PaymentProbability,
    TaskTemplate,
    TaskStep,
    TaskInstance,
)


# Task templates to seed
TASK_TEMPLATES = [
    {
        "task_code": "verify_eligibility",
        "task_name": "Verify Insurance Eligibility",
        "task_description": "Verify patient's insurance eligibility and coverage dates",
        "assignable_to": ["system", "user"],
        "can_system_execute": True,
        "requires_human_in_loop": False,
        "success_rate_threshold": 0.85,
        "historical_success_rate": 0.92,
        "value_tier": "medium",
        "expected_probability_lift": 0.15,
        "always_requires_oversight": False,
        "steps": [
            {"step_code": "get_demographics", "step_name": "Retrieve patient demographics", "can_system_execute": True},
            {"step_code": "query_clearinghouse", "step_name": "Query insurance clearinghouse", "can_system_execute": True},
            {"step_code": "validate_dates", "step_name": "Validate coverage dates", "can_system_execute": True},
            {"step_code": "confirm_benefits", "step_name": "Confirm benefits", "can_system_execute": True},
        ]
    },
    {
        "task_code": "get_preauth",
        "task_name": "Obtain Prior Authorization",
        "task_description": "Request and obtain prior authorization for scheduled services",
        "assignable_to": ["system", "user"],
        "can_system_execute": True,
        "requires_human_in_loop": True,  # Needs human review
        "success_rate_threshold": 0.80,
        "historical_success_rate": 0.75,
        "value_tier": "high",
        "expected_probability_lift": 0.25,
        "always_requires_oversight": True,
        "steps": [
            {"step_code": "check_requirement", "step_name": "Check if preauth required", "can_system_execute": True},
            {"step_code": "gather_clinical", "step_name": "Gather clinical documentation", "can_system_execute": False, "requires_human_in_loop": True},
            {"step_code": "submit_request", "step_name": "Submit preauth request", "can_system_execute": True},
            {"step_code": "track_status", "step_name": "Track authorization status", "can_system_execute": True},
            {"step_code": "handle_denial", "step_name": "Handle denial/appeal if needed", "can_system_execute": False, "requires_human_in_loop": True},
        ]
    },
    {
        "task_code": "confirm_appointment",
        "task_name": "Confirm Patient Appointment",
        "task_description": "Send appointment reminders and confirm patient attendance",
        "assignable_to": ["system", "user", "patient"],
        "can_system_execute": True,
        "requires_human_in_loop": False,
        "success_rate_threshold": 0.90,
        "historical_success_rate": 0.95,
        "value_tier": "low",
        "expected_probability_lift": 0.10,
        "always_requires_oversight": False,
        "steps": [
            {"step_code": "send_reminder", "step_name": "Send appointment reminder", "can_system_execute": True},
            {"step_code": "get_confirmation", "step_name": "Get patient confirmation", "can_system_execute": True},
            {"step_code": "update_status", "step_name": "Update appointment status", "can_system_execute": True},
        ]
    },
    {
        "task_code": "review_billing",
        "task_name": "Review Billing Codes",
        "task_description": "Review and validate billing codes for accuracy",
        "assignable_to": ["user", "role"],
        "assignable_roles": ["billing_specialist", "coder"],
        "can_system_execute": False,  # Requires human judgment
        "requires_human_in_loop": True,
        "success_rate_threshold": 0.95,
        "historical_success_rate": None,  # No system history
        "value_tier": "high",
        "expected_probability_lift": 0.20,
        "always_requires_oversight": True,
        "steps": [
            {"step_code": "pull_codes", "step_name": "Pull procedure codes", "can_system_execute": True},
            {"step_code": "validate_codes", "step_name": "Validate code accuracy", "can_system_execute": False, "requires_human_in_loop": True},
            {"step_code": "check_bundling", "step_name": "Check for bundling issues", "can_system_execute": False, "requires_human_in_loop": True},
            {"step_code": "approve_final", "step_name": "Approve final codes", "can_system_execute": False, "requires_human_in_loop": True},
        ]
    },
    {
        "task_code": "patient_outreach",
        "task_name": "Contact Patient",
        "task_description": "Reach out to patient for missing information or follow-up",
        "assignable_to": ["user", "system", "patient"],
        "can_system_execute": True,  # Can send automated messages
        "requires_human_in_loop": False,
        "success_rate_threshold": 0.70,
        "historical_success_rate": 0.65,
        "value_tier": "medium",
        "expected_probability_lift": 0.10,
        "always_requires_oversight": False,
        "steps": [
            {"step_code": "identify_info", "step_name": "Identify missing information", "can_system_execute": True},
            {"step_code": "send_message", "step_name": "Send patient message", "can_system_execute": True},
            {"step_code": "track_response", "step_name": "Track patient response", "can_system_execute": True},
            {"step_code": "manual_call", "step_name": "Make manual call if needed", "can_system_execute": False, "requires_human_in_loop": True, "is_optional": True},
        ]
    },
    {
        "task_code": "verify_demographics",
        "task_name": "Verify Patient Demographics",
        "task_description": "Verify and update patient demographic information",
        "assignable_to": ["system", "user"],
        "can_system_execute": True,
        "requires_human_in_loop": False,
        "success_rate_threshold": 0.90,
        "historical_success_rate": 0.88,
        "value_tier": "low",
        "expected_probability_lift": 0.05,
        "always_requires_oversight": False,
        "steps": []  # Simple task, no sub-steps
    },
]


def seed_task_templates(db, tenant_id: uuid.UUID):
    """Seed task templates and their steps."""
    print("\n--- Seeding Task Templates ---")
    
    templates_created = 0
    steps_created = 0
    
    for tmpl_data in TASK_TEMPLATES:
        # Check if template already exists
        existing = db.query(TaskTemplate).filter(
            TaskTemplate.task_code == tmpl_data["task_code"]
        ).first()
        
        if existing:
            print(f"  [exists] {tmpl_data['task_code']}")
            continue
        
        # Create template
        template = TaskTemplate(
            tenant_id=tenant_id,
            task_code=tmpl_data["task_code"],
            task_name=tmpl_data["task_name"],
            task_description=tmpl_data.get("task_description"),
            assignable_to=tmpl_data.get("assignable_to"),
            assignable_roles=tmpl_data.get("assignable_roles"),
            can_system_execute=tmpl_data.get("can_system_execute", False),
            requires_human_in_loop=tmpl_data.get("requires_human_in_loop", False),
            success_rate_threshold=tmpl_data.get("success_rate_threshold", 0.8),
            historical_success_rate=tmpl_data.get("historical_success_rate"),
            value_tier=tmpl_data.get("value_tier"),
            expected_probability_lift=tmpl_data.get("expected_probability_lift"),
            always_requires_oversight=tmpl_data.get("always_requires_oversight", False),
            is_active=True,
        )
        db.add(template)
        db.flush()
        templates_created += 1
        print(f"  [created] {tmpl_data['task_code']} (id: {template.template_id})")
        
        # Create steps
        for idx, step_data in enumerate(tmpl_data.get("steps", []), start=1):
            step = TaskStep(
                template_id=template.template_id,
                step_order=idx,
                step_code=step_data["step_code"],
                step_name=step_data["step_name"],
                step_description=step_data.get("step_description"),
                can_system_execute=step_data.get("can_system_execute", False),
                requires_human_in_loop=step_data.get("requires_human_in_loop", False),
                is_optional=step_data.get("is_optional", False),
                is_active=True,
            )
            db.add(step)
            steps_created += 1
    
    db.commit()
    print(f"\n  Templates created: {templates_created}")
    print(f"  Steps created: {steps_created}")


def seed_payment_probabilities(db, tenant_id: uuid.UUID):
    """Seed payment probabilities for existing patients with problem statements."""
    print("\n--- Seeding Payment Probabilities ---")
    
    # Get all patient contexts for this tenant
    patients = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).all()
    
    print(f"  Found {len(patients)} patients")
    
    probabilities_created = 0
    probabilities_updated = 0
    
    # Patient-centered problem statements (5 categories, user-friendly language)
    # These align with Affordable Care Act style, patient/individual centered approach
    PROBLEM_STATEMENTS = {
        "attendance": [
            "Is the patient likely to attend this visit?",
            "Will the patient show up for their appointment?",
            "Is there a risk the patient may miss this visit?",
        ],
        "eligibility": [
            "Does the patient have coverage for this service?",
            "Is the patient's insurance active and valid?",
            "Does the patient have funding for this care?",
        ],
        "coverage": [
            "Is this service covered under their plan?",
            "Will the patient's insurance pay for this service?",
            "Is this procedure covered by the patient's insurance?",
        ],
        "errors": [
            "Are there any claim issues we need to address?",
            "Will we be able to submit a clean claim?",
            "Are there any billing problems to resolve?",
        ],
        "payor_error": [
            "Are there any payor errors to resolve?",
            "Does the payor need to correct their records?",
            "Are there payor system issues affecting this claim?",
        ],
    }
    
    # Patient-centered reasons (more empathetic, less technical)
    PROBLEM_REASONS = {
        "attendance": [
            "patient missed last appointment",
            "transportation challenges",
            "work schedule conflicts",
            "first-time visit - needs confirmation",
            "patient requested reschedule",
            "no response to reminder",
        ],
        "eligibility": [
            "insurance may have expired",
            "coverage change reported",
            "new insurance not yet verified",
            "Medicaid renewal in progress",
            "employer plan change",
            "coverage gap detected",
        ],
        "coverage": [
            "service may require authorization",
            "plan may not cover this procedure",
            "out-of-network concern",
            "benefit limit may be reached",
            "specialty referral needed",
            "plan restrictions apply",
        ],
        "errors": [
            "billing codes need review",
            "claim may have errors",
            "documentation incomplete",
            "provider information mismatch",
            "diagnosis codes need verification",
            "service dates need confirmation",
        ],
        "payor_error": [
            "payor system error detected",
            "payor records incorrect",
            "payor processing delay",
            "payor data mismatch",
            "payor portal issue",
            "payor requires correction",
        ],
    }
    
    # Define some probability profiles for variety
    profiles = [
        # High probability - GREEN (no problem statement needed, but generate anyway)
        {"overall": 0.92, "confidence": 0.9, "attendance": 0.95, "eligibility": 0.90, "coverage": 0.95, "errors": 0.98},
        {"overall": 0.88, "confidence": 0.85, "attendance": 0.92, "eligibility": 0.85, "coverage": 0.90, "errors": 0.95},
        # Medium probability - YELLOW
        {"overall": 0.72, "confidence": 0.8, "attendance": 0.85, "eligibility": 0.65, "coverage": 0.80, "errors": 0.90, "lowest": "eligibility"},
        {"overall": 0.68, "confidence": 0.75, "attendance": 0.90, "eligibility": 0.80, "coverage": 0.60, "errors": 0.85, "lowest": "coverage"},
        {"overall": 0.75, "confidence": 0.7, "attendance": 0.70, "eligibility": 0.85, "coverage": 0.85, "errors": 0.90, "lowest": "attendance"},
        # Low probability - RED
        {"overall": 0.45, "confidence": 0.8, "attendance": 0.50, "eligibility": 0.40, "coverage": 0.60, "errors": 0.80, "lowest": "eligibility"},
        {"overall": 0.35, "confidence": 0.75, "attendance": 0.80, "eligibility": 0.60, "coverage": 0.30, "errors": 0.70, "lowest": "coverage"},
        {"overall": 0.55, "confidence": 0.65, "attendance": 0.45, "eligibility": 0.70, "coverage": 0.75, "errors": 0.85, "lowest": "attendance"},
    ]
    
    for patient in patients:
        # Check if probability already exists
        existing = db.query(PaymentProbability).filter(
            PaymentProbability.patient_context_id == patient.patient_context_id
        ).first()
        
        # Pick a random profile
        profile = random.choice(profiles)
        
        # Determine lowest factor (map "errors" to "payor_error" if needed)
        lowest_factor = profile.get("lowest")
        if not lowest_factor:
            # Determine from values
            factors = {
                "attendance": profile["attendance"],
                "eligibility": profile["eligibility"],
                "coverage": profile["coverage"],
                "errors": profile["errors"],
            }
            lowest_factor = min(factors, key=factors.get)
        
        # Map "errors" to either "errors" or "payor_error" (20% chance for payor_error)
        if lowest_factor == "errors" and random.random() < 0.2:
            factor_key = "payor_error"
        else:
            factor_key = lowest_factor
        
        # Generate patient-centered problem statement
        problem_statement = random.choice(PROBLEM_STATEMENTS.get(factor_key, PROBLEM_STATEMENTS[lowest_factor]))
        reason = random.choice(PROBLEM_REASONS.get(factor_key, PROBLEM_REASONS[lowest_factor]))
        
        # Generate problem details (ordered list of issues)
        problem_details = []
        # Add primary issue
        problem_details.append({
            "issue": lowest_factor,  # Keep original factor for matching
            "question": problem_statement,  # Patient-centered question
            "reason": reason,
            "severity": "high" if profile["overall"] < 0.6 else "medium",
        })
        # Maybe add secondary issue (20% chance)
        if random.random() < 0.2:
            other_factors = [f for f in ["eligibility", "coverage", "attendance", "errors"] if f != lowest_factor]
            secondary = random.choice(other_factors)
            secondary_key = "payor_error" if secondary == "errors" and random.random() < 0.2 else secondary
            problem_details.append({
                "issue": secondary,
                "question": random.choice(PROBLEM_STATEMENTS.get(secondary_key, PROBLEM_STATEMENTS[secondary])),
                "reason": random.choice(PROBLEM_REASONS.get(secondary_key, PROBLEM_REASONS[secondary])),
                "severity": "low",
            })
        
        if existing:
            # Always update existing records to use the 5 categories (patient-centered)
            existing.problem_statement = problem_statement
            existing.problem_details = problem_details
            existing.lowest_factor = lowest_factor
            existing.lowest_factor_reason = reason
            probabilities_updated += 1
            continue
        
        # Create new probability record
        prob = PaymentProbability(
            patient_context_id=patient.patient_context_id,
            target_date=date.today() + timedelta(days=random.randint(1, 30)),
            overall_probability=profile["overall"],
            confidence=profile["confidence"],
            prob_appointment_attendance=profile["attendance"],
            prob_eligibility=profile["eligibility"],
            prob_coverage=profile["coverage"],
            prob_no_errors=profile["errors"],
            lowest_factor=lowest_factor,  # Keep original factor for matching with resolution plans
            lowest_factor_reason=reason,
            problem_statement=problem_statement,  # Patient-centered question
            problem_details=problem_details,
            batch_job_id="seed_script_v2",
        )
        db.add(prob)
        probabilities_created += 1
    
    db.commit()
    print(f"  Probabilities created: {probabilities_created}")
    print(f"  Probabilities updated: {probabilities_updated}")


def seed_task_instances(db, tenant_id: uuid.UUID):
    """Seed task instances for some patients."""
    print("\n--- Seeding Task Instances ---")
    
    # Get templates
    templates = {
        t.task_code: t for t in db.query(TaskTemplate).all()
    }
    
    if not templates:
        print("  No templates found, skipping task instances")
        return
    
    # Get patients with payment probability (focus on non-green)
    probs = db.query(PaymentProbability).filter(
        PaymentProbability.overall_probability < 0.85  # YELLOW or RED
    ).all()
    
    print(f"  Found {len(probs)} patients needing tasks")
    
    instances_created = 0
    
    # Define task assignment scenarios
    task_scenarios = [
        # Eligibility issue -> verify eligibility task
        {"condition": lambda p: p.prob_eligibility < 0.7, "task": "verify_eligibility", "assigned": "system"},
        # Coverage issue -> get preauth task
        {"condition": lambda p: p.prob_coverage < 0.7, "task": "get_preauth", "assigned": "user"},
        # Attendance issue -> confirm appointment
        {"condition": lambda p: p.prob_appointment_attendance < 0.7, "task": "confirm_appointment", "assigned": "system"},
        # Low overall -> patient outreach
        {"condition": lambda p: p.overall_probability < 0.5, "task": "patient_outreach", "assigned": "system"},
    ]
    
    for prob in probs:
        # Check if tasks already exist
        existing = db.query(TaskInstance).filter(
            TaskInstance.patient_context_id == prob.patient_context_id
        ).first()
        
        if existing:
            continue
        
        # Assign tasks based on scenarios
        for scenario in task_scenarios:
            if scenario["condition"](prob):
                template = templates.get(scenario["task"])
                if not template:
                    continue
                
                instance = TaskInstance(
                    template_id=template.template_id,
                    patient_context_id=prob.patient_context_id,
                    assigned_to_type=scenario["assigned"],
                    status="pending",
                    priority=2 if template.value_tier == "high" else 3,
                    reason=f"Auto-assigned due to low {prob.lowest_factor} probability",
                    expected_impact=template.expected_probability_lift,
                    batch_job_id="seed_script_v1",
                )
                db.add(instance)
                instances_created += 1
    
    db.commit()
    print(f"  Task instances created: {instances_created}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Seeding Payment Probability and Task Data")
    print("=" * 60)
    
    # Initialize DB
    init_db()
    db = get_db_session()
    
    try:
        # Get default tenant
        tenant = db.query(Tenant).first()
        if not tenant:
            print("\nERROR: No tenant found. Please run seed_data.py first.")
            return
        
        print(f"\nUsing tenant: {tenant.name} (id: {tenant.tenant_id})")
        
        # Seed task templates
        seed_task_templates(db, tenant.tenant_id)
        
        # Seed payment probabilities
        seed_payment_probabilities(db, tenant.tenant_id)
        
        # Seed task instances
        seed_task_instances(db, tenant.tenant_id)
        
        print("\n" + "=" * 60)
        print("Seeding complete!")
        print("=" * 60)
        
        # Summary
        template_count = db.query(TaskTemplate).count()
        step_count = db.query(TaskStep).count()
        prob_count = db.query(PaymentProbability).count()
        instance_count = db.query(TaskInstance).count()
        
        print(f"\nDatabase Summary:")
        print(f"  Task Templates: {template_count}")
        print(f"  Task Steps: {step_count}")
        print(f"  Payment Probabilities: {prob_count}")
        print(f"  Task Instances: {instance_count}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
