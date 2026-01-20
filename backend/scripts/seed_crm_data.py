#!/usr/bin/env python3
"""
CRM/Scheduler data seeding script.

Creates sample appointments, reminders, intake forms, and insurance verifications
for development/testing of the Mock CRM system.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/seed_crm_data.py

Prerequisites:
    - Database must be migrated (alembic upgrade head)
    - Patient data must be seeded first (python scripts/seed_data.py)
"""

import sys
import random
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, date, timedelta

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.postgres import get_db_session
from app.models.patient import PatientContext, PatientSnapshot
from app.models.patient_ids import PatientId
from app.models.appointment import Appointment, AppointmentReminder
from app.models.intake import IntakeForm, InsuranceVerification, IntakeChecklist

# Default tenant ID
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Sample data pools
APPOINTMENT_TYPES = [
    "new_patient", "follow_up", "annual_exam", "urgent", 
    "telehealth", "procedure", "consultation", "lab_work"
]

APPOINTMENT_STATUSES = [
    "scheduled", "confirmed", "checked_in", "in_progress", 
    "completed", "no_show", "cancelled"
]

PROVIDERS = [
    "Dr. Emily Williams", "Dr. Robert Johnson", "Dr. Sarah Miller",
    "Dr. Michael Brown", "Dr. Lisa Park", "Dr. James Chen",
    "Dr. Maria Garcia", "Dr. David Lee", "Dr. Jennifer Adams"
]

LOCATIONS = [
    "Main Campus - Building A", "East Wing Clinic", "West Side Office",
    "Downtown Medical Center", "Telehealth"
]

ROOMS = ["101", "102", "103", "201", "202", "203", "301", "302", "Exam 1", "Exam 2", "Tele-A"]

VISIT_REASONS = [
    "Annual wellness exam", "Follow-up visit", "Blood pressure check",
    "Medication review", "Lab results discussion", "New patient consultation",
    "Chronic care management", "Urgent symptoms", "Pre-operative evaluation",
    "Post-operative follow-up", "Vaccination", "Physical therapy referral"
]

INSURANCE_NAMES = [
    "Blue Cross Blue Shield", "Aetna", "United Healthcare", "Cigna",
    "Humana", "Kaiser Permanente", "Medicare", "Medicaid", "Tricare"
]

FORM_TYPES = [
    "demographics", "insurance", "consent", "medical_history",
    "hipaa", "financial_policy", "release_of_info", "emergency_contact"
]


