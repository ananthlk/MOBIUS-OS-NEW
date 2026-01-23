#!/usr/bin/env python3
"""
CLEAN START: Clear all patient data and seed ONE patient with full 6-layer architecture.

Layers:
1. PaymentProbability - The bottleneck (what Mini shows)
2. ResolutionPlan - The plan to resolve the bottleneck
3. PlanStep - Mitigations with rationale linking to evidence
4. Evidence - Extracted facts
5. SourceDocument - Catalog of documents/transactions
6. RawData - Actual raw content

This gives us a clean slate to test the full Mini/Sidecar flow.
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
from app.models import PatientContext, PatientSnapshot, Tenant, AppUser
from app.models.probability import PaymentProbability, TaskInstance
from app.models.resolution import (
    ResolutionPlan, PlanStep, StepAnswer, PlanNote,
    PlanStatus, StepStatus, StepType, InputType, FactorType
)
from app.models.evidence import RawData, SourceDocument, Evidence, FactSourceLink, PlanStepFactLink
from app.models.patient_ids import PatientId
from app.models.mock_emr import MockEmrRecord
from app.models.event_log import EventLog
from app.models.response import SystemResponse, MiniSubmission
from app.models.sidecar import Milestone, MilestoneHistory, MilestoneSubstep, UserAlert, UserOwnedTask


def clear_all_patient_data(db):
    """Clear all patient-related data but keep base config (tenant, users, roles)."""
    
    print("\n--- Clearing Patient Data ---")
    
    # Order matters due to foreign keys - clear from bottom up
    
    # Clear join tables first
    count = db.query(PlanStepFactLink).delete()
    print(f"  Deleted {count} plan_step_fact_links")
    
    count = db.query(FactSourceLink).delete()
    print(f"  Deleted {count} fact_source_links")
    
    # Clear evidence layers (4, 5, 6)
    count = db.query(Evidence).delete()
    print(f"  Deleted {count} evidence records (Layer 4)")
    
    count = db.query(SourceDocument).delete()
    print(f"  Deleted {count} source_documents (Layer 5)")
    
    count = db.query(RawData).delete()
    print(f"  Deleted {count} raw_data records (Layer 6)")
    
    # Clear resolution plan related
    count = db.query(StepAnswer).delete()
    print(f"  Deleted {count} step_answers")
    
    count = db.query(PlanNote).delete()
    print(f"  Deleted {count} plan_notes")
    
    count = db.query(PlanStep).delete()
    print(f"  Deleted {count} plan_steps (Layer 3)")
    
    count = db.query(ResolutionPlan).delete()
    print(f"  Deleted {count} resolution_plans (Layer 2)")
    
    # Clear probability related
    count = db.query(TaskInstance).delete()
    print(f"  Deleted {count} task_instances")
    
    count = db.query(PaymentProbability).delete()
    print(f"  Deleted {count} payment_probabilities (Layer 1)")
    
    # Clear mock EMR
    count = db.query(MockEmrRecord).delete()
    print(f"  Deleted {count} mock_emr_records")
    
    # Clear patient IDs
    count = db.query(PatientId).delete()
    print(f"  Deleted {count} patient_ids")
    
    # Clear patient snapshots
    count = db.query(PatientSnapshot).delete()
    print(f"  Deleted {count} patient_snapshots")
    
    # Clear event logs (have FK to patient_context)
    count = db.query(EventLog).delete()
    print(f"  Deleted {count} event_logs")
    
    # Clear system responses (have FK to patient_context)
    count = db.query(SystemResponse).delete()
    print(f"  Deleted {count} system_responses")
    
    # Clear mini submissions (have FK to patient_context)
    count = db.query(MiniSubmission).delete()
    print(f"  Deleted {count} mini_submissions")
    
    # Clear sidecar tables (have FK to patient_context)
    count = db.query(MilestoneSubstep).delete()
    print(f"  Deleted {count} milestone_substeps")
    
    count = db.query(MilestoneHistory).delete()
    print(f"  Deleted {count} milestone_history")
    
    count = db.query(Milestone).delete()
    print(f"  Deleted {count} milestones")
    
    count = db.query(UserAlert).delete()
    print(f"  Deleted {count} user_alerts")
    
    count = db.query(UserOwnedTask).delete()
    print(f"  Deleted {count} user_owned_tasks")
    
    # Clear patient contexts
    count = db.query(PatientContext).delete()
    print(f"  Deleted {count} patient_contexts")
    
    db.commit()
    print("  All patient data cleared!")


def create_test_patient(db, tenant_id):
    """Create ONE test patient with all necessary data."""
    
    print("\n--- Creating Test Patient ---")
    
    # Create patient context
    patient = PatientContext(
        tenant_id=tenant_id,
        patient_key="test_patient_001",
    )
    db.add(patient)
    db.flush()
    
    # Create patient snapshot (what displays in UI)
    snapshot = PatientSnapshot(
        patient_context_id=patient.patient_context_id,
        display_name="John Smith",
        id_label="MRN",
        id_masked="****1234",
        dob=date(1985, 6, 15),
        verified=True,
        data_complete=True,
    )
    db.add(snapshot)
    
    # Create patient ID (for MRN lookup)
    patient_id = PatientId(
        patient_context_id=patient.patient_context_id,
        id_type="mrn",
        id_value="TEST-1234",
        source_system="mock_emr",
        is_primary=True,
    )
    db.add(patient_id)
    
    # Create mock EMR record
    emr = MockEmrRecord(
        patient_context_id=patient.patient_context_id,
        allergies=["Penicillin"],
        medications=[{"name": "Metformin", "dose": "500mg", "frequency": "BID"}],
        vitals={"bp": "120/80", "hr": 72, "temp": 98.6},
        primary_care_provider="Dr. Jane Wilson",
        blood_type="A+",
    )
    db.add(emr)
    
    db.flush()
    
    print(f"  patient_context_id: {patient.patient_context_id}")
    print(f"  display_name: John Smith")
    print(f"  MRN: TEST-1234")
    
    return patient


def seed_layer6(db, tenant_id):
    """
    LAYER 6: Raw Data
    
    The actual raw content from source systems.
    """
    
    print("\n--- Seeding Layer 6: RawData ---")
    
    # Raw 271 response from Availity (45 days ago)
    raw_271 = RawData(
        tenant_id=tenant_id,
        content_type="edi_271",
        source_system="availity",
        collected_at=datetime.utcnow() - timedelta(days=45),
        raw_content={
            "transaction_id": "271-ABC123",
            "response_code": "AAA",  # Active coverage
            "subscriber": {
                "id": "BCB-987654",
                "name": "SMITH, JOHN",
                "dob": "1985-06-15"
            },
            "payer": {
                "name": "BlueCross BlueShield",
                "id": "BCBS-IL"
            },
            "coverage": {
                "status": "active",
                "effective_date": "2025-01-01",
                "term_date": "2025-12-31"
            },
            "benefits": {
                "copay": "$25",
                "deductible": "$500",
                "deductible_met": "$350"
            }
        }
    )
    db.add(raw_271)
    
    # Patient call notes (30 days ago)
    raw_notes = RawData(
        tenant_id=tenant_id,
        content_type="text",
        source_system="phone_system",
        collected_at=datetime.utcnow() - timedelta(days=30),
        raw_content={
            "call_id": "CALL-789",
            "call_date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "staff_member": "Jane Doe",
            "transcript": "Patient called to confirm appointment for next week. "
                         "Mentioned starting new job next month at Acme Corp. "
                         "May need to update insurance info after job change."
        }
    )
    db.add(raw_notes)
    
    db.flush()
    
    print(f"  Created 2 raw_data records:")
    print(f"    - 271 response from Availity (45 days ago)")
    print(f"    - Patient call notes (30 days ago)")
    
    return raw_271, raw_notes


def seed_layer5(db, tenant_id, raw_271, raw_notes):
    """
    LAYER 5: Source Documents
    
    Catalog of documents/transactions.
    One source document can produce multiple facts.
    """
    
    print("\n--- Seeding Layer 5: SourceDocument ---")
    
    # 271 eligibility check document
    doc_271 = SourceDocument(
        tenant_id=tenant_id,
        raw_id=raw_271.raw_id,
        document_type="eligibility_check",
        document_label="271 from Availity - " + (datetime.utcnow() - timedelta(days=45)).strftime("%Y-%m-%d"),
        source_system="availity",
        transaction_id="271-ABC123",
        document_date=datetime.utcnow() - timedelta(days=45),
        trust_score=0.95  # High trust - API response
    )
    db.add(doc_271)
    
    # Patient call notes document
    doc_call = SourceDocument(
        tenant_id=tenant_id,
        raw_id=raw_notes.raw_id,
        document_type="patient_note",
        document_label="Patient call - " + (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"),
        source_system="phone_system",
        transaction_id="CALL-789",
        document_date=datetime.utcnow() - timedelta(days=30),
        trust_score=0.80  # Medium trust - self-reported
    )
    db.add(doc_call)
    
    db.flush()
    
    print(f"  Created 2 source_documents:")
    print(f"    - 271 eligibility check (trust: 0.95)")
    print(f"    - Patient call notes (trust: 0.80)")
    
    return doc_271, doc_call


def seed_layer4(db, patient_context_id, doc_271, doc_call):
    """
    LAYER 4: Evidence (Facts)
    
    Multiple facts can come from a single source document.
    These facts inform the probability calculations and step rationale.
    """
    
    print("\n--- Seeding Layer 4: Evidence ---")
    
    # From the 271 document, we extract 2 facts:
    
    # Fact 1: Coverage was active (positive)
    fact_coverage = Evidence(
        patient_context_id=patient_context_id,
        source_id=doc_271.source_id,
        factor_type="eligibility",
        fact_type="coverage_status",
        fact_summary="Coverage was active as of 45 days ago",
        fact_data={
            "status": "active",
            "payer": "BlueCross BlueShield",
            "policy_id": "BCB-987654",
            "effective_date": "2025-01-01",
            "term_date": "2025-12-31",
            "copay": "$25"
        },
        impact_direction="positive",
        impact_weight=0.3
    )
    db.add(fact_coverage)
    
    # Fact 2: Check is stale (negative)
    fact_stale = Evidence(
        patient_context_id=patient_context_id,
        source_id=doc_271.source_id,
        factor_type="eligibility",
        fact_type="staleness",
        fact_summary="Eligibility check is 45 days old - may be stale",
        fact_data={
            "check_date": (datetime.utcnow() - timedelta(days=45)).isoformat(),
            "days_ago": 45,
            "threshold_days": 30,
            "exceeds_threshold": True
        },
        is_stale=True,
        stale_after=datetime.utcnow() - timedelta(days=15),  # Was stale 15 days ago
        impact_direction="negative",
        impact_weight=0.5
    )
    db.add(fact_stale)
    
    # From the patient call, we extract 1 fact:
    
    # Fact 3: Job change mentioned (negative)
    fact_job = Evidence(
        patient_context_id=patient_context_id,
        source_id=doc_call.source_id,
        factor_type="eligibility",
        fact_type="employment_change",
        fact_summary="Patient mentioned starting new job - may affect coverage",
        fact_data={
            "note_date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "concern": "job_change",
            "current_employer": "Unknown",
            "new_employer": "Acme Corp",
            "quote": "starting new job next month"
        },
        impact_direction="negative",
        impact_weight=0.6
    )
    db.add(fact_job)
    
    db.flush()
    
    # Create FactSourceLink entries (join table)
    link1 = FactSourceLink(
        fact_id=fact_coverage.evidence_id,
        source_id=doc_271.source_id,
        role="primary",
        confidence=0.95
    )
    db.add(link1)
    
    link2 = FactSourceLink(
        fact_id=fact_stale.evidence_id,
        source_id=doc_271.source_id,
        role="primary",
        confidence=0.95
    )
    db.add(link2)
    
    link3 = FactSourceLink(
        fact_id=fact_job.evidence_id,
        source_id=doc_call.source_id,
        role="primary",
        confidence=0.80
    )
    db.add(link3)
    
    db.flush()
    
    print(f"  Created 3 evidence records:")
    print(f"    - Coverage was active (positive, from 271)")
    print(f"    - Check is 45 days old/stale (negative, from 271)")
    print(f"    - Patient mentioned job change (negative, from call)")
    print(f"  Created 3 fact_source_links")
    
    return fact_coverage, fact_stale, fact_job


def seed_layer1(db, patient_context_id):
    """
    LAYER 1: PaymentProbability
    
    The critical bottleneck - what Mini displays.
    Shows all 5 factors with eligibility as the bottleneck.
    """
    
    print("\n--- Seeding Layer 1: PaymentProbability ---")
    
    # ELIGIBILITY is the bottleneck (lowest factor)
    BOTTLENECK = "eligibility"
    
    prob = PaymentProbability(
        patient_context_id=patient_context_id,
        target_date=date.today() + timedelta(days=7),
        
        # Overall probability (weighted product)
        overall_probability=0.45,
        confidence=0.85,
        
        # Individual factor probabilities - all 5 factors
        prob_appointment_attendance=0.95,  # HIGH - Confirmed (resolved)
        prob_eligibility=0.40,             # LOW - the bottleneck
        prob_coverage=0.75,                # Medium - waiting on eligibility
        prob_no_errors=0.92,               # HIGH - clean claim ready
        
        # The bottleneck
        lowest_factor=BOTTLENECK,
        lowest_factor_reason="Insurance may have expired - needs verification",
        
        # Problem statement (what Mini displays)
        problem_statement="Does the patient have funding for this care?",
        
        # Problem details
        problem_details=[{
            "issue": BOTTLENECK,
            "question": "Does the patient have funding for this care?",
            "reason": "Insurance may have expired - needs verification",
            "severity": "high",
        }],
        
        batch_job_id="seed_clean_start",
        
        # Batch recommendation (for Mini workflow mode UI)
        agentic_confidence=0.78,  # 78% confidence Mobius can handle this
        recommended_mode="mobius",
        recommendation_reason="Can run 270/271 eligibility check automatically and verify coverage status",
        agentic_actions=["run_270_eligibility_check", "verify_coverage_status", "check_payer_portal"],
    )
    db.add(prob)
    db.flush()
    
    print(f"  lowest_factor: {BOTTLENECK}")
    print(f"  overall_probability: {prob.overall_probability}")
    print(f"  Factor probabilities:")
    print(f"    - attendance: {prob.prob_appointment_attendance} (resolved)")
    print(f"    - eligibility: {prob.prob_eligibility} (BOTTLENECK)")
    print(f"    - coverage: {prob.prob_coverage} (waiting)")
    print(f"    - errors: {prob.prob_no_errors} (resolved)")
    print(f"  problem_statement: \"{prob.problem_statement}\"")
    
    return prob, BOTTLENECK


def seed_layer2_and_3(db, patient_context_id, tenant_id, bottleneck, fact_coverage, fact_stale, fact_job):
    """
    LAYER 2: ResolutionPlan
    LAYER 3: PlanSteps with rationale and evidence_ids
    
    Creates steps for ALL 5 factors:
    - attendance: resolved
    - eligibility: blocked (current focus)
    - coverage: waiting
    - clean_claim: waiting
    - errors: waiting
    """
    
    print("\n--- Seeding Layer 2: ResolutionPlan ---")
    
    # Create resolution plan with all factors
    plan = ResolutionPlan(
        patient_context_id=patient_context_id,
        tenant_id=tenant_id,
        gap_types=["attendance", "eligibility", "coverage", "clean_claim", "errors"],
        status=PlanStatus.ACTIVE,
        initial_probability=0.45,
        current_probability=0.45,
        target_probability=0.85,
        batch_job_id="seed_clean_start",
        # Start with no factor modes - user will delegate via Mini
        factor_modes={},
    )
    db.add(plan)
    db.flush()
    
    print(f"  gap_types: {plan.gap_types}")
    print(f"  factor_modes: {plan.factor_modes}")
    print(f"  status: {plan.status}")
    
    print("\n--- Seeding Layer 3: PlanSteps (ALL 5 factors) ---")
    
    all_steps = []
    step_order = 0
    
    # =========================================================================
    # FACTOR 1: ATTENDANCE (RESOLVED)
    # =========================================================================
    step_order += 1
    step_attendance = PlanStep(
        plan_id=plan.plan_id,
        step_order=step_order,
        step_code="confirm_appointment",
        step_type=StepType.CONFIRMATION,
        input_type=InputType.CONFIRMATION,
        question_text="Confirm patient appointment",
        factor_type="attendance",
        can_system_answer=True,
        status=StepStatus.RESOLVED,  # Already done
        resolved_at=datetime.utcnow() - timedelta(days=2),
        assignee_type="mobius",
        rationale="Automated appointment reminder sent and patient confirmed",
    )
    db.add(step_attendance)
    all_steps.append(step_attendance)
    print(f"    ATTENDANCE: 1 step (resolved)")
    
    # =========================================================================
    # FACTOR 2: ELIGIBILITY (BLOCKED - current focus)
    # =========================================================================
    
    # Step 1: Run fresh 270 check
    step_order += 1
    step_elig1 = PlanStep(
        plan_id=plan.plan_id,
        step_order=step_order,
        step_code="verify_eligibility",
        step_type=StepType.ACTION,
        input_type=InputType.SINGLE_CHOICE,
        question_text="Run 270 eligibility check",
        factor_type="eligibility",
        can_system_answer=True,
        status=StepStatus.CURRENT,
        assignee_type="mobius",  # Mobius handles this
        rationale="Last eligibility check was 45 days ago (stale) and patient mentioned job change - need fresh verification",
        evidence_ids=[str(fact_stale.evidence_id), str(fact_job.evidence_id)],
        assignable_activities=["verify_eligibility"],
        answer_options=[
            {"code": "done", "label": "Done"},
            {"code": "skip", "label": "Skip"},
        ],
    )
    db.add(step_elig1)
    all_steps.append(step_elig1)
    
    # Step 2: Verify employment status
    step_order += 1
    step_elig2 = PlanStep(
        plan_id=plan.plan_id,
        step_order=step_order,
        step_code="verify_employment",
        step_type=StepType.QUESTION,
        input_type=InputType.SINGLE_CHOICE,
        question_text="Is the patient still employed at their current job?",
        factor_type="eligibility",
        can_system_answer=False,  # Requires human
        status=StepStatus.PENDING,
        assignee_type="user",  # User handles this
        rationale="Patient mentioned starting new job at Acme Corp - need to confirm if current coverage still applies",
        evidence_ids=[str(fact_job.evidence_id)],
        assignable_activities=["patient_outreach"],
        answer_options=[
            {"code": "yes", "label": "Yes - Still at current job"},
            {"code": "no", "label": "No - Job changed"},
            {"code": "unknown", "label": "Unknown - Need to ask patient"},
        ],
    )
    db.add(step_elig2)
    all_steps.append(step_elig2)
    
    # Step 3: Get updated insurance info
    step_order += 1
    step_elig3 = PlanStep(
        plan_id=plan.plan_id,
        step_order=step_order,
        step_code="get_new_insurance",
        step_type=StepType.ACTION,
        input_type=InputType.SINGLE_CHOICE,
        question_text="Get updated insurance information from patient",
        factor_type="eligibility",
        can_system_answer=True,
        status=StepStatus.PENDING,
        assignee_type="mobius",  # Mobius handles this
        rationale="If employment changed, patient likely has new insurance - need updated card/info",
        evidence_ids=[str(fact_job.evidence_id), str(fact_coverage.evidence_id)],
        assignable_activities=["patient_outreach"],
        answer_options=[
            {"code": "done", "label": "Done"},
            {"code": "skip", "label": "Skip"},
        ],
    )
    db.add(step_elig3)
    all_steps.append(step_elig3)
    print(f"    ELIGIBILITY: 3 steps (1 current, 2 pending)")
    
    # =========================================================================
    # FACTOR 3: COVERAGE (WAITING)
    # =========================================================================
    step_order += 1
    step_coverage = PlanStep(
        plan_id=plan.plan_id,
        step_order=step_order,
        step_code="verify_prior_auth",
        step_type=StepType.ACTION,
        input_type=InputType.SINGLE_CHOICE,
        question_text="Check if prior authorization is required",
        factor_type="coverage",
        can_system_answer=True,
        status=StepStatus.PENDING,
        assignee_type=None,  # Not assigned yet - waiting on eligibility
        rationale="Depends on eligibility verification - may need prior auth based on payer",
        assignable_activities=["prior_authorization"],
        answer_options=[
            {"code": "not_required", "label": "Not required"},
            {"code": "required", "label": "Required - submit request"},
            {"code": "approved", "label": "Already approved"},
        ],
    )
    db.add(step_coverage)
    all_steps.append(step_coverage)
    print(f"    COVERAGE: 1 step (waiting on eligibility)")
    
    # =========================================================================
    # FACTOR 4: CLEAN CLAIM (WAITING)
    # =========================================================================
    step_order += 1
    step_clean = PlanStep(
        plan_id=plan.plan_id,
        step_order=step_order,
        step_code="verify_claim_ready",
        step_type=StepType.CONFIRMATION,
        input_type=InputType.CONFIRMATION,
        question_text="Verify claim submission is ready",
        factor_type="clean_claim",
        can_system_answer=True,
        status=StepStatus.PENDING,
        assignee_type=None,  # Not assigned yet
        rationale="Final check before claim submission - verify all data is accurate",
        assignable_activities=["submit_claims"],
        answer_options=[
            {"code": "ready", "label": "Ready to submit"},
            {"code": "issues", "label": "Has issues - needs review"},
        ],
    )
    db.add(step_clean)
    all_steps.append(step_clean)
    print(f"    CLEAN_CLAIM: 1 step (waiting on coverage)")
    
    # =========================================================================
    # FACTOR 5: ERRORS (WAITING)
    # =========================================================================
    step_order += 1
    step_errors = PlanStep(
        plan_id=plan.plan_id,
        step_order=step_order,
        step_code="final_review",
        step_type=StepType.CONFIRMATION,
        input_type=InputType.CONFIRMATION,
        question_text="Final review for potential errors",
        factor_type="errors",
        can_system_answer=True,
        status=StepStatus.PENDING,
        assignee_type=None,  # Not assigned yet
        rationale="Review for coding errors, missing info, or denial risks",
        assignable_activities=["submit_claims", "rework_denials"],
        answer_options=[
            {"code": "clean", "label": "Looks clean"},
            {"code": "errors", "label": "Found errors - needs fix"},
        ],
    )
    db.add(step_errors)
    all_steps.append(step_errors)
    print(f"    ERRORS: 1 step (final review)")
    
    db.flush()
    
    # Set current step to first eligibility step
    plan.current_step_id = step_elig1.step_id
    
    # Create PlanStepFactLink entries for eligibility steps
    step_link1a = PlanStepFactLink(
        plan_step_id=step_elig1.step_id,
        fact_id=fact_stale.evidence_id,
        display_order=1
    )
    db.add(step_link1a)
    
    step_link1b = PlanStepFactLink(
        plan_step_id=step_elig1.step_id,
        fact_id=fact_job.evidence_id,
        display_order=2
    )
    db.add(step_link1b)
    
    step_link2 = PlanStepFactLink(
        plan_step_id=step_elig2.step_id,
        fact_id=fact_job.evidence_id,
        display_order=1
    )
    db.add(step_link2)
    
    step_link3a = PlanStepFactLink(
        plan_step_id=step_elig3.step_id,
        fact_id=fact_job.evidence_id,
        display_order=1
    )
    db.add(step_link3a)
    
    step_link3b = PlanStepFactLink(
        plan_step_id=step_elig3.step_id,
        fact_id=fact_coverage.evidence_id,
        display_order=2
    )
    db.add(step_link3b)
    
    db.flush()
    
    print(f"\n  Total: {len(all_steps)} steps across 5 factors")
    print(f"  Created 5 plan_step_fact_links for eligibility steps")
    
    return plan, all_steps


def main():
    print("=" * 70)
    print("CLEAN START: 6-Layer Architecture for One Patient")
    print("=" * 70)
    
    init_db()
    db = get_db_session()
    
    try:
        # Get tenant
        tenant = db.query(Tenant).first()
        if not tenant:
            print("ERROR: No tenant found! Run seed_data.py first.")
            return
        
        print(f"\nTenant: {tenant.name}")
        
        # Get a user for reference
        user = db.query(AppUser).first()
        if user:
            print(f"User available: {user.email}")
        
        # Clear all patient data
        clear_all_patient_data(db)
        
        # Create test patient
        patient = create_test_patient(db, tenant.tenant_id)
        
        # Seed Layer 6: Raw Data
        raw_271, raw_notes = seed_layer6(db, tenant.tenant_id)
        
        # Seed Layer 5: Source Documents
        doc_271, doc_call = seed_layer5(db, tenant.tenant_id, raw_271, raw_notes)
        
        # Seed Layer 4: Evidence (Facts)
        fact_coverage, fact_stale, fact_job = seed_layer4(db, patient.patient_context_id, doc_271, doc_call)
        
        # Seed Layer 1: Payment Probability
        prob, bottleneck = seed_layer1(db, patient.patient_context_id)
        
        # Seed Layers 2 & 3: Resolution Plan + Steps (with evidence links)
        plan, steps = seed_layer2_and_3(
            db, patient.patient_context_id, tenant.tenant_id, bottleneck,
            fact_coverage, fact_stale, fact_job
        )
        
        db.commit()
        
        print("\n" + "=" * 70)
        print("SUCCESS! Full 6-layer architecture seeded for one patient")
        print("=" * 70)
        print(f"""
  Patient: John Smith (MRN: TEST-1234)
  
  Layer 6 (RawData): 2 records
    - 271 eligibility response
    - Patient call notes
  
  Layer 5 (SourceDocument): 2 records
    - Eligibility check document
    - Patient call document
  
  Layer 4 (Evidence): 3 facts
    - Coverage was active (positive)
    - Check is stale (negative)
    - Job change mentioned (negative)
  
  Layer 3 (PlanStep): {len(steps)} steps across 5 factors
    - ATTENDANCE: 1 step (resolved)
    - ELIGIBILITY: 3 steps (blocked - YOUR FOCUS)
    - COVERAGE: 1 step (waiting)
    - CLEAN_CLAIM: 1 step (waiting)
    - ERRORS: 1 step (waiting)
  
  Layer 2 (ResolutionPlan): 1 active plan
    - gap_types: {plan.gap_types}
    - factor_modes: {plan.factor_modes}
  
  Layer 1 (PaymentProbability): 1 record
    - lowest_factor: {bottleneck}
    - problem_statement: "{prob.problem_statement}"
""")
        
        print("To verify, run:")
        print("  python scripts/inspect_layers.py")
        
    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
