#!/usr/bin/env python3
"""
Clear Cascade Test - Shows 2-3 scenarios with full before/after states
"""

import sys
import os
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models import Tenant, PatientContext, AppUser
from app.models.probability import PaymentProbability
from app.models.resolution import ResolutionPlan, PlanStatus
from app.services.bottleneck_cascade import cascade_bottleneck_override

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def print_scenario_header(num, title):
    print("\n" + "=" * 80)
    print(f"SCENARIO {num}: {title}")
    print("=" * 80)


def print_state(title, pc, prob, plan):
    print(f"\n{title}")
    print("-" * 80)
    print(f"Patient: {pc.patient_key}")
    print(f"  Attention Status: {pc.attention_status or 'None'}")
    print(f"  Override Color: {pc.override_color or 'None'}")
    
    if prob:
        print(f"\n📊 LAYER 1 (Payment Probability):")
        print(f"  Problem Statement: {prob.problem_statement}")
        print(f"  Lowest Factor: {prob.lowest_factor}")
        print(f"  Overall Probability: {prob.overall_probability:.1%}")
        if prob.problem_details:
            overrides = [d for d in prob.problem_details if isinstance(d, dict) and d.get("type") == "user_override"]
            if overrides:
                print(f"  User Overrides in problem_details: {len(overrides)}")
                for ov in overrides:
                    print(f"    → {ov.get('factor')} marked as {ov.get('status')}")
    
    if plan:
        print(f"\n📋 LAYER 2 (Resolution Plan):")
        print(f"  Plan Status: {plan.status}")
        print(f"  Gap Types: {plan.gap_types}")
        print(f"  Resolved At: {plan.resolved_at or 'Not resolved'}")
        print(f"  Resolved By: {plan.resolved_by or 'None'}")
        if plan.resolution_notes:
            print(f"  Resolution Notes: {plan.resolution_notes[:100]}..." if len(plan.resolution_notes) > 100 else f"  Resolution Notes: {plan.resolution_notes}")