def get_deterministic_random(seed_value: str):
    """Get a deterministic random generator based on a seed string."""
    seed = int(hashlib.md5(seed_value.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def seed_appointments(db, tenant_id: uuid.UUID):
    """Create sample appointments for today and upcoming days."""
    print("\n1. Seeding appointments...")
    
    # Get all patients
    contexts = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).all()
    
    if not contexts:
        print("   ERROR: No patients found. Run seed_data.py first.")
        return []
    
    created_appointments = []
    today = date.today()
    
    # Create appointments for today (8-10 appointments)
    print(f"   Creating appointments for today ({today})...")
    
    # Select random patients for today
    rng = get_deterministic_random(f"today-{today.isoformat()}")
    today_patients = rng.sample(contexts, min(10, len(contexts)))
    
    # Time slots: 8:00 AM to 5:00 PM in 30-minute intervals
    time_slots = []
    for hour in range(8, 17):
        for minute in [0, 30]:
            time_slots.append((hour, minute))
    
    for i, ctx in enumerate(today_patients):
        patient_rng = get_deterministic_random(f"appt-{ctx.patient_key}-{today}")
        
        # Check if appointment already exists for this patient today
        existing = db.query(Appointment).filter(
            Appointment.patient_context_id == ctx.patient_context_id,
            Appointment.scheduled_date == today
        ).first()
        
        if existing:
            print(f"   - Skipping existing appointment for patient")
            continue
        
        # Assign time slot
        if i < len(time_slots):
            hour, minute = time_slots[i]
        else:
            hour, minute = patient_rng.choice(time_slots)
        
        scheduled_time = datetime(today.year, today.month, today.day, hour, minute)
        
        # Determine status based on time
        now = datetime.now()
        if scheduled_time < now - timedelta(hours=1):
            # Past appointments - mix of completed and no-show
            status = patient_rng.choice(["completed", "completed", "completed", "no_show"])
        elif scheduled_time < now:
            # Recent past - in_progress or checked_in
            status = patient_rng.choice(["in_progress", "checked_in", "completed"])
        else:
            # Future - scheduled or confirmed
            status = patient_rng.choice(["scheduled", "confirmed", "confirmed"])
        
        appt = Appointment(
            tenant_id=tenant_id,
            patient_context_id=ctx.patient_context_id,
            scheduled_date=today,
            scheduled_time=scheduled_time,
            duration_minutes=patient_rng.choice([15, 30, 30, 30, 45, 60]),
            appointment_type=patient_rng.choice(APPOINTMENT_TYPES),
            status=status,
            provider_name=patient_rng.choice(PROVIDERS),
            location=patient_rng.choice(LOCATIONS),
            room=patient_rng.choice(ROOMS),
            visit_reason=patient_rng.choice(VISIT_REASONS),
            needs_confirmation=(status == "scheduled"),
            needs_insurance_verification=patient_rng.choice([True, False, False, False]),
            created_at=datetime.utcnow(),
        )
        
        # Add check-in time for checked_in, in_progress, completed
        if status in ["checked_in", "in_progress", "completed"]:
            appt.checked_in_at = scheduled_time - timedelta(minutes=patient_rng.randint(5, 20))
            if status in ["in_progress", "completed"]:
                appt.wait_time_minutes = patient_rng.randint(0, 25)
        
        if status == "completed":
            appt.completed_at = scheduled_time + timedelta(minutes=appt.duration_minutes)
        elif status == "no_show":
            appt.no_show_at = scheduled_time + timedelta(minutes=15)
        
        db.add(appt)
        created_appointments.append(appt)
    
    # Create appointments for tomorrow (5-8 appointments)
    tomorrow = today + timedelta(days=1)
    print(f"   Creating appointments for tomorrow ({tomorrow})...")
    
    tomorrow_rng = get_deterministic_random(f"tomorrow-{tomorrow.isoformat()}")
    tomorrow_patients = tomorrow_rng.sample(contexts, min(8, len(contexts)))
    
    for i, ctx in enumerate(tomorrow_patients):
        patient_rng = get_deterministic_random(f"appt-{ctx.patient_key}-{tomorrow}")
        
        existing = db.query(Appointment).filter(
            Appointment.patient_context_id == ctx.patient_context_id,
            Appointment.scheduled_date == tomorrow
        ).first()
        
        if existing:
            continue
        
        if i < len(time_slots):
            hour, minute = time_slots[i]
        else:
            hour, minute = patient_rng.choice(time_slots)
        
        scheduled_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute)
        
        appt = Appointment(
            tenant_id=tenant_id,
            patient_context_id=ctx.patient_context_id,
            scheduled_date=tomorrow,
            scheduled_time=scheduled_time,
            duration_minutes=patient_rng.choice([15, 30, 30, 30, 45]),
            appointment_type=patient_rng.choice(APPOINTMENT_TYPES),
            status=patient_rng.choice(["scheduled", "scheduled", "confirmed"]),
            provider_name=patient_rng.choice(PROVIDERS),
            location=patient_rng.choice(LOCATIONS),
            room=patient_rng.choice(ROOMS),
            visit_reason=patient_rng.choice(VISIT_REASONS),
            needs_confirmation=True,
            needs_insurance_verification=patient_rng.choice([True, True, False, False]),
            created_at=datetime.utcnow(),
        )
        
        db.add(appt)
        created_appointments.append(appt)
    
    db.commit()
    print(f"\n   Created {len(created_appointments)} appointments")
    return created_appointments


