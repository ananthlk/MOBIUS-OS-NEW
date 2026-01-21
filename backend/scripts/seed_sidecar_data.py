#!/usr/bin/env python3
"""
Seed script for Sidecar tables.

Creates sample data for:
- user_alert: Cross-patient notifications
- milestone: Care journey progress
- milestone_history: Timeline of actions
- milestone_substep: Substeps within milestones
- user_owned_task: Tasks user took ownership of

This script links to existing data from:
- app_user (demo users)
- patient_context (demo patients)
- resolution_plan / plan_step (demo plans)

Run: python scripts/seed_sidecar_data.py

Prerequisites: Run seed_demo.py first to create users and patients.
"""

import sys
import os
import uuid
import random
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.postgres import get_db_session, init_db
from app.models import (
    Tenant,
    AppUser,
    PatientContext,
    ResolutionPlan,
    PlanStep,
)
from app.models.resolution import PlanStatus, StepStatus
from app.models.sidecar import (
    UserAlert,
    Milestone,
    MilestoneHistory,
    MilestoneSubstep,
    UserOwnedTask,
    AlertType,
    AlertPriority,
    MilestoneType,
    MilestoneStatus,
    SubstepStatus,
    ActorType,
    OwnershipStatus,
)

# Default tenant ID (must match seed_demo.py)
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# =============================================================================
# MILESTONE TEMPLATES
# =============================================================================

MILESTONE_TEMPLATES = [
    {
        "type": MilestoneType.VISIT,
        "label_template": "{{name}}'s visit confirmed",
        "order": 0,
        "substeps": [
            "Appointment scheduled",
            "Reminder sent",
            "Patient confirmed attendance",
        ],
    },
    {
        "type": MilestoneType.ELIGIBILITY,
        "label_template": "{{name}}'s insurance verified",
        "order": 1,
        "substeps": [
            "Insurance card collected",
            "Coverage dates verified",
            "Benefits confirmed",
        ],
    },
    {
        "type": MilestoneType.AUTHORIZATION,
        "label_template": "{{name}}'s authorization secured",
        "order": 2,
        "substeps": [
            "Auth requirement checked",
            "Documentation gathered",
            "Request submitted",
            "Decision received",
        ],
    },
    {
        "type": MilestoneType.DOCUMENTATION,
        "label_template": "{{name}}'s documentation ready",
        "order": 3,
        "substeps": [
            "Clinical notes complete",
            "Coding verified",
            "Claim ready to submit",
        ],
    },
]


# =============================================================================
# ALERT TEMPLATES
# =============================================================================

WIN_ALERTS = [
    {
        "title": "Authorization approved!",
        "subtitle": "{{name}}'s MRI pre-auth was approved",
        "type": AlertType.WIN,
        "priority": AlertPriority.NORMAL,
    },
    {
        "title": "Insurance verified",
        "subtitle": "{{name}}'s coverage confirmed through 2026",
        "type": AlertType.WIN,
        "priority": AlertPriority.NORMAL,
    },
    {
        "title": "Patient confirmed",
        "subtitle": "{{name}} confirmed tomorrow's appointment",
        "type": AlertType.WIN,
        "priority": AlertPriority.NORMAL,
    },
    {
        "title": "Claim submitted",
        "subtitle": "{{name}}'s claim sent to Blue Cross",
        "type": AlertType.WIN,
        "priority": AlertPriority.NORMAL,
    },
]

REMINDER_ALERTS = [
    {
        "title": "Follow-up needed",
        "subtitle": "{{name}}'s eligibility check pending 2 days",
        "type": AlertType.REMINDER,
        "priority": AlertPriority.NORMAL,
    },
    {
        "title": "Task awaiting response",
        "subtitle": "{{name}}'s auth request needs follow-up",
        "type": AlertType.REMINDER,
        "priority": AlertPriority.HIGH,
    },
]

UPDATE_ALERTS = [
    {
        "title": "Status update",
        "subtitle": "{{name}}'s auth status changed to 'In Review'",
        "type": AlertType.UPDATE,
        "priority": AlertPriority.NORMAL,
    },
    {
        "title": "New information",
        "subtitle": "Payer portal shows update for {{name}}",
        "type": AlertType.UPDATE,
        "priority": AlertPriority.NORMAL,
    },
]


