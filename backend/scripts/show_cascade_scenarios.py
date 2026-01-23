#!/usr/bin/env python3
"""
Show Cascade Scenarios - Clear before/after demonstration

Shows what happens in 3 scenarios:
1. User overrides in Mini (Layer 1 → Layer 2 cascade)
2. User overrides in Sidecar (Layer 2 → Layer 1 cascade)  
3. User marks as unresolved

Run: python scripts/show_cascade_scenarios.py
"""

import sys
import os
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models import Tenant, PatientContext, AppUser
from app.models.probability import PaymentProbability
from app.models.resolution import ResolutionPlan, PlanStatus, PlanStep
from app.services.bottleneck_cascade import cascade_bottleneck_override

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_state(data, title, db):
    """Print patient state clearly."""
    print(f"\n{title}")
    print("-" * 80)
    
    pc = data["patient_context"]
    prob = data["payment_probability"]
    plan = data["resolution_plan"]
    
    print(f"Patient Key: {pc.patient_key}")
    print(f"  ├─ Attention Status: {pc.attention_status or 'None'}")
    print(f"  ├─ Override Color: {pc.override_color or 'None'}")
    print(f"  └─ Resolved Until: {pc.resolved_until or 'None'}")
    
    if prob:
        print(f"\n📊 Layer 1 (Payment Probability):")
        print(f"  ├─ Problem Statement: {prob.problem_statement}")
        print(f"  ├─ Lowest Factor: {prob.lowest_factor}")
        print(f"  ├─ Overall Probability: {prob.overall_probability:.1%}")
        if prob.problem_details:
            overrides = [d for d in prob.problem_details if isinstance(d, dict) and d.get("type") == "user_override"]
            if overrides:
                print(f"  └─ User Overrides: {len(overrides)}")
                for ov in overrides[-2:]:
                    print(f"      • {ov.get('factor')} -> {ov.get('status')} ({ov.get('timestamp', '')[:19]})")
            else:
                print(f"  └─ Problem Details: {len(prob.problem_details)} issue(s)")
    
    if plan:
        print(f"\n📋 Layer 2 (Resolution Plan):")
        print(f"  ├─ Plan Status: {plan.status}")
        print(f"  ├─ Gap Types: {plan.gap_types}")
        print(f"  ├─ Resolved At: {plan.resolved_at or 'Not resolved'}")
        print(f"  ├─ Resolved By: {plan.resolved_by or 'None'}")
        if plan.resolution_notes:
            notes_preview = plan.resolution_notes[:80] + "..." if len(plan.resolution_notes) > 80 else plan.resolution_notes
            print(f"  └─ Resolution Notes: {notes_preview}")
        
        if db:
            steps = db.query(PlanStep).filter(PlanStep.plan_id == plan.plan_id).count()
            print(f"  └─ Total Steps: {steps}")


def get_patient_data(db, patient_key):
    """Get all relevant data for a patient."""
    patient_context = db.query(PatientContext).filter(
        PatientContext.patient_key == patient_key
    ).first()
    
    if not patient_context:
        return None
    
    prob = db.query(PaymentProbability).filter(
        PaymentProbability.patient_context_id == patient_context.patient_context_id
    ).order_by(PaymentProbability.computed_at.desc()).first()
    
    # Get active plan first, if not found, get most recent plan (could be resolved)
    plan = db.query(ResolutionPlan).filter(
        ResolutionPlan.patient_context_id == patient_context.patient_context_id,
        ResolutionPlan.status == PlanStatus.ACTIVE
    ).first()
    
    if not plan:
        # Get most recent plan (could be resolved)
        plan = db.query(ResolutionPlan).filter(
            ResolutionPlan.patient_context_id == patient_context.patient_context_id
        ).order_by(ResolutionPlan.updated_at.desc()).first()
    
    return {
        "patient_context": patient_context,
        "payment_probability": prob,
        "resolution_plan": plan,
    }


