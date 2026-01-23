#!/usr/bin/env python3
"""
Test Cascade Scenarios - Shows what happens in database, backend, and frontend

Tests 3 scenarios:
1. User overrides in Mini (Layer 1 → Layer 2 cascade)
2. User overrides in Sidecar (Layer 2 → Layer 1 cascade)
3. Multiple bottlenecks with different statuses

Run: python scripts/test_cascade_scenarios.py
"""

import sys
import os
import uuid
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models import Tenant, PatientContext
from app.models.probability import PaymentProbability
from app.models.resolution import ResolutionPlan, PlanStatus, PlanStep, StepStatus
from app.services.bottleneck_cascade import cascade_bottleneck_override


# Default tenant ID
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_subsection(title):
    """Print a subsection header."""
    print(f"\n--- {title} ---")


def get_patient_data(db, patient_key):
    """Get all relevant data for a patient."""
    patient_context = db.query(PatientContext).filter(
        PatientContext.patient_key == patient_key
    ).first()
    
    if not patient_context:
        return None
    
    # Get payment probability (Layer 1)
    prob = db.query(PaymentProbability).filter(
        PaymentProbability.patient_context_id == patient_context.patient_context_id
    ).order_by(PaymentProbability.computed_at.desc()).first()
    
    # Get resolution plan (Layer 2)
    plan = db.query(ResolutionPlan).filter(
        ResolutionPlan.patient_context_id == patient_context.patient_context_id,
        ResolutionPlan.status == PlanStatus.ACTIVE
    ).first()
    
    return {
        "patient_context": patient_context,
        "payment_probability": prob,
        "resolution_plan": plan,
    }


def print_patient_state(data, title="Current State", db=None):
    """Print the current state of a patient."""
    print_subsection(title)
    
    pc = data["patient_context"]
    prob = data["payment_probability"]
    plan = data["resolution_plan"]
    
    print(f"Patient: {pc.patient_key}")
    print(f"  Attention Status: {pc.attention_status}")
    print(f"  Override Color: {pc.override_color}")
    print(f"  Resolved Until: {pc.resolved_until}")
    
    if prob:
        print(f"\nLayer 1 (Payment Probability):")
        print(f"  Problem Statement: {prob.problem_statement}")
        print(f"  Lowest Factor: {prob.lowest_factor}")
        print(f"  Overall Probability: {prob.overall_probability:.2%}")
        if prob.problem_details:
            print(f"  Problem Details: {len(prob.problem_details)} issue(s)")
            for detail in prob.problem_details[-3:]:  # Show last 3
                if isinstance(detail, dict) and detail.get("type") == "user_override":
                    print(f"    - Override: {detail.get('factor')} -> {detail.get('status')} at {detail.get('timestamp')}")
    
    if plan and db:
        print(f"\nLayer 2 (Resolution Plan):")
        print(f"  Plan Status: {plan.status}")
        print(f"  Gap Types: {plan.gap_types}")
        notes_preview = (plan.resolution_notes[:100] + "...") if plan.resolution_notes and len(plan.resolution_notes) > 100 else (plan.resolution_notes or "None")
        print(f"  Resolution Notes: {notes_preview}")
        print(f"  Resolved At: {plan.resolved_at}")
        print(f"  Resolved By: {plan.resolved_by}")
        
        # Get steps
        steps = db.query(PlanStep).filter(
            PlanStep.plan_id == plan.plan_id
        ).order_by(PlanStep.step_order).all()
        print(f"  Steps: {len(steps)} total")
        for step in steps[:3]:  # Show first 3
            print(f"    - Step {step.step_order}: {step.question_text[:50]}... [{step.status}]")


def test_scenario_1_mini_override(db, tenant_id):
    """Scenario 1: User overrides in Mini (Layer 1 → Layer 2 cascade)"""
    print_section("SCENARIO 1: User Override in Mini (Layer 1 → Layer 2 Cascade)")
    
    # Find a patient with both Layer 1 and Layer 2 data
    patients = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).limit(10).all()
    
    test_patient = None
    for p in patients:
        prob = db.query(PaymentProbability).filter(
            PaymentProbability.patient_context_id == p.patient_context_id
        ).first()
        plan = db.query(ResolutionPlan).filter(
            ResolutionPlan.patient_context_id == p.patient_context_id,
            ResolutionPlan.status == PlanStatus.ACTIVE
        ).first()
        
        if prob and plan and prob.lowest_factor in (plan.gap_types or []):
            test_patient = p
            break
    
    if not test_patient:
        print("No suitable test patient found. Skipping scenario 1.")
        return
    
    data = get_patient_data(db, test_patient.patient_key)
    print_patient_state(data, "BEFORE Mini Override", db)
    
    # Simulate Mini override: User marks as "resolved"
    print_subsection("Action: User clicks 'Resolved' in Mini")
    
    prob = data["payment_probability"]
    user_id = uuid.uuid4()  # Mock user
    submitted_at = datetime.utcnow()
    
    # Call cascade function (what happens in mini.py)
    cascade_bottleneck_override(
        db=db,
        patient_context_id=test_patient.patient_context_id,
        bottleneck_factor=prob.lowest_factor,
        status="resolved",
        user_id=user_id,
        submitted_at=submitted_at,
        source_layer="layer1"
    )
    
    db.commit()
    
    # Refresh and show after state
    db.refresh(test_patient)
    data_after = get_patient_data(db, test_patient.patient_key)
    print_patient_state(data_after, "AFTER Mini Override (Cascade Applied)", db)
    
    print("\n✓ Expected Result:")
    print("  - Layer 1: Problem statement unchanged (from batch job)")
    print("  - Layer 2: Resolution plan status = RESOLVED")
    print("  - Layer 2: Resolution notes contain override info")
    print("  - Layer 2: Resolved_at and resolved_by set")