# =============================================================================
# HISTORY ACTIONS
# =============================================================================

HISTORY_ACTIONS = {
    MilestoneType.VISIT: [
        {"actor": ActorType.SYSTEM, "action": "Appointment created in scheduler", "action_type": "create"},
        {"actor": ActorType.MOBIUS, "action": "Sent appointment reminder via SMS", "action_type": "notify"},
        {"actor": ActorType.USER, "action": "Called patient to confirm", "action_type": "verify"},
    ],
    MilestoneType.ELIGIBILITY: [
        {"actor": ActorType.USER, "action": "Uploaded insurance card", "action_type": "submit"},
        {"actor": ActorType.MOBIUS, "action": "Verified coverage dates with payer", "action_type": "verify"},
        {"actor": ActorType.PAYER, "action": "Confirmed active coverage", "action_type": "approve"},
    ],
    MilestoneType.AUTHORIZATION: [
        {"actor": ActorType.USER, "action": "Gathered clinical documentation", "action_type": "submit"},
        {"actor": ActorType.MOBIUS, "action": "Submitted auth request to payer portal", "action_type": "submit"},
        {"actor": ActorType.PAYER, "action": "Approved authorization request", "action_type": "approve", 
         "artifact_type": "confirmation", "artifact_label": "Auth #12345"},
    ],
    MilestoneType.DOCUMENTATION: [
        {"actor": ActorType.USER, "action": "Completed clinical notes", "action_type": "submit"},
        {"actor": ActorType.MOBIUS, "action": "Verified CPT/ICD codes", "action_type": "verify"},
        {"actor": ActorType.SYSTEM, "action": "Claim queued for submission", "action_type": "create"},
    ],
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_patient_first_name(display_name: str) -> str:
    """Extract first name from display name like 'Demo - Scenario - Maria Santos'."""
    if " - " in display_name:
        parts = display_name.split(" - ")
        full_name = parts[-1]  # Last part is the actual name
        return full_name.split()[0]
    return display_name.split()[0]


def format_template(template: str, name: str) -> str:
    """Replace {{name}} with actual name."""
    return template.replace("{{name}}", name)


def clear_sidecar_data(db):
    """Clear existing sidecar data."""
    print("\n1. Clearing existing sidecar data...")
    
    from sqlalchemy import text
    
    tables = [
        "user_owned_task",
        "milestone_substep",
        "milestone_history",
        "user_alert",
        "milestone",
    ]
    
    for table in tables:
        try:
            db.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        except Exception as e:
            print(f"   (skipped {table}: {e})")
            db.rollback()
    
    db.commit()
    print("   Cleared sidecar data.")


def seed_milestones(db, patients, tenant_id):
    """Create milestones for patients."""
    print("\n2. Creating milestones...")
    
    milestone_count = 0
    substep_count = 0
    history_count = 0
    
    # Get some users for history entries
    users = db.query(AppUser).filter(AppUser.tenant_id == tenant_id).limit(5).all()
    user_names = {u.user_id: u.display_name for u in users}
    
    for patient in patients:
        patient_name = get_patient_first_name(patient.display_name)
        
        # Get associated plan to determine status
        plan = db.query(ResolutionPlan).filter(
            ResolutionPlan.patient_context_id == patient.patient_context_id
        ).first()
        
        plan_resolved = plan and plan.status == PlanStatus.RESOLVED
        
        for template in MILESTONE_TEMPLATES:
            # Determine milestone status based on plan status and milestone type
            if plan_resolved:
                status = MilestoneStatus.COMPLETE
            else:
                # First 1-2 milestones might be complete, rest pending/in_progress
                if template["order"] == 0:
                    status = random.choice([MilestoneStatus.COMPLETE, MilestoneStatus.IN_PROGRESS])
                elif template["order"] == 1:
                    status = random.choice([MilestoneStatus.COMPLETE, MilestoneStatus.IN_PROGRESS, MilestoneStatus.PENDING])
                else:
                    status = random.choice([MilestoneStatus.PENDING, MilestoneStatus.BLOCKED])
            
            milestone = Milestone(
                patient_context_id=patient.patient_context_id,
                tenant_id=tenant_id,
                milestone_type=template["type"],
                label=format_template(template["label_template"], patient_name),
                label_template=template["label_template"],
                milestone_order=template["order"],
                status=status,
                started_at=datetime.utcnow() - timedelta(days=random.randint(1, 7)) if status != MilestoneStatus.PENDING else None,
                completed_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)) if status == MilestoneStatus.COMPLETE else None,
                completed_by="mobius" if status == MilestoneStatus.COMPLETE and random.random() > 0.5 else "user" if status == MilestoneStatus.COMPLETE else None,
            )
            db.add(milestone)
            db.flush()
            milestone_count += 1
            
            # Create substeps
            for i, substep_label in enumerate(template["substeps"]):
                if status == MilestoneStatus.COMPLETE:
                    substep_status = SubstepStatus.COMPLETE
                elif status == MilestoneStatus.IN_PROGRESS:
                    if i < len(template["substeps"]) // 2:
                        substep_status = SubstepStatus.COMPLETE
                    elif i == len(template["substeps"]) // 2:
                        substep_status = SubstepStatus.CURRENT
                    else:
                        substep_status = SubstepStatus.PENDING
                else:
                    substep_status = SubstepStatus.PENDING
                
                substep = MilestoneSubstep(
                    milestone_id=milestone.milestone_id,
                    label=substep_label,
                    status=substep_status,
                    substep_order=i,
                    completed_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72)) if substep_status == SubstepStatus.COMPLETE else None,
                    completed_by="mobius" if substep_status == SubstepStatus.COMPLETE and random.random() > 0.5 else "user" if substep_status == SubstepStatus.COMPLETE else None,
                )
                db.add(substep)
                substep_count += 1
            
            # Create history entries for complete/in-progress milestones
            if status in [MilestoneStatus.COMPLETE, MilestoneStatus.IN_PROGRESS]:
                actions = HISTORY_ACTIONS.get(template["type"], [])
                num_history = len(actions) if status == MilestoneStatus.COMPLETE else random.randint(1, len(actions))
                
                for i, action_data in enumerate(actions[:num_history]):
                    # Select user for user actions
                    actor_user_id = None
                    actor_name = None
                    
                    if action_data["actor"] == ActorType.USER and users:
                        user = random.choice(users)
                        actor_user_id = user.user_id
                        actor_name = user.display_name
                    elif action_data["actor"] == ActorType.MOBIUS:
                        actor_name = "Mobius"
                    elif action_data["actor"] == ActorType.PAYER:
                        actor_name = "Blue Cross"
                    elif action_data["actor"] == ActorType.SYSTEM:
                        actor_name = "System"
                    
                    history = MilestoneHistory(
                        milestone_id=milestone.milestone_id,
                        actor=action_data["actor"],
                        actor_name=actor_name,
                        actor_user_id=actor_user_id,
                        action=action_data["action"],
                        action_type=action_data.get("action_type"),
                        artifact_type=action_data.get("artifact_type"),
                        artifact_label=action_data.get("artifact_label"),
                        created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 168) - i * 24),
                    )
                    db.add(history)
                    history_count += 1
    
    db.commit()
    print(f"   Created {milestone_count} milestones")
    print(f"   Created {substep_count} substeps")
    print(f"   Created {history_count} history entries")