def scenario_1_mini_override(db, tenant_id, user_id):
    """Scenario 1: Mini override (Layer 1 → Layer 2)"""
    print_header("SCENARIO 1: User Override in Mini (Layer 1 → Layer 2 Cascade)")
    
    # Find suitable patient
    patients = db.query(PatientContext).filter(PatientContext.tenant_id == tenant_id).limit(20).all()
    
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
        print("❌ No suitable patient found for Scenario 1")
        return
    
    data_before = get_patient_data(db, test_patient.patient_key)
    print_state(data_before, "🔵 BEFORE: User clicks 'Resolved' in Mini", db)
    
    # Simulate override
    prob = data_before["payment_probability"]
    
    if not user_id:
        print("❌ No user provided. Skipping scenario.")
        return
    
    print(f"\n⚡ ACTION: Calling cascade_bottleneck_override()")
    print(f"   - Factor: {prob.lowest_factor}")
    print(f"   - Status: resolved")
    print(f"   - Source: layer1 (Mini)")
    print(f"   - User ID: {user_id}")
    
    cascade_bottleneck_override(
        db=db,
        patient_context_id=test_patient.patient_context_id,
        bottleneck_factor=prob.lowest_factor,
        status="resolved",
        user_id=user_id,
        submitted_at=datetime.utcnow(),
        source_layer="layer1"
    )
    db.commit()
    
    # Force refresh all objects
    db.refresh(test_patient)
    if data_before["payment_probability"]:
        db.refresh(data_before["payment_probability"])
    if data_before["resolution_plan"]:
        db.refresh(data_before["resolution_plan"])
    
    # Re-fetch to get updated state
    data_after = get_patient_data(db, test_patient.patient_key)
    print_state(data_after, "🟢 AFTER: Cascade Applied", db)
    
    print("\n✅ EXPECTED RESULTS:")
    print("   ✓ Layer 2: Plan status changed to RESOLVED")
    print("   ✓ Layer 2: resolved_at and resolved_by set")
    print("   ✓ Layer 2: resolution_notes contains override info")


def scenario_2_sidecar_override(db, tenant_id, user_id):
    """Scenario 2: Sidecar override (Layer 2 → Layer 1)"""
    print_header("SCENARIO 2: User Override in Sidecar (Layer 2 → Layer 1 Cascade)")
    
    # Find suitable patient
    patients = db.query(PatientContext).filter(PatientContext.tenant_id == tenant_id).limit(20).all()
    
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
            gap_types = plan.gap_types or []
            if gap_types:
                test_patient = p
                break
    
    if not test_patient:
        print("❌ No suitable patient found for Scenario 2")
        return
    
    data_before = get_patient_data(db, test_patient.patient_key)
    print_state(data_before, "🔵 BEFORE: User clicks 'Resolved' in Sidecar", db)
    
    # Simulate override
    plan = data_before["resolution_plan"]
    gap_type = (plan.gap_types or [""])[0] if plan.gap_types else "eligibility"
    
    if not user_id:
        print("❌ No user provided. Skipping scenario.")
        return
    
    print(f"\n⚡ ACTION: Calling cascade_bottleneck_override()")
    print(f"   - Factor: {gap_type}")
    print(f"   - Status: resolved")
    print(f"   - Source: layer2 (Sidecar)")
    
    cascade_bottleneck_override(
        db=db,
        patient_context_id=test_patient.patient_context_id,
        bottleneck_factor=gap_type,
        status="resolved",
        user_id=user_id,
        submitted_at=datetime.utcnow(),
        source_layer="layer2"
    )
    db.commit()
    
    # Force refresh all objects
    db.refresh(test_patient)
    if data_before["payment_probability"]:
        db.refresh(data_before["payment_probability"])
    if data_before["resolution_plan"]:
        db.refresh(data_before["resolution_plan"])
    
    # Re-fetch to get updated state
    data_after = get_patient_data(db, test_patient.patient_key)
    print_state(data_after, "🟢 AFTER: Cascade Applied", db)
    
    print("\n✅ EXPECTED RESULTS:")
    print("   ✓ Layer 1: problem_details updated with override metadata")
    print("   ✓ Layer 1: Override tracked in JSONB for audit")
    print("   ✓ Layer 2: Plan status changed to RESOLVED")