def seed_reminders(db, tenant_id: uuid.UUID, appointments: list):
    """Create appointment reminders."""
    print("\n2. Seeding appointment reminders...")
    
    created_count = 0
    today = date.today()
    
    for appt in appointments:
        rng = get_deterministic_random(f"reminder-{appt.appointment_id}")
        
        # Skip if reminders already exist
        existing = db.query(AppointmentReminder).filter(
            AppointmentReminder.appointment_id == appt.appointment_id
        ).first()
        
        if existing:
            continue
        
        # Create pre-visit reminder
        if appt.scheduled_date >= today:
            pre_visit_due = datetime.combine(
                appt.scheduled_date - timedelta(days=1),
                datetime.min.time().replace(hour=10)
            )
            
            # If due date is in the past but appointment is future, mark as pending
            pre_status = "pending"
            if pre_visit_due < datetime.now():
                pre_status = rng.choice(["completed", "completed", "pending", "failed"])
            
            pre_reminder = AppointmentReminder(
                appointment_id=appt.appointment_id,
                patient_context_id=appt.patient_context_id,
                reminder_type="pre_visit",
                channel=rng.choice(["sms", "sms", "email", "phone_call"]),
                scheduled_date=appt.scheduled_date - timedelta(days=1),
                due_date=pre_visit_due,
                status=pre_status,
                attempt_count=rng.randint(0, 2) if pre_status != "pending" else 0,
                created_at=datetime.utcnow(),
            )
            
            if pre_status == "completed":
                pre_reminder.completed_at = pre_visit_due + timedelta(hours=rng.randint(1, 4))
                pre_reminder.patient_responded = rng.choice([True, True, False])
            elif pre_status == "failed":
                pre_reminder.failed_at = pre_visit_due + timedelta(hours=2)
                pre_reminder.failure_reason = rng.choice([
                    "Invalid phone number", "Voicemail full", "No answer"
                ])
            
            db.add(pre_reminder)
            created_count += 1
        
        # Create post-visit reminder for completed appointments
        if appt.status == "completed":
            post_visit_due = datetime.combine(
                appt.scheduled_date + timedelta(days=3),
                datetime.min.time().replace(hour=14)
            )
            
            post_status = "pending"
            if post_visit_due < datetime.now():
                post_status = rng.choice(["completed", "completed", "pending"])
            
            post_reminder = AppointmentReminder(
                appointment_id=appt.appointment_id,
                patient_context_id=appt.patient_context_id,
                reminder_type="post_visit",
                channel=rng.choice(["sms", "email"]),
                scheduled_date=appt.scheduled_date + timedelta(days=3),
                due_date=post_visit_due,
                status=post_status,
                attempt_count=1 if post_status == "completed" else 0,
                created_at=datetime.utcnow(),
            )
            
            if post_status == "completed":
                post_reminder.completed_at = post_visit_due + timedelta(hours=1)
            
            db.add(post_reminder)
            created_count += 1
        
        # Create no-show follow-up reminder
        if appt.status == "no_show":
            noshow_due = datetime.combine(
                appt.scheduled_date + timedelta(days=1),
                datetime.min.time().replace(hour=9)
            )
            
            noshow_reminder = AppointmentReminder(
                appointment_id=appt.appointment_id,
                patient_context_id=appt.patient_context_id,
                reminder_type="no_show_follow_up",
                channel="phone_call",
                scheduled_date=appt.scheduled_date + timedelta(days=1),
                due_date=noshow_due,
                status="pending",
                staff_action=None,
                created_at=datetime.utcnow(),
            )
            
            db.add(noshow_reminder)
            created_count += 1
    
    db.commit()
    print(f"   Created {created_count} reminders")


