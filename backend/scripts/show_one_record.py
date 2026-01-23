#!/usr/bin/env python3
"""
Show exactly what data exists for ONE patient - for debugging seed issues.
"""

import sys
import os
import logging

# Disable SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models import PatientContext
from app.models.probability import PaymentProbability
from app.models.resolution import ResolutionPlan, PlanStep
import json

def main():
    init_db()
    db = get_db_session()
    
    print("=" * 70)
    print("SHOWING ONE PATIENT'S DATA (Layer 1 + Layer 2)")
    print("=" * 70)
    
    # Find a patient with ACTIVE resolution plan (most interesting)
    plan = db.query(ResolutionPlan).filter(
        ResolutionPlan.status == 'active'
    ).first()
    
    if not plan:
        print("\nNo active plans found. Trying any plan...")
        plan = db.query(ResolutionPlan).first()
    
    if not plan:
        print("\nNo resolution plans found at all!")
        return
    
    patient = db.query(PatientContext).filter(
        PatientContext.patient_context_id == plan.patient_context_id
    ).first()
    
    prob = db.query(PaymentProbability).filter(
        PaymentProbability.patient_context_id == plan.patient_context_id
    ).first()
    
    steps = db.query(PlanStep).filter(
        PlanStep.plan_id == plan.plan_id
    ).order_by(PlanStep.step_order).all()
    
    print(f"\n{'='*70}")
    print("PATIENT CONTEXT")
    print("="*70)
    print(f"  patient_context_id: {patient.patient_context_id}")
    print(f"  mrn: {patient.mrn}")
    print(f"  patient_name: {patient.patient_name}")
    print(f"  attention_status: {patient.attention_status}")
    print(f"  override_color: {patient.override_color}")
    
    print(f"\n{'='*70}")
    print("LAYER 1: PAYMENT PROBABILITY")
    print("="*70)
    if prob:
        print(f"  probability_id: {prob.probability_id}")
        print(f"  overall_probability: {prob.overall_probability}")
        print(f"  lowest_factor: {prob.lowest_factor}")
        print(f"  lowest_factor_reason: {prob.lowest_factor_reason}")
        print(f"  problem_statement: {prob.problem_statement}")
        print(f"  problem_details: {json.dumps(prob.problem_details, indent=4) if prob.problem_details else 'None'}")
        print(f"\n  Factor Probabilities:")
        print(f"    attendance: {prob.prob_appointment_attendance}")
        print(f"    eligibility: {prob.prob_eligibility}")
        print(f"    coverage: {prob.prob_coverage}")
        print(f"    errors: {prob.prob_no_errors}")
    else:
        print("  NO PAYMENT PROBABILITY RECORD")
    
    print(f"\n{'='*70}")
    print("LAYER 2: RESOLUTION PLAN")
    print("="*70)
    print(f"  plan_id: {plan.plan_id}")
    print(f"  status: {plan.status}")
    print(f"  gap_types: {plan.gap_types}")
    print(f"  initial_probability: {plan.initial_probability}")
    print(f"  current_probability: {plan.current_probability}")
    print(f"  current_step_id: {plan.current_step_id}")
    
    print(f"\n  STEPS ({len(steps)} total):")
    for step in steps:
        print(f"\n  Step {step.step_order}: {step.step_code}")
        print(f"    status: {step.status}")
        print(f"    question_text: {step.question_text}")
        print(f"    factor_type: {step.factor_type}")
        print(f"    can_system_answer: {step.can_system_answer}")
        print(f"    assignable_activities: {step.assignable_activities}")
        if step.answer_options:
            print(f"    answer_options:")
            for opt in step.answer_options:
                print(f"      - {opt.get('code')}: {opt.get('label')}")
    
    print(f"\n{'='*70}")
    print("KEY ALIGNMENT CHECK")
    print("="*70)
    if prob:
        print(f"  Layer 1 lowest_factor: {prob.lowest_factor}")
        print(f"  Layer 2 gap_types: {plan.gap_types}")
        match = prob.lowest_factor in plan.gap_types if prob.lowest_factor else False
        print(f"  ALIGNED: {'YES ✓' if match else 'NO ✗'}")
    
    db.close()

if __name__ == "__main__":
    main()