def main():
    print("=" * 80)
    print("CASCADE TEST - 3 SCENARIOS")
    print("=" * 80)
    
    init_db()
    db = get_db_session()
    
    try:
        tenant = db.query(Tenant).filter(Tenant.tenant_id == DEFAULT_TENANT_ID).first()
        user = db.query(AppUser).filter(AppUser.tenant_id == tenant.tenant_id).first()
        
        if not user:
            print("ERROR: No users found")
            return
        
        user_id = user.user_id
        
        # SCENARIO 1: Mini Override (Layer 1 → Layer 2)
        print_scenario_header(1, "User Override in Mini (Layer 1 → Layer 2 Cascade)")
        
        # Find patient with matching Layer 1 and Layer 2
        patients = db.query(PatientContext).filter(PatientContext.tenant_id == tenant.tenant_id).limit(30).all()
        test_patient_1 = None
        
        for p in patients:
            prob = db.query(PaymentProbability).filter(
                PaymentProbability.patient_context_id == p.patient_context_id
            ).first()
            plan = db.query(ResolutionPlan).filter(
                ResolutionPlan.patient_context_id == p.patient_context_id,
                ResolutionPlan.status == PlanStatus.ACTIVE
            ).first()
            
            if prob and plan and prob.lowest_factor in (plan.gap_types or []):
                test_patient_1 = p
                break
        
        if test_patient_1:
            prob = db.query(PaymentProbability).filter(
                PaymentProbability.patient_context_id == test_patient_1.patient_context_id
            ).first()
            plan_before = db.query(ResolutionPlan).filter(
                ResolutionPlan.patient_context_id == test_patient_1.patient_context_id,
                ResolutionPlan.status == PlanStatus.ACTIVE
            ).first()
            
            print_state("🔵 BEFORE: User clicks 'Resolved' in Mini", test_patient_1, prob, plan_before)
            
            print(f"\n⚡ ACTION: cascade_bottleneck_override()")
            print(f"   Factor: {prob.lowest_factor}")
            print(f"   Status: resolved")
            print(f"   Source: layer1")
            
            cascade_bottleneck_override(
                db=db,
                patient_context_id=test_patient_1.patient_context_id,
                bottleneck_factor=prob.lowest_factor,
                status="resolved",
                user_id=user_id,
                submitted_at=datetime.utcnow(),
                source_layer="layer1"
            )
            db.commit()
            
            # Refresh and re-fetch
            db.refresh(test_patient_1)
            if prob:
                db.refresh(prob)
            if plan_before:
                db.refresh(plan_before)
            
            plan_after = db.query(ResolutionPlan).filter(
                ResolutionPlan.plan_id == plan_before.plan_id
            ).first()
            
            print_state("🟢 AFTER: Cascade Applied", test_patient_1, prob, plan_after)
            
            print("\n✅ VERIFICATION:")
            if plan_after.status == PlanStatus.RESOLVED:
                print("   ✓ Layer 2: Plan status = RESOLVED")
            else:
                print(f"   ✗ Layer 2: Plan status = {plan_after.status} (expected RESOLVED)")
            if plan_after.resolved_at:
                print("   ✓ Layer 2: resolved_at is set")
            if plan_after.resolved_by:
                print("   ✓ Layer 2: resolved_by is set")
            if plan_after.resolution_notes and "User override (Layer 1)" in plan_after.resolution_notes:
                print("   ✓ Layer 2: resolution_notes contains override info")
        
        # SCENARIO 2: Sidecar Override (Layer 2 → Layer 1)
        print_scenario_header(2, "User Override in Sidecar (Layer 2 → Layer 1 Cascade)")
        
        test_patient_2 = None
        for p in patients:
            if p.patient_context_id == test_patient_1.patient_context_id:
                continue
            prob = db.query(PaymentProbability).filter(
                PaymentProbability.patient_context_id == p.patient_context_id
            ).first()
            plan = db.query(ResolutionPlan).filter(
                ResolutionPlan.patient_context_id == p.patient_context_id,
                ResolutionPlan.status == PlanStatus.ACTIVE
            ).first()
            
            if prob and plan and plan.gap_types:
                # Check if gap_type matches prob's lowest_factor or exists in problem_details
                gap_types = plan.gap_types or []
                matches = (
                    prob.lowest_factor in gap_types or
                    (prob.problem_details and any(
                        detail.get("issue") in gap_types
                        for detail in (prob.problem_details if isinstance(prob.problem_details, list) else [])
                    ))
                )
                if matches:
                    test_patient_2 = p
                    break
        
        if test_patient_2:
            prob_before = db.query(PaymentProbability).filter(
                PaymentProbability.patient_context_id == test_patient_2.patient_context_id
            ).order_by(PaymentProbability.computed_at.desc()).first()
            plan = db.query(ResolutionPlan).filter(
                ResolutionPlan.patient_context_id == test_patient_2.patient_context_id,
                ResolutionPlan.status == PlanStatus.ACTIVE
            ).first()
            
            print_state("🔵 BEFORE: User clicks 'Resolved' in Sidecar", test_patient_2, prob_before, plan)
            
            gap_type = (plan.gap_types or [""])[0] if plan.gap_types else "eligibility"
            
            print(f"\n⚡ ACTION: cascade_bottleneck_override()")
            print(f"   Factor: {gap_type}")
            print(f"   Status: resolved")
            print(f"   Source: layer2")
            
            cascade_bottleneck_override(
                db=db,
                patient_context_id=test_patient_2.patient_context_id,
                bottleneck_factor=gap_type,
                status="resolved",
                user_id=user_id,
                submitted_at=datetime.utcnow(),
                source_layer="layer2"
            )
            db.commit()
            
            # Refresh and re-fetch
            db.refresh(test_patient_2)
            if prob_before:
                db.refresh(prob_before)
            if plan:
                db.refresh(plan)
            
            prob_after = db.query(PaymentProbability).filter(
                PaymentProbability.probability_id == prob_before.probability_id
            ).first()
            plan_after = db.query(ResolutionPlan).filter(
                ResolutionPlan.plan_id == plan.plan_id
            ).first()
            
            print_state("🟢 AFTER: Cascade Applied", test_patient_2, prob_after, plan_after)
            
            print("\n✅ VERIFICATION:")
            if prob_after.problem_details:
                overrides = [d for d in prob_after.problem_details if isinstance(d, dict) and d.get("type") == "user_override"]
                if overrides:
                    print(f"   ✓ Layer 1: problem_details contains {len(overrides)} override(s)")
                    for ov in overrides:
                        print(f"     → {ov.get('factor')} marked as {ov.get('status')}")
                else:
                    print("   ✗ Layer 1: No override found in problem_details")
            if plan_after.status == PlanStatus.RESOLVED:
                print("   ✓ Layer 2: Plan status = RESOLVED")
            else:
                print(f"   ✗ Layer 2: Plan status = {plan_after.status} (expected RESOLVED)")
        
        # SCENARIO 3: Unresolved
        print_scenario_header(3, "User Override - Unresolved Status")
        
        test_patient_3 = None
        for p in patients:
            if p.patient_context_id in [test_patient_1.patient_context_id, test_patient_2.patient_context_id]:
                continue
            prob = db.query(PaymentProbability).filter(
                PaymentProbability.patient_context_id == p.patient_context_id
            ).first()
            plan = db.query(ResolutionPlan).filter(
                ResolutionPlan.patient_context_id == p.patient_context_id,
                ResolutionPlan.status == PlanStatus.ACTIVE
            ).first()
            
            if prob and plan and prob.lowest_factor in (plan.gap_types or []):
                test_patient_3 = p
                break
        
        if test_patient_3:
            prob = db.query(PaymentProbability).filter(
                PaymentProbability.patient_context_id == test_patient_3.patient_context_id
            ).first()
            plan_before = db.query(ResolutionPlan).filter(
                ResolutionPlan.patient_context_id == test_patient_3.patient_context_id,
                ResolutionPlan.status == PlanStatus.ACTIVE
            ).first()
            
            print_state("🔵 BEFORE: User clicks 'Unresolved' in Mini", test_patient_3, prob, plan_before)
            
            print(f"\n⚡ ACTION: cascade_bottleneck_override()")
            print(f"   Factor: {prob.lowest_factor}")
            print(f"   Status: unresolved")
            print(f"   Source: layer1")
            
            cascade_bottleneck_override(
                db=db,
                patient_context_id=test_patient_3.patient_context_id,
                bottleneck_factor=prob.lowest_factor,
                status="unresolved",
                user_id=user_id,
                submitted_at=datetime.utcnow(),
                source_layer="layer1"
            )
            db.commit()
            
            # Refresh and re-fetch
            db.refresh(test_patient_3)
            if prob:
                db.refresh(prob)
            if plan_before:
                db.refresh(plan_before)
            
            plan_after = db.query(ResolutionPlan).filter(
                ResolutionPlan.plan_id == plan_before.plan_id
            ).first()
            
            print_state("🟢 AFTER: Cascade Applied", test_patient_3, prob, plan_after)
            
            print("\n✅ VERIFICATION:")
            if plan_after.status == PlanStatus.ACTIVE:
                print("   ✓ Layer 2: Plan status = ACTIVE (not changed to RESOLVED)")
            else:
                print(f"   ✗ Layer 2: Plan status = {plan_after.status} (expected ACTIVE)")
            if plan_after.resolution_notes and "unresolved" in plan_after.resolution_notes:
                print("   ✓ Layer 2: resolution_notes contains unresolved override")
        
        print("\n" + "=" * 80)
        print("ALL SCENARIOS COMPLETED")
        print("=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
