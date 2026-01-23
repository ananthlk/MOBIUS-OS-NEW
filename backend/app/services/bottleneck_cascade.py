"""
Bottleneck Override Cascade Service

Reusable service for cascading user overrides between Layer 1 (payment_probability)
and Layer 2 (resolution_plan). When a user overrides a bottleneck in either layer,
the same bottleneck in the other layer is updated to maintain consistency.

Bottlenecks are matched by factor_type (eligibility, coverage, attendance, errors).
"""

from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified
from app.models.probability import PaymentProbability
from app.models.resolution import ResolutionPlan, PlanStatus, PlanStep


def cascade_bottleneck_override(
    db: Session,
    patient_context_id: UUID,
    bottleneck_factor: str,  # "eligibility", "coverage", "attendance", "errors"
    status: str,  # "resolved" | "unresolved"
    user_id: UUID,
    submitted_at: datetime,
    source_layer: str  # "layer1" (payment_probability) or "layer2" (resolution_plan)
):
    """
    Cascade user override between Layer 1 (payment_probability) and Layer 2 (resolution_plan).
    
    When override originates from Layer 1 (Mini):
    - Update matching resolution_plans (by gap_types or step factor_type)
    
    When override originates from Layer 2 (Sidecar):
    - Update matching payment_probability records (by lowest_factor or problem_details)
    
    Args:
        db: Database session
        patient_context_id: Patient context UUID
        bottleneck_factor: The factor type being overridden (e.g., "eligibility")
        status: "resolved" or "unresolved"
        user_id: User who made the override
        submitted_at: Timestamp of the override
        source_layer: Which layer the override originated from ("layer1" or "layer2")
    """
    try:
        if source_layer == "layer1":
            # Cascade from payment_probability → resolution_plan
            _cascade_to_resolution_plan(
                db, patient_context_id, bottleneck_factor, status, user_id, submitted_at
            )
        elif source_layer == "layer2":
            # Cascade from resolution_plan → payment_probability
            _cascade_to_payment_probability(
                db, patient_context_id, bottleneck_factor, status, user_id, submitted_at
            )
    except Exception as e:
        print(f"[bottleneck_cascade] Warning: Cascade failed (non-critical): {e}")
        import traceback
        traceback.print_exc()


def _cascade_to_resolution_plan(
    db: Session,
    patient_context_id: UUID,
    bottleneck_factor: str,
    status: str,
    user_id: UUID,
    submitted_at: datetime
):
    """Cascade override from Layer 1 to Layer 2."""
    # Eager load steps to avoid lazy loading issues
    active_plans = db.query(ResolutionPlan).options(
        joinedload(ResolutionPlan.steps)
    ).filter(
        ResolutionPlan.patient_context_id == patient_context_id,
        ResolutionPlan.status == PlanStatus.ACTIVE
    ).all()
    
    for plan in active_plans:
        # Match by gap_types or step factor_type
        gap_types = plan.gap_types or []
        matches = (
            bottleneck_factor in gap_types or
            any(step.factor_type == bottleneck_factor for step in plan.steps)
        )
        
        if matches:
            if status == "resolved":
                plan.status = PlanStatus.RESOLVED
                plan.resolved_at = submitted_at
                plan.resolved_by = user_id
                plan.resolution_type = "user_override"
                plan.resolution_notes = f"User override (Layer 1): {bottleneck_factor} marked as resolved at {submitted_at.isoformat()}"
                print(f"[bottleneck_cascade] Updated ResolutionPlan {plan.plan_id} to RESOLVED for factor {bottleneck_factor}")
            elif status == "unresolved":
                existing_notes = plan.resolution_notes or ""
                override_note = f"User override (Layer 1): {bottleneck_factor} marked as unresolved at {submitted_at.isoformat()}"
                plan.resolution_notes = f"{existing_notes}\n{override_note}".strip()
                print(f"[bottleneck_cascade] Noted user override (unresolved) in ResolutionPlan {plan.plan_id} for factor {bottleneck_factor}")


def _cascade_to_payment_probability(
    db: Session,
    patient_context_id: UUID,
    bottleneck_factor: str,
    status: str,
    user_id: UUID,
    submitted_at: datetime
):
    """Cascade override from Layer 2 to Layer 1."""
    # Get all payment_probability records for this patient (not just latest)
    prob_records = db.query(PaymentProbability).filter(
        PaymentProbability.patient_context_id == patient_context_id
    ).order_by(PaymentProbability.computed_at.desc()).all()
    
    for prob in prob_records:
        # Match by lowest_factor or problem_details containing the factor
        matches = (
            prob.lowest_factor == bottleneck_factor or
            (prob.problem_details and any(
                detail.get("issue") == bottleneck_factor 
                for detail in (prob.problem_details if isinstance(prob.problem_details, list) else [])
            ))
        )
        
        if matches:
            # Store override metadata in problem_details
            override_note = f"User override (Layer 2): {bottleneck_factor} marked as {status} at {submitted_at.isoformat()}"
            
            # Initialize problem_details if needed
            if not prob.problem_details:
                prob.problem_details = []
            if not isinstance(prob.problem_details, list):
                prob.problem_details = []
            
            # Add override metadata
            prob.problem_details.append({
                "type": "user_override",
                "factor": bottleneck_factor,
                "status": status,
                "timestamp": submitted_at.isoformat(),
                "user_id": str(user_id),
                "note": override_note
            })
            # Flag JSONB column as modified so SQLAlchemy detects the change
            flag_modified(prob, "problem_details")
            print(f"[bottleneck_cascade] Updated PaymentProbability {prob.probability_id} with override for factor {bottleneck_factor}")
