#!/usr/bin/env python3
"""
Debug script to fetch actual data for patient and Alex Admin
to understand why Step 3 ("Waiting on another team member") was triggered.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session
from app.models import AppUser, Role, PatientContext, PatientSnapshot
from app.models.resolution import ResolutionPlan, PlanStep, PlanStatus, StepStatus
from app.models.activity import UserActivity, Activity
from app.modes.mini import _step_matches_user_activities, _map_factor_to_activities

def debug_patient_and_user():
    db = get_db_session()
    
    # Find patient "Janet Morris" or "Complex Case" with ID ending in 0014
    print("=" * 80)
    print("FINDING PATIENT")
    print("=" * 80)
    
    # Try to find by snapshot display_name
    snapshot = db.query(PatientSnapshot).filter(
        PatientSnapshot.display_name.like("%Janet Morris%")
    ).first()
    
    if not snapshot:
        # Try "Complex Case"
        snapshot = db.query(PatientSnapshot).filter(
            PatientSnapshot.display_name.like("%Complex%")
        ).first()
    
    if not snapshot:
        print("ERROR: Patient not found")
        return
    
    patient_context = snapshot.patient_context
    print(f"Patient Context ID: {patient_context.patient_context_id}")
    print(f"Patient Key: {patient_context.patient_key}")
    print(f"Display Name: {snapshot.display_name}")
    print(f"ID Masked: {snapshot.id_masked}")
    
    # Find Alex Admin
    print("\n" + "=" * 80)
    print("FINDING ALEX ADMIN USER")
    print("=" * 80)
    
    alex = db.query(AppUser).filter(
        AppUser.display_name == "Alex Admin"
    ).first()
    
    if not alex:
        alex = db.query(AppUser).filter(
            AppUser.email == "admin@demo.clinic"
        ).first()
    
    if not alex:
        print("ERROR: Alex Admin not found")
        return
    
    print(f"User ID: {alex.user_id}")
    print(f"Display Name: {alex.display_name}")
    print(f"Email: {alex.email}")
    print(f"Role ID: {alex.role_id}")
    
    # Check admin status
    if alex.role_id:
        role = db.query(Role).filter(Role.role_id == alex.role_id).first()
        if role:
            print(f"Role Name: {role.name}")
            print(f"Is Admin (role.name.lower() == 'admin'): {role.name.lower() == 'admin'}")
        else:
            print("ERROR: Role not found")
    else:
        print("ERROR: User has no role_id")
    
    # Get user activities
    print("\n" + "=" * 80)
    print("ALEX ADMIN USER ACTIVITIES")
    print("=" * 80)
    
    user_activities = db.query(UserActivity).filter(
        UserActivity.user_id == alex.user_id
    ).all()
    
    activity_codes = []
    for ua in user_activities:
        activity = db.query(Activity).filter(Activity.activity_id == ua.activity_id).first()
        if activity:
            activity_codes.append(activity.activity_code)
            print(f"  - {activity.activity_code} ({activity.label})")
    
    print(f"\nTotal Activities: {len(activity_codes)}")
    print(f"Activity Codes: {activity_codes}")
    
    # Get resolution plan
    print("\n" + "=" * 80)
    print("RESOLUTION PLAN")
    print("=" * 80)
    
    plan = db.query(ResolutionPlan).filter(
        ResolutionPlan.patient_context_id == patient_context.patient_context_id,
        ResolutionPlan.status.in_([PlanStatus.ACTIVE, PlanStatus.RESOLVED])
    ).order_by(
        ResolutionPlan.status.asc(),
        ResolutionPlan.updated_at.desc()
    ).first()
    
    if not plan:
        print("ERROR: No resolution plan found")
        return
    
    print(f"Plan ID: {plan.plan_id}")
    print(f"Status: {plan.status}")
    print(f"Gap Types: {plan.gap_types}")
    
    # Get all steps
    print("\n" + "=" * 80)
    print("PLAN STEPS")
    print("=" * 80)
    
    steps = db.query(PlanStep).filter(PlanStep.plan_id == plan.plan_id).all()
    print(f"Total Steps: {len(steps)}")
    
    total_pending_steps = 0
    actions_for_user = 0
    
    for step in steps:
        print(f"\nStep: {step.step_code}")
        print(f"  Status: {step.status}")
        print(f"  Question: {step.question_text}")
        print(f"  Factor Type: {step.factor_type}")
        print(f"  Assignable Activities: {step.assignable_activities}")
        
        if step.status in [StepStatus.CURRENT, StepStatus.PENDING]:
            total_pending_steps += 1
            step_matches = _step_matches_user_activities(step, activity_codes)
            
            if step_matches:
                actions_for_user += 1
                # Show why it matched
                step_activities = step.assignable_activities or []
                direct_overlap = [a for a in step_activities if a in activity_codes] if step_activities else []
                factor_activities = _map_factor_to_activities(step.factor_type) if step.factor_type else []
                factor_overlap = [a for a in factor_activities if a in activity_codes] if factor_activities else []
                
                if direct_overlap:
                    print(f"  → MATCHES (Direct activity overlap: {direct_overlap})")
                elif factor_overlap:
                    print(f"  → MATCHES (Factor-based match: {step.factor_type} → {factor_overlap})")
                else:
                    # Handle legacy handle_* codes
                    handle_match = False
                    for activity in step_activities:
                        if activity.startswith("handle_"):
                            factor = activity.replace("handle_", "")
                            mapped = _map_factor_to_activities(factor)
                            mapped_overlap = [a for a in mapped if a in activity_codes]
                            if mapped_overlap:
                                print(f"  → MATCHES (Legacy handle_* code: {activity} → {mapped_overlap})")
                                handle_match = True
                                break
                    if not handle_match:
                        print(f"  → MATCHES (Unknown reason)")
            else:
                print(f"  → NO MATCH")
        elif step.status == StepStatus.PENDING:
            total_pending_steps += 1
    
    # Calculate other_role_tasks
    print("\n" + "=" * 80)
    print("CALCULATION RESULTS")
    print("=" * 80)
    
    print(f"user_activities: {activity_codes}")
    print(f"total_pending_steps: {total_pending_steps}")
    print(f"actions_for_user: {actions_for_user}")
    
    other_role_tasks = (total_pending_steps - actions_for_user) if (
        activity_codes and len(activity_codes) > 0 and 
        actions_for_user < total_pending_steps
    ) else 0
    
    print(f"other_role_tasks: {other_role_tasks}")
    
    print("\n" + "=" * 80)
    print("WHY STEP 3 WAS TRIGGERED")
    print("=" * 80)
    
    if other_role_tasks > 0 and actions_for_user == 0:
        print("✓ Step 3 TRIGGERED: 'Waiting on another team member'")
        print(f"  Reason: other_role_tasks={other_role_tasks} > 0 AND actions_for_user={actions_for_user} == 0")
    else:
        print("✗ Step 3 NOT TRIGGERED")
        print(f"  other_role_tasks={other_role_tasks}, actions_for_user={actions_for_user}")
    
    if actions_for_user == 0:
        print(f"\n  → No steps matched user activities")
        if not activity_codes:
            print(f"  → User has no activities configured!")
        else:
            print(f"  → User has {len(activity_codes)} activities but none matched step activities")
            print(f"  → Check factor mapping: eligibility → {_map_factor_to_activities('eligibility')}")
            print(f"  → Check factor mapping: coverage → {_map_factor_to_activities('coverage')}")
            print(f"  → Check factor mapping: attendance → {_map_factor_to_activities('attendance')}")
    
    db.close()

if __name__ == "__main__":
    debug_patient_and_user()