def test_scenario_2_sidecar_override(db, tenant_id):
    """Scenario 2: User overrides in Sidecar (Layer 2 → Layer 1 cascade)"""
    print_section("SCENARIO 2: User Override in Sidecar (Layer 2 → Layer 1 Cascade)")
    
    # Find a patient with both Layer 1 and Layer 2 data
    patients = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).limit(10).all()
    
    test_patient = None
    for p in patients:
        prob = db.query(PaymentProbability).filter(
            PaymentProbability.patient_context_id == p.patient_context_id
        ).first()
        plan = db.query(ResolutionPlan).filter(
            ResolutionPlan.patient_context_id == p.patient_context_id,
            ResolutionPlan.status == PlanStatus.ACTIVE
        ).first()
        
        if prob and plan:
            # Check if plan's gap_type matches prob's lowest_factor or exists in problem_details
            gap_types = plan.gap_types or []
            matches = (
                prob.lowest_factor in gap_types or
                (prob.problem_details and any(
                    detail.get("issue") in gap_types
                    for detail in (prob.problem_details if isinstance(prob.problem_details, list) else [])
                ))
            )
            if matches:
                test_patient = p
                break
    
    if not test_patient:
        print("No suitable test patient found. Skipping scenario 2.")
        return
    
    data = get_patient_data(db, test_patient.patient_key)
    print_patient_state(data, "BEFORE Sidecar Override", db)
    
    # Simulate Sidecar override: User marks plan as "resolved"
    print_subsection("Action: User clicks 'Resolved' in Sidecar")
    
    plan = data["resolution_plan"]
    user_id = uuid.uuid4()  # Mock user
    submitted_at = datetime.utcnow()
    
    # Get first gap_type from plan
    gap_type = (plan.gap_types or [""])[0] if plan.gap_types else "eligibility"
    
    # Call cascade function (what happens in sidecar.py)
    cascade_bottleneck_override(
        db=db,
        patient_context_id=test_patient.patient_context_id,
        bottleneck_factor=gap_type,
        status="resolved",
        user_id=user_id,
        submitted_at=submitted_at,
        source_layer="layer2"
    )
    
    db.commit()
    
    # Refresh and show after state
    db.refresh(test_patient)
    data_after = get_patient_data(db, test_patient.patient_key)
    print_patient_state(data_after, "AFTER Sidecar Override (Cascade Applied)", db)
    
    print("\n✓ Expected Result:")
    print("  - Layer 2: Resolution plan status = RESOLVED")
    print("  - Layer 1: Payment probability problem_details updated with override metadata")
    print("  - Layer 1: Override tracked in JSONB for audit")


def test_scenario_3_unresolved_override(db, tenant_id):
    """Scenario 3: User marks as unresolved (both layers)"""
    print_section("SCENARIO 3: User Override - Unresolved Status")
    
    # Find a patient with both Layer 1 and Layer 2 data
    patients = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).limit(10).all()
    
    test_patient = None
    for p in patients:
        prob = db.query(PaymentProbability).filter(
            PaymentProbability.patient_context_id == p.patient_context_id
        ).first()
        plan = db.query(ResolutionPlan).filter(
            ResolutionPlan.patient_context_id == p.patient_context_id,
            ResolutionPlan.status == PlanStatus.ACTIVE
        ).first()
        
        if prob and plan and prob.lowest_factor in (plan.gap_types or []):
            test_patient = p
            break
    
    if not test_patient:
        print("No suitable test patient found. Skipping scenario 3.")
        return
    
    data = get_patient_data(db, test_patient.patient_key)
    print_patient_state(data, "BEFORE Unresolved Override", db)
    
    # Simulate Mini override: User marks as "unresolved"
    print_subsection("Action: User clicks 'Unresolved' in Mini")
    
    prob = data["payment_probability"]
    user_id = uuid.uuid4()  # Mock user
    submitted_at = datetime.utcnow()
    
    # Call cascade function
    cascade_bottleneck_override(
        db=db,
        patient_context_id=test_patient.patient_context_id,
        bottleneck_factor=prob.lowest_factor,
        status="unresolved",
        user_id=user_id,
        submitted_at=submitted_at,
        source_layer="layer1"
    )
    
    db.commit()
    
    # Refresh and show after state
    db.refresh(test_patient)
    data_after = get_patient_data(db, test_patient.patient_key)
    print_patient_state(data_after, "AFTER Unresolved Override (Cascade Applied)", db)
    
    print("\n✓ Expected Result:")
    print("  - Layer 1: Problem statement unchanged")
    print("  - Layer 2: Resolution plan status = ACTIVE (not changed to RESOLVED)")
    print("  - Layer 2: Resolution notes contain override info (unresolved)")
    print("  - Layer 2: Plan remains active for further work")


def main():
    """Main entry point."""
    print("=" * 80)
    print("  CASCADE SCENARIO TESTS")
    print("  Testing bidirectional bottleneck override cascade")
    print("=" * 80)
    
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
        
        # Run scenarios
        test_scenario_1_mini_override(db, tenant.tenant_id)
        test_scenario_2_sidecar_override(db, tenant.tenant_id)
        test_scenario_3_unresolved_override(db, tenant.tenant_id)
        
        print_section("SUMMARY")
        print("All scenarios completed. Check the output above to see:")
        print("  1. Database state before and after each override")
        print("  2. How Layer 1 and Layer 2 stay in sync")
        print("  3. Cascade behavior in both directions")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