def seed_alerts(db, users, patients, tenant_id):
    """Create alerts for users."""
    print("\n3. Creating user alerts...")
    
    alert_count = 0
    
    # Get patients with their names
    patient_data = []
    for patient in patients[:30]:  # Use first 30 patients for alerts
        patient_data.append({
            "context": patient,
            "name": get_patient_first_name(patient.display_name),
            "key": patient.patient_key,
        })
    
    # Create alerts for each user
    for user in users:
        # 3-5 alerts per user
        num_alerts = random.randint(3, 5)
        
        # Mix of win, reminder, update alerts
        all_templates = WIN_ALERTS * 3 + REMINDER_ALERTS * 2 + UPDATE_ALERTS * 2
        selected_templates = random.sample(all_templates, min(num_alerts, len(all_templates)))
        
        for i, template in enumerate(selected_templates):
            patient = random.choice(patient_data)
            patient_name = patient["name"]
            
            # Get related plan
            plan = db.query(ResolutionPlan).filter(
                ResolutionPlan.patient_context_id == patient["context"].patient_context_id
            ).first()
            
            # Get related step if plan exists
            step = None
            if plan:
                step = db.query(PlanStep).filter(
                    PlanStep.plan_id == plan.plan_id,
                    PlanStep.status == StepStatus.CURRENT
                ).first()
            
            alert = UserAlert(
                user_id=user.user_id,
                alert_type=template["type"],
                priority=template["priority"],
                title=template["title"],
                subtitle=format_template(template["subtitle"], patient_name),
                patient_context_id=patient["context"].patient_context_id,
                patient_name=patient_name,
                patient_key=patient["key"],
                action_type="open_sidecar",
                related_plan_id=plan.plan_id if plan else None,
                related_step_id=step.step_id if step else None,
                read=(i >= 2),  # First 2 unread, rest read
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
            )
            db.add(alert)
            alert_count += 1
    
    db.commit()
    print(f"   Created {alert_count} alerts for {len(users)} users")


