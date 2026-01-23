#!/usr/bin/env python3
"""
Inspect all 6 layers of data for ONE patient.

Shows the full chain:
Layer 1 → Layer 2 → Layer 3 → Layer 4 → Layer 5 → Layer 6
"""

import sys
import os
import json

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
from app.models import PatientContext, PatientSnapshot
from app.models.probability import PaymentProbability
from app.models.resolution import ResolutionPlan, PlanStep
from app.models.evidence import RawData, SourceDocument, Evidence, FactSourceLink, PlanStepFactLink
from app.models.patient_ids import PatientId


def main():
    init_db()
    db = get_db_session()
    
    print("=" * 70)
    print("INSPECTING 6-LAYER ARCHITECTURE FOR ONE PATIENT")
    print("=" * 70)
    
    # Get the most recently created PaymentProbability
    prob = db.query(PaymentProbability).order_by(PaymentProbability.computed_at.desc()).first()
    
    if not prob:
        print("\nNO PaymentProbability records found! Run seed_clean_start.py first.")
        return
    
    patient_id = prob.patient_context_id
    
    # Get related data across all layers
    patient = db.query(PatientContext).filter(
        PatientContext.patient_context_id == patient_id
    ).first()
    
    snapshot = db.query(PatientSnapshot).filter(
        PatientSnapshot.patient_context_id == patient_id
    ).first()
    
    mrn_record = db.query(PatientId).filter(
        PatientId.patient_context_id == patient_id,
        PatientId.id_type == 'mrn'
    ).first()
    
    plan = db.query(ResolutionPlan).filter(
        ResolutionPlan.patient_context_id == patient_id
    ).first()
    
    steps = []
    if plan:
        steps = db.query(PlanStep).filter(
            PlanStep.plan_id == plan.plan_id
        ).order_by(PlanStep.step_order).all()
    
    # Get Layer 4: Evidence
    evidence_list = db.query(Evidence).filter(
        Evidence.patient_context_id == patient_id
    ).all()
    
    # Get Layer 5: Source Documents (via evidence)
    source_ids = [e.source_id for e in evidence_list if e.source_id]
    source_docs = db.query(SourceDocument).filter(
        SourceDocument.source_id.in_(source_ids)
    ).all() if source_ids else []
    
    # Get Layer 6: Raw Data (via source documents)
    raw_ids = [sd.raw_id for sd in source_docs if sd.raw_id]
    raw_data_list = db.query(RawData).filter(
        RawData.raw_id.in_(raw_ids)
    ).all() if raw_ids else []
    
    # ========== PRINT OUTPUT ==========
    
    print(f"\nPatient ID: {patient_id}")
    if snapshot:
        print(f"Patient Name: {snapshot.display_name}")
        print(f"ID Label: {snapshot.id_label} = {snapshot.id_masked}")
    if mrn_record:
        print(f"MRN: {mrn_record.id_value}")
    
    # Layer 1
    print("\n" + "=" * 70)
    print("LAYER 1: PaymentProbability (Critical Bottleneck)")
    print("=" * 70)
    print(f"""
  probability_id:     {prob.probability_id}
  overall_probability: {prob.overall_probability}
  confidence:         {prob.confidence}
  
  FACTOR PROBABILITIES:
    attendance:  {prob.prob_appointment_attendance}
    eligibility: {prob.prob_eligibility}
    coverage:    {prob.prob_coverage}
    errors:      {prob.prob_no_errors}
  
  BOTTLENECK:
    lowest_factor: {prob.lowest_factor}
    reason: {prob.lowest_factor_reason}
  
  PROBLEM STATEMENT (what Mini displays):
    "{prob.problem_statement}"
""")
    
    # Layer 2
    print("=" * 70)
    print("LAYER 2: ResolutionPlan")
    print("=" * 70)
    if not plan:
        print("\n  NO ResolutionPlan found!")
    else:
        gap_types = plan.gap_types or []
        print(f"""
  plan_id:            {plan.plan_id}
  status:             {plan.status}
  gap_types:          {gap_types}
  initial_probability: {plan.initial_probability}
  current_probability: {plan.current_probability}
  
  ALIGNMENT CHECK:
    Layer 1 lowest_factor: "{prob.lowest_factor}"
    Layer 2 gap_types:     {gap_types}
    MATCH: {"YES" if prob.lowest_factor in gap_types else "NO - MISALIGNED!"}
""")
    
    # Layer 3
    print("=" * 70)
    print("LAYER 3: PlanSteps (Mitigations with Rationale)")
    print("=" * 70)
    if not steps:
        print("\n  NO PlanSteps found!")
    else:
        for step in steps:
            evidence_ids = step.evidence_ids or []
            print(f"""
  Step {step.step_order}: {step.step_code}
    status:       {step.status}
    question:     "{step.question_text}"
    factor_type:  {step.factor_type}
    can_system_answer: {step.can_system_answer}
    
    RATIONALE: "{step.rationale or 'None'}"
    EVIDENCE_IDS: {evidence_ids}
""")
    
    # Layer 4
    print("=" * 70)
    print("LAYER 4: Evidence (Extracted Facts)")
    print("=" * 70)
    if not evidence_list:
        print("\n  NO Evidence records found!")
    else:
        for e in evidence_list:
            print(f"""
  evidence_id: {e.evidence_id}
    factor_type:    {e.factor_type}
    fact_type:      {e.fact_type}
    fact_summary:   "{e.fact_summary}"
    impact:         {e.impact_direction} (weight: {e.impact_weight})
    is_stale:       {e.is_stale}
    source_id:      {e.source_id}
    
    fact_data: {json.dumps(e.fact_data, indent=6) if e.fact_data else 'None'}
""")
    
    # Layer 5
    print("=" * 70)
    print("LAYER 5: SourceDocument (Document Catalog)")
    print("=" * 70)
    if not source_docs:
        print("\n  NO SourceDocument records found!")
    else:
        for sd in source_docs:
            print(f"""
  source_id:      {sd.source_id}
    document_type:  {sd.document_type}
    document_label: "{sd.document_label}"
    source_system:  {sd.source_system}
    transaction_id: {sd.transaction_id}
    document_date:  {sd.document_date}
    trust_score:    {sd.trust_score}
    raw_id:         {sd.raw_id}
""")
    
    # Layer 6
    print("=" * 70)
    print("LAYER 6: RawData (Actual Content)")
    print("=" * 70)
    if not raw_data_list:
        print("\n  NO RawData records found!")
    else:
        for rd in raw_data_list:
            content_preview = json.dumps(rd.raw_content, indent=6)[:500] if rd.raw_content else 'None'
            if len(json.dumps(rd.raw_content or {})) > 500:
                content_preview += "\n      ... (truncated)"
            print(f"""
  raw_id:         {rd.raw_id}
    content_type:   {rd.content_type}
    source_system:  {rd.source_system}
    collected_at:   {rd.collected_at}
    file_reference: {rd.file_reference}
    
    raw_content (preview):
      {content_preview}
""")
    
    # Get join table data
    fact_source_links = db.query(FactSourceLink).all()
    plan_step_fact_links = db.query(PlanStepFactLink).all()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"""
  Layer 1 (PaymentProbability): {1 if prob else 0} record
  Layer 2 (ResolutionPlan):     {1 if plan else 0} record
  Layer 3 (PlanStep):           {len(steps)} steps
  Layer 4 (Evidence):           {len(evidence_list)} facts
  Layer 5 (SourceDocument):     {len(source_docs)} documents
  Layer 6 (RawData):            {len(raw_data_list)} raw records
  
  JOIN TABLES:
    FactSourceLink:     {len(fact_source_links)} links (Fact → Source)
    PlanStepFactLink:   {len(plan_step_fact_links)} links (Step → Fact)
""")
    
    # Show join table details
    if fact_source_links:
        print("  FACT → SOURCE LINKS:")
        for link in fact_source_links:
            print(f"    Fact {str(link.fact_id)[:8]}... → Source {str(link.source_id)[:8]}... (role={link.role}, conf={link.confidence})")
    
    if plan_step_fact_links:
        print("\n  STEP → FACT LINKS:")
        for link in plan_step_fact_links:
            print(f"    Step {str(link.plan_step_id)[:8]}... → Fact {str(link.fact_id)[:8]}... (order={link.display_order})")
    
    # Verify links
    print("\nLINK VERIFICATION:")
    
    # Check Layer 3 → Layer 4 links (via join table)
    all_evidence_ids = [str(e.evidence_id) for e in evidence_list]
    for link in plan_step_fact_links:
        if str(link.fact_id) in all_evidence_ids:
            print(f"  PlanStepFactLink → Evidence {str(link.fact_id)[:8]}... OK")
        else:
            print(f"  PlanStepFactLink → Evidence {str(link.fact_id)[:8]}... MISSING!")
    
    # Check Layer 4 → Layer 5 links (via join table)
    all_source_ids = [str(sd.source_id) for sd in source_docs]
    for link in fact_source_links:
        if str(link.source_id) in all_source_ids:
            print(f"  FactSourceLink → SourceDoc {str(link.source_id)[:8]}... OK")
        else:
            print(f"  FactSourceLink → SourceDoc {str(link.source_id)[:8]}... MISSING!")
    
    # Check Layer 5 → Layer 6 links
    all_raw_ids = [str(rd.raw_id) for rd in raw_data_list]
    for sd in source_docs:
        if sd.raw_id:
            if str(sd.raw_id) in all_raw_ids:
                print(f"  SourceDoc {str(sd.source_id)[:8]}... → RawData OK")
            else:
                print(f"  SourceDoc {str(sd.source_id)[:8]}... → RawData MISSING!")
    
    print("")
    db.close()


if __name__ == "__main__":
    main()