def seed_intake_forms(db, tenant_id: uuid.UUID, appointments: list):
    """Create intake forms for appointments."""
    print("\n3. Seeding intake forms...")
    
    created_count = 0
    
    for appt in appointments:
        # Only create intake forms for scheduled/confirmed appointments
        if appt.status not in ["scheduled", "confirmed", "checked_in"]:
            continue
        
        rng = get_deterministic_random(f"intake-{appt.appointment_id}")
        
        # Check for existing forms
        existing = db.query(IntakeForm).filter(
            IntakeForm.patient_context_id == appt.patient_context_id
        ).first()
        
        if existing:
            continue
        
        # Create forms for this patient
        num_forms = rng.randint(3, len(FORM_TYPES))
        selected_forms = rng.sample(FORM_TYPES, num_forms)
        
        for form_type in selected_forms:
            # Randomly set completion status
            status_weights = ["completed"] * 3 + ["in_progress"] * 2 + ["not_started"]
            status = rng.choice(status_weights)
            
            total_fields = rng.randint(8, 20)
            if status == "completed":
                completed_fields = total_fields
                completion_pct = 100
            elif status == "in_progress":
                completed_fields = rng.randint(1, total_fields - 1)
                completion_pct = int((completed_fields / total_fields) * 100)
            else:
                completed_fields = 0
                completion_pct = 0
            
            form = IntakeForm(
                tenant_id=tenant_id,
                patient_context_id=appt.patient_context_id,
                form_type=form_type,
                form_name=form_type.replace("_", " ").title() + " Form",
                form_version="1.0",
                status=status,
                total_fields=total_fields,
                completed_fields=completed_fields,
                completion_percentage=completion_pct,
                started_at=datetime.utcnow() - timedelta(days=rng.randint(1, 7)) if status != "not_started" else None,
                completed_at=datetime.utcnow() - timedelta(hours=rng.randint(1, 48)) if status == "completed" else None,
                needs_review=(status == "completed" and rng.choice([True, False, False])),
                is_valid=(status == "completed"),
                created_at=datetime.utcnow(),
            )
            
            db.add(form)
            created_count += 1
    
    db.commit()
    print(f"   Created {created_count} intake forms")


def seed_insurance_verifications(db, tenant_id: uuid.UUID, appointments: list):
    """Create insurance verification records."""
    print("\n4. Seeding insurance verifications...")
    
    created_count = 0
    
    for appt in appointments:
        if appt.status in ["cancelled"]:
            continue
        
        rng = get_deterministic_random(f"insurance-{appt.appointment_id}")
        
        # Check for existing verification
        existing = db.query(InsuranceVerification).filter(
            InsuranceVerification.appointment_id == appt.appointment_id
        ).first()
        
        if existing:
            continue
        
        # Determine verification status
        if appt.status in ["checked_in", "in_progress", "completed"]:
            status = rng.choice(["verified", "verified", "verified", "failed"])
        else:
            status = rng.choice(["pending", "pending", "verified", "in_progress"])
        
        verification = InsuranceVerification(
            tenant_id=tenant_id,
            patient_context_id=appt.patient_context_id,
            appointment_id=appt.appointment_id,
            insurance_name=rng.choice(INSURANCE_NAMES),
            member_id=f"{rng.choice(['BCX', 'AET', 'UHC', 'CIG', 'HUM'])}-{rng.randint(100000, 999999)}",
            group_number=f"GRP-{rng.randint(1000, 9999)}",
            subscriber_name=None,  # Would come from patient data
            subscriber_relationship="self",
            status=status,
            verification_date=date.today() if status == "verified" else None,
            service_date=appt.scheduled_date,
            is_eligible=(status == "verified"),
            coverage_start_date=date.today() - timedelta(days=rng.randint(30, 365)) if status == "verified" else None,
            coverage_end_date=date.today() + timedelta(days=rng.randint(30, 365)) if status == "verified" else None,
            copay_amount=rng.choice([2000, 2500, 3000, 3500, 4000, 5000]) if status == "verified" else None,  # In cents
            deductible_amount=rng.choice([50000, 100000, 150000, 200000, 250000]) if status == "verified" else None,
            deductible_met=rng.randint(0, 100000) if status == "verified" else None,
            requires_prior_auth=rng.choice([True, False, False, False]),
            verified_at=datetime.utcnow() - timedelta(hours=rng.randint(1, 24)) if status == "verified" else None,
            failure_reason="Unable to verify with payer" if status == "failed" else None,
            created_at=datetime.utcnow(),
        )
        
        db.add(verification)
        created_count += 1
    
    db.commit()
    print(f"   Created {created_count} insurance verifications")