def seed_user_owned_tasks(db, users, patients, tenant_id):
    """Create user-owned tasks."""
    print("\n4. Creating user-owned tasks...")
    
    task_count = 0
    
    # Get active plans with current steps
    active_plans = db.query(ResolutionPlan).filter(
        ResolutionPlan.tenant_id == tenant_id,
        ResolutionPlan.status == PlanStatus.ACTIVE
    ).limit(20).all()
    
    for user in users[:3]:  # First 3 users get owned tasks
        # 2-4 tasks per user
        num_tasks = random.randint(2, 4)
        
        for _ in range(num_tasks):
            if not active_plans:
                break
            
            plan = random.choice(active_plans)
            
            # Get current step
            step = db.query(PlanStep).filter(
                PlanStep.plan_id == plan.plan_id,
                PlanStep.status == StepStatus.CURRENT
            ).first()
            
            if not step:
                continue
            
            # Get patient name
            patient = db.query(PatientContext).filter(
                PatientContext.patient_context_id == plan.patient_context_id
            ).first()
            
            if not patient:
                continue
            
            from app.models import PatientSnapshot
            snapshot = db.query(PatientSnapshot).filter(
                PatientSnapshot.patient_context_id == patient.patient_context_id
            ).first()
            
            patient_name = get_patient_first_name(snapshot.display_name) if snapshot else "Patient"
            
            # Determine status
            status = random.choice([
                OwnershipStatus.ACTIVE,
                OwnershipStatus.ACTIVE,
                OwnershipStatus.REMINDER_SENT,
                OwnershipStatus.RESOLVED,
            ])
            
            task = UserOwnedTask(
                user_id=user.user_id,
                tenant_id=tenant_id,
                plan_step_id=step.step_id,
                plan_id=plan.plan_id,
                patient_context_id=patient.patient_context_id,
                question_text=step.question_text,
                patient_name=patient_name,
                patient_key=patient.patient_key,
                status=status,
                initial_note="I'll check on this today" if random.random() > 0.5 else None,
                assigned_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72)),
                resolution_detected_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24)) if status == OwnershipStatus.RESOLVED else None,
                resolution_signal="Status updated in payer portal" if status == OwnershipStatus.RESOLVED else None,
                resolution_source="batch" if status == OwnershipStatus.RESOLVED else None,
                last_reminder_at=datetime.utcnow() - timedelta(hours=random.randint(1, 12)) if status == OwnershipStatus.REMINDER_SENT else None,
                reminder_count=1 if status == OwnershipStatus.REMINDER_SENT else 0,
                resolved_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24)) if status == OwnershipStatus.RESOLVED else None,
            )
            db.add(task)
            task_count += 1
    
    db.commit()
    print(f"   Created {task_count} user-owned tasks")


