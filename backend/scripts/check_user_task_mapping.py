#!/usr/bin/env python3
"""
Script to check user-task mappings in the database.

Run this to verify:
1. Which users exist and their activities
2. Which tasks exist and their assignable_activities
3. Which users can see which tasks
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from app.db.postgres import get_db_session
from app.models.tenant import AppUser, Role
from app.models.activity import UserActivity, Activity
from app.models.resolution import PlanStep, ResolutionPlan
from collections import defaultdict

def main():
    db = get_db_session()
    
    print("=" * 80)
    print("USER-TASK MAPPING ANALYSIS")
    print("=" * 80)
    print()
    
    # Get all users with their activities
    print("=== USERS AND THEIR ACTIVITIES ===")
    print()
    users_data = []
    users = db.query(AppUser).filter(AppUser.status == 'active').all()
    
    for user in users:
        role = db.query(Role).filter(Role.role_id == user.role_id).first() if user.role_id else None
        user_activities = db.query(UserActivity).filter(UserActivity.user_id == user.user_id).all()
        activity_codes = [ua.activity.activity_code for ua in user_activities if ua.activity]
        
        users_data.append({
            'user_id': str(user.user_id),
            'name': user.display_name or user.email,
            'email': user.email,
            'role': role.name if role else 'No role',
            'role_id': str(user.role_id) if user.role_id else None,
            'activities': activity_codes
        })
        
        print(f"User: {user.display_name or user.email}")
        print(f"  Email: {user.email}")
        print(f"  Role: {role.name if role else 'No role'}")
        print(f"  Activities ({len(activity_codes)}): {', '.join(activity_codes) if activity_codes else 'NONE'}")
        print()
    
    # Get all plan steps with their assignable_activities
    print("=" * 80)
    print("=== PLAN STEPS AND ASSIGNABLE ACTIVITIES ===")
    print()
    
    steps_data = []
    steps = db.query(PlanStep).join(ResolutionPlan).filter(
        PlanStep.status.in_(['current', 'pending'])
    ).limit(30).all()
    
    for step in steps:
        steps_data.append({
            'step_id': str(step.step_id),
            'step_code': step.step_code,
            'question': step.question_text[:80] + '...' if step.question_text and len(step.question_text) > 80 else (step.question_text or 'No question'),
            'factor_type': step.factor_type,
            'assignable_activities': step.assignable_activities or []
        })
        
        print(f"Step: {step.step_code}")
        print(f"  Question: {step.question_text[:80] if step.question_text else 'No question'}")
        print(f"  Factor Type: {step.factor_type}")
        print(f"  Assignable Activities: {', '.join(step.assignable_activities) if step.assignable_activities else 'NONE'}")
        print()
    
    # Create mapping matrix
    print("=" * 80)
    print("=== USER-TASK MATCHING MATRIX ===")
    print()
    print("Shows which users can see which tasks (based on activity overlap)")
    print()
    
    # Header
    print(f"{'User':<25} {'Role':<15} {'# Activities':<12} {'# Matching Tasks':<18}")
    print("-" * 80)
    
    for user_info in users_data:
        matching_count = 0
        matching_steps = []
        
        for step_info in steps_data:
            user_acts = set(user_info['activities'])
            step_acts = set(step_info['assignable_activities'])
            
            # Check if user is admin (by role name)
            is_admin = user_info['role'].lower() == 'admin'
            
            if is_admin or (user_acts and step_acts and user_acts.intersection(step_acts)):
                matching_count += 1
                matching_steps.append(step_info['step_code'])
        
        role_display = user_info['role'][:14]
        activities_count = len(user_info['activities'])
        print(f"{user_info['name']:<25} {role_display:<15} {activities_count:<12} {matching_count:<18}")
    
    print()
    print("=" * 80)
    print("=== DETAILED MATCHING FOR EACH USER ===")
    print()
    
    for user_info in users_data:
        is_admin = user_info['role'].lower() == 'admin'
        print(f"User: {user_info['name']} ({user_info['email']})")
        print(f"  Role: {user_info['role']}")
        print(f"  Is Admin: {is_admin}")
        print(f"  User Activities: {', '.join(user_info['activities']) if user_info['activities'] else 'NONE'}")
        print()
        
        matching_steps = []
        for step_info in steps_data:
            user_acts = set(user_info['activities'])
            step_acts = set(step_info['assignable_activities'])
            
            if is_admin:
                matching_steps.append({
                    'step_code': step_info['step_code'],
                    'question': step_info['question'],
                    'reason': 'Admin - sees all tasks'
                })
            elif user_acts and step_acts:
                overlap = user_acts.intersection(step_acts)
                if overlap:
                    matching_steps.append({
                        'step_code': step_info['step_code'],
                        'question': step_info['question'],
                        'reason': f'Activity overlap: {", ".join(overlap)}'
                    })
        
        if matching_steps:
            print(f"  Can see {len(matching_steps)} task(s):")
            for match in matching_steps[:10]:  # Limit to first 10
                print(f"    - {match['step_code']}: {match['question'][:60]}...")
                print(f"      Reason: {match['reason']}")
            if len(matching_steps) > 10:
                print(f"    ... and {len(matching_steps) - 10} more")
        else:
            print(f"  ⚠️  Cannot see any tasks (no activity overlap)")
        print()
    
    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