def seed_intake_checklists(db, tenant_id: uuid.UUID, appointments: list):
    """Create intake checklists for appointments."""
    print("\n5. Seeding intake checklists...")
    
    created_count = 0
    
    for appt in appointments:
        if appt.status in ["cancelled", "no_show"]:
            continue
        
        rng = get_deterministic_random(f"checklist-{appt.appointment_id}")
        
        # Check for existing checklist
        existing = db.query(IntakeChecklist).filter(
            IntakeChecklist.appointment_id == appt.appointment_id
        ).first()
        
        if existing:
            continue
        
        # Determine checklist completion based on appointment status
        if appt.status in ["completed", "in_progress"]:
            # Most items complete
            demographics_complete = True
            insurance_verified = True
            consent_signed = True
            hipaa_signed = True
            medical_history_complete = rng.choice([True, True, False])
            photo_id_verified = True
            insurance_card_scanned = True
            copay_collected = rng.choice([True, True, False])
        elif appt.status == "checked_in":
            # Some items complete
            demographics_complete = True
            insurance_verified = rng.choice([True, True, False])
            consent_signed = rng.choice([True, True, False])
            hipaa_signed = rng.choice([True, False])
            medical_history_complete = rng.choice([True, False])
            photo_id_verified = True
            insurance_card_scanned = rng.choice([True, False])
            copay_collected = False
        else:
            # Scheduled/confirmed - fewer items complete
            demographics_complete = rng.choice([True, True, False])
            insurance_verified = rng.choice([True, False, False])
            consent_signed = rng.choice([True, False, False])
            hipaa_signed = False
            medical_history_complete = rng.choice([True, False])
            photo_id_verified = False
            insurance_card_scanned = False
            copay_collected = False
        
        checklist = IntakeChecklist(
            tenant_id=tenant_id,
            patient_context_id=appt.patient_context_id,
            appointment_id=appt.appointment_id,
            demographics_complete=demographics_complete,
            insurance_verified=insurance_verified,
            consent_signed=consent_signed,
            hipaa_signed=hipaa_signed,
            medical_history_complete=medical_history_complete,
            photo_id_verified=photo_id_verified,
            insurance_card_scanned=insurance_card_scanned,
            copay_collected=copay_collected,
            has_issues=rng.choice([True, False, False, False, False]),
            issues=["Insurance card expired", "Missing signature on consent"] if rng.random() < 0.1 else None,
            created_at=datetime.utcnow(),
        )
        
        # Calculate status
        checklist.calculate_status()
        
        db.add(checklist)
        created_count += 1
    
    db.commit()
    print(f"   Created {created_count} intake checklists")


def main():
    print("=" * 60)
    print("Mobius OS - CRM/Scheduler Data Seeding")
    print("=" * 60)
    
    db = get_db_session()
    tenant_id = DEFAULT_TENANT_ID
    
    # Verify tenant exists
    from app.models.tenant import Tenant
    tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    if not tenant:
        print("\nERROR: Default tenant not found. Run seed_data.py first.")
        return
    
    print(f"\nUsing tenant: {tenant.name} ({tenant_id})")
    
    # Step 1: Create appointments
    appointments = seed_appointments(db, tenant_id)
    
    if not appointments:
        # If no new appointments were created, get existing ones
        today = date.today()
        appointments = db.query(Appointment).filter(
            Appointment.tenant_id == tenant_id,
            Appointment.scheduled_date >= today - timedelta(days=1)
        ).all()
        print(f"\n   Using {len(appointments)} existing appointments")
    
    # Step 2: Create reminders
    seed_reminders(db, tenant_id, appointments)
    
    # Step 3: Create intake forms
    seed_intake_forms(db, tenant_id, appointments)
    
    # Step 4: Create insurance verifications
    seed_insurance_verifications(db, tenant_id, appointments)
    
    # Step 5: Create intake checklists
    seed_intake_checklists(db, tenant_id, appointments)
    
    print("\n" + "=" * 60)
    print("CRM data seeding complete!")
    print("=" * 60)
    
    print("\nTo view the Mock CRM page:")
    print("  http://localhost:5001/mock-crm")
    print("\nAvailable styles:")
    print("  http://localhost:5001/mock-crm?style=modern")
    print("  http://localhost:5001/mock-crm?style=classic")
    print("  http://localhost:5001/mock-crm?style=healthcare_first")
    print("  http://localhost:5001/mock-crm?style=efficiency")


if __name__ == "__main__":
    main()