def print_summary(db, tenant_id):
    """Print summary of seeded data."""
    print("\n" + "=" * 60)
    print("SIDECAR DATA SEEDING COMPLETE")
    print("=" * 60)
    
    milestone_count = db.query(Milestone).filter(
        Milestone.tenant_id == tenant_id
    ).count()
    
    substep_count = db.query(MilestoneSubstep).count()
    history_count = db.query(MilestoneHistory).count()
    alert_count = db.query(UserAlert).count()
    task_count = db.query(UserOwnedTask).filter(
        UserOwnedTask.tenant_id == tenant_id
    ).count()
    
    # Count by status
    complete_milestones = db.query(Milestone).filter(
        Milestone.tenant_id == tenant_id,
        Milestone.status == MilestoneStatus.COMPLETE
    ).count()
    
    in_progress_milestones = db.query(Milestone).filter(
        Milestone.tenant_id == tenant_id,
        Milestone.status == MilestoneStatus.IN_PROGRESS
    ).count()
    
    unread_alerts = db.query(UserAlert).filter(
        UserAlert.read == False
    ).count()
    
    active_tasks = db.query(UserOwnedTask).filter(
        UserOwnedTask.tenant_id == tenant_id,
        UserOwnedTask.status == OwnershipStatus.ACTIVE
    ).count()
    
    print(f"\n📊 Database Summary:")
    print(f"  Milestones: {milestone_count}")
    print(f"    - Complete: {complete_milestones}")
    print(f"    - In Progress: {in_progress_milestones}")
    print(f"    - Pending/Blocked: {milestone_count - complete_milestones - in_progress_milestones}")
    print(f"  Substeps: {substep_count}")
    print(f"  History Entries: {history_count}")
    print(f"  User Alerts: {alert_count} ({unread_alerts} unread)")
    print(f"  User-Owned Tasks: {task_count} ({active_tasks} active)")
    
    print("\n🎯 Sidecar UI Features Ready:")
    print("  ✓ StatusBar - Care readiness from milestones")
    print("  ✓ Bottlenecks - From resolution plan steps")
    print("  ✓ Milestones - With substeps and history")
    print("  ✓ Alerts/Toasts - Cross-patient notifications")
    print("  ✓ User Tasks - 'I'll handle this' tracking")
    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("MOBIUS OS - SIDECAR DATA SEED")
    print("=" * 60)
    print("\nThis script creates sidecar-specific data (milestones, alerts, etc.)")
    print("Prerequisites: Run seed_demo.py first.\n")
    
    # Initialize DB
    init_db()
    
    with get_db_session() as db:
        # Verify tenant exists
        tenant = db.query(Tenant).filter(
            Tenant.tenant_id == DEFAULT_TENANT_ID
        ).first()
        
        if not tenant:
            print("ERROR: No tenant found. Run seed_demo.py first.")
            return
        
        # Get users
        users = db.query(AppUser).filter(
            AppUser.tenant_id == tenant.tenant_id
        ).all()
        
        if not users:
            print("ERROR: No users found. Run seed_demo.py first.")
            return
        
        print(f"Found {len(users)} users")
        
        # Get patients with snapshots
        from app.models import PatientSnapshot
        patients = db.query(PatientSnapshot).join(
            PatientContext,
            PatientContext.patient_context_id == PatientSnapshot.patient_context_id
        ).filter(
            PatientContext.tenant_id == tenant.tenant_id
        ).all()
        
        if not patients:
            print("ERROR: No patients found. Run seed_demo.py first.")
            return
        
        print(f"Found {len(patients)} patients")
        
        # Get patient contexts for the snapshots
        patient_contexts = []
        for snapshot in patients:
            ctx = db.query(PatientContext).filter(
                PatientContext.patient_context_id == snapshot.patient_context_id
            ).first()
            if ctx:
                ctx.display_name = snapshot.display_name
                patient_contexts.append(ctx)
        
        # Clear and seed
        clear_sidecar_data(db)
        seed_milestones(db, patient_contexts, tenant.tenant_id)
        seed_alerts(db, users, patient_contexts, tenant.tenant_id)
        seed_user_owned_tasks(db, users, patient_contexts, tenant.tenant_id)
        
        print_summary(db, tenant.tenant_id)
    
    print("✅ Sidecar seed complete!\n")


if __name__ == "__main__":
    main()