def scenario_3_unresolved(db, tenant_id, user_id):
    """Scenario 3: Unresolved override"""
    print_header("SCENARIO 3: User Override - Unresolved Status")
    
    # Find suitable patient
    patients = db.query(PatientContext).filter(PatientContext.tenant_id == tenant_id).limit(20).all()
    
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
        print("❌ No suitable patient found for Scenario 3")
        return
    
    data_before = get_patient_data(db, test_patient.patient_key)
    print_state(data_before, "🔵 BEFORE: User clicks 'Unresolved' in Mini", db)
    
    # Simulate override
    prob = data_before["payment_probability"]
    
    if not user_id:
        print("❌ No user provided. Skipping scenario.")
        return
    
    print(f"\n⚡ ACTION: Calling cascade_bottleneck_override()")
    print(f"   - Factor: {prob.lowest_factor}")
    print(f"   - Status: unresolved")
    print(f"   - Source: layer1 (Mini)")
    
    cascade_bottleneck_override(
        db=db,
        patient_context_id=test_patient.patient_context_id,
        bottleneck_factor=prob.lowest_factor,
        status="unresolved",
        user_id=user_id,
        submitted_at=datetime.utcnow(),
        source_layer="layer1"
    )
    db.commit()
    
    # Force refresh all objects
    db.refresh(test_patient)
    if data_before["payment_probability"]:
        db.refresh(data_before["payment_probability"])
    if data_before["resolution_plan"]:
        db.refresh(data_before["resolution_plan"])
    
    # Re-fetch to get updated state
    data_after = get_patient_data(db, test_patient.patient_key)
    print_state(data_after, "🟢 AFTER: Cascade Applied", db)
    
    print("\n✅ EXPECTED RESULTS:")
    print("   ✓ Layer 2: Plan status remains ACTIVE (not changed to RESOLVED)")
    print("   ✓ Layer 2: resolution_notes contains override info (unresolved)")
    print("   ✓ Layer 2: Plan stays active for further work")


def main():
    print("=" * 80)
    print("  CASCADE SCENARIO DEMONSTRATION")
    print("  Showing before/after states for 3 scenarios")
    print("=" * 80)
    
    init_db()
    db = get_db_session()
    
    try:
        tenant = db.query(Tenant).filter(Tenant.tenant_id == DEFAULT_TENANT_ID).first()
        if not tenant:
            print("\nERROR: No tenant found. Please run seed_data.py first.")
            return
        
        print(f"\nUsing tenant: {tenant.name}")
        
        # Get a real user for the tests
        user = db.query(AppUser).filter(AppUser.tenant_id == tenant.tenant_id).first()
        if not user:
            print("❌ ERROR: No users found. Please run seed_user_data.py first.")
            return
        
        user_id = user.user_id
        print(f"Using user: {user.email} (id: {user_id})")
        
        scenario_1_mini_override(db, tenant.tenant_id, user_id)
        scenario_2_sidecar_override(db, tenant.tenant_id, user_id)
        scenario_3_unresolved(db, tenant.tenant_id, user_id)
        
        print_header("SUMMARY")
        print("All 3 scenarios completed!")
        print("\nKey Takeaways:")
        print("  1. Mini override (Layer 1) → cascades to Layer 2 (resolution plan)")
        print("  2. Sidecar override (Layer 2) → cascades to Layer 1 (payment probability)")
        print("  3. Unresolved status keeps plan active but tracks override")
        print("  4. Both layers stay in sync through bottleneck matching")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
