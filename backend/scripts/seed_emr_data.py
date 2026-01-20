#!/usr/bin/env python3
"""
Seed script for Orders, Billing, and Messages data.

Run this after seed_crm_data.py to populate the EMR with realistic test data.
"""

import sys
import uuid
import random
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.postgres import get_db_session
from app.models import (
    PatientContext,
    Provider,
    ClinicalOrder,
    LabOrder,
    ImagingOrder,
    MedicationOrder,
    ReferralOrder,
    PatientInsurance,
    Charge,
    Claim,
    Payment,
    PatientStatement,
    MessageThread,
    Message,
    MessageTemplate,
)

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Sample lab orders
LAB_ORDERS = [
    {"name": "Complete Blood Count (CBC)", "code": "85025", "specimen": "Blood", "fasting": False},
    {"name": "Comprehensive Metabolic Panel", "code": "80053", "specimen": "Blood", "fasting": True},
    {"name": "Lipid Panel", "code": "80061", "specimen": "Blood", "fasting": True},
    {"name": "Hemoglobin A1C", "code": "83036", "specimen": "Blood", "fasting": False},
    {"name": "Thyroid Stimulating Hormone", "code": "84443", "specimen": "Blood", "fasting": False},
    {"name": "Urinalysis", "code": "81003", "specimen": "Urine", "fasting": False},
    {"name": "Basic Metabolic Panel", "code": "80048", "specimen": "Blood", "fasting": False},
    {"name": "Liver Function Panel", "code": "80076", "specimen": "Blood", "fasting": False},
    {"name": "PT/INR", "code": "85610", "specimen": "Blood", "fasting": False},
    {"name": "Vitamin D, 25-Hydroxy", "code": "82306", "specimen": "Blood", "fasting": False},
]

# Sample imaging orders
IMAGING_ORDERS = [
    {"name": "Chest X-Ray (2 views)", "code": "71046", "modality": "X-Ray", "body_part": "Chest"},
    {"name": "CT Abdomen/Pelvis with Contrast", "code": "74177", "modality": "CT", "body_part": "Abdomen/Pelvis", "contrast": True},
    {"name": "MRI Brain without Contrast", "code": "70551", "modality": "MRI", "body_part": "Brain"},
    {"name": "Ultrasound Abdomen Complete", "code": "76700", "modality": "Ultrasound", "body_part": "Abdomen"},
    {"name": "X-Ray Knee (3 views)", "code": "73562", "modality": "X-Ray", "body_part": "Knee"},
    {"name": "Mammogram Screening Bilateral", "code": "77067", "modality": "Mammography", "body_part": "Breast"},
    {"name": "DEXA Bone Density", "code": "77080", "modality": "DEXA", "body_part": "Hip/Spine"},
    {"name": "CT Head without Contrast", "code": "70450", "modality": "CT", "body_part": "Head"},
]

# Sample medications
MEDICATIONS = [
    {"name": "Lisinopril 10mg", "generic": "Lisinopril", "dose": "10mg", "route": "Oral", "frequency": "Once daily", "quantity": 30},
    {"name": "Metformin 500mg", "generic": "Metformin", "dose": "500mg", "route": "Oral", "frequency": "Twice daily", "quantity": 60},
    {"name": "Atorvastatin 20mg", "generic": "Atorvastatin", "dose": "20mg", "route": "Oral", "frequency": "Once daily at bedtime", "quantity": 30},
    {"name": "Amlodipine 5mg", "generic": "Amlodipine", "dose": "5mg", "route": "Oral", "frequency": "Once daily", "quantity": 30},
    {"name": "Omeprazole 20mg", "generic": "Omeprazole", "dose": "20mg", "route": "Oral", "frequency": "Once daily before breakfast", "quantity": 30},
    {"name": "Levothyroxine 50mcg", "generic": "Levothyroxine", "dose": "50mcg", "route": "Oral", "frequency": "Once daily on empty stomach", "quantity": 30},
    {"name": "Gabapentin 300mg", "generic": "Gabapentin", "dose": "300mg", "route": "Oral", "frequency": "Three times daily", "quantity": 90},
    {"name": "Sertraline 50mg", "generic": "Sertraline", "dose": "50mg", "route": "Oral", "frequency": "Once daily", "quantity": 30},
]

# Sample referral specialties
REFERRAL_SPECIALTIES = [
    {"specialty": "Cardiology", "facility": "Heart Care Associates", "reason": "Chest pain evaluation"},
    {"specialty": "Orthopedics", "facility": "Bone & Joint Center", "reason": "Knee pain - possible meniscus tear"},
    {"specialty": "Gastroenterology", "facility": "Digestive Health Clinic", "reason": "GERD management"},
    {"specialty": "Dermatology", "facility": "Skin Care Specialists", "reason": "Suspicious mole evaluation"},
    {"specialty": "Neurology", "facility": "Brain & Spine Institute", "reason": "Chronic headaches"},
    {"specialty": "Endocrinology", "facility": "Diabetes & Hormone Center", "reason": "Thyroid nodule"},
]

# Sample insurance payers
INSURANCE_PAYERS = [
    {"name": "Blue Cross Blue Shield", "payer_id": "BCBS001", "plan_type": "PPO", "copay": 25},
    {"name": "Aetna", "payer_id": "AETNA01", "plan_type": "HMO", "copay": 20},
    {"name": "United Healthcare", "payer_id": "UHC0001", "plan_type": "PPO", "copay": 30},
    {"name": "Cigna", "payer_id": "CIGNA01", "plan_type": "EPO", "copay": 25},
    {"name": "Medicare", "payer_id": "MED0001", "plan_type": "Medicare", "copay": 0},
    {"name": "Medicaid", "payer_id": "MCAID01", "plan_type": "Medicaid", "copay": 0},
    {"name": "Humana", "payer_id": "HUMANA1", "plan_type": "PPO", "copay": 25},
]

# Sample CPT codes for charges
CPT_CODES = [
    {"code": "99213", "description": "Office Visit - Established Patient (Level 3)", "charge": 150.00},
    {"code": "99214", "description": "Office Visit - Established Patient (Level 4)", "charge": 200.00},
    {"code": "99203", "description": "Office Visit - New Patient (Level 3)", "charge": 175.00},
    {"code": "99204", "description": "Office Visit - New Patient (Level 4)", "charge": 250.00},
    {"code": "36415", "description": "Venipuncture", "charge": 25.00},
    {"code": "93000", "description": "ECG with Interpretation", "charge": 75.00},
    {"code": "90471", "description": "Immunization Administration", "charge": 35.00},
    {"code": "99395", "description": "Preventive Visit 18-39 years", "charge": 225.00},
]

# Sample message templates
MESSAGE_TEMPLATES = [
    {
        "name": "Appointment Reminder",
        "category": "appointment",
        "subject": "Appointment Reminder - {appointment_date}",
        "body": "Dear {patient_name},\n\nThis is a reminder that you have an appointment scheduled for {appointment_date} at {appointment_time}.\n\nPlease arrive 15 minutes early to complete any necessary paperwork.\n\nIf you need to reschedule, please call us at (555) 123-4567.\n\nThank you,\nYour Care Team",
    },
    {
        "name": "Lab Results Available",
        "category": "lab_results",
        "subject": "Your Lab Results Are Ready",
        "body": "Dear {patient_name},\n\nYour recent lab results are now available in your patient portal.\n\nPlease log in to review your results. If you have any questions or concerns, please don't hesitate to contact our office.\n\nBest regards,\nYour Care Team",
    },
    {
        "name": "Prescription Refill",
        "category": "prescription",
        "subject": "Prescription Refill Request",
        "body": "Dear {patient_name},\n\nWe have received your prescription refill request for {medication_name}.\n\nYour prescription has been sent to {pharmacy_name} and should be ready for pickup within 24 hours.\n\nThank you,\nYour Care Team",
    },
    {
        "name": "Balance Due",
        "category": "billing",
        "subject": "Account Balance Notification",
        "body": "Dear {patient_name},\n\nThis is a friendly reminder that you have an outstanding balance of ${balance_due} on your account.\n\nPlease log in to your patient portal to make a payment or contact our billing department at (555) 123-4568.\n\nThank you,\nBilling Department",
    },
]


def get_random_date_in_past(days_back=90):
    """Get a random date in the past."""
    return date.today() - timedelta(days=random.randint(1, days_back))


def get_random_date_in_future(days_ahead=30):
    """Get a random date in the future."""
    return date.today() + timedelta(days=random.randint(1, days_ahead))


def seed_orders(db, tenant_id, patients, providers):
    """Seed clinical orders for patients."""
    print("\n--- Seeding Clinical Orders ---")
    
    orders_created = {"lab": 0, "imaging": 0, "medication": 0, "referral": 0}
    
    for patient in patients:
        patient_context_id = patient.patient_context_id
        
        # Create 2-4 lab orders per patient
        for _ in range(random.randint(2, 4)):
            lab_info = random.choice(LAB_ORDERS)
            provider = random.choice(providers) if providers else None
            order_date = get_random_date_in_past(60)
            
            # Determine status
            status = random.choices(
                ["completed", "pending", "in_progress"],
                weights=[0.6, 0.25, 0.15]
            )[0]
            
            clinical_order = ClinicalOrder(
                tenant_id=tenant_id,
                patient_context_id=patient_context_id,
                order_type="lab",
                order_name=lab_info["name"],
                order_code=lab_info["code"],
                status=status,
                priority=random.choice(["routine", "urgent"]),
                ordering_provider_id=provider.provider_id if provider else None,
                ordering_provider_name=provider.provider_name if provider else "Dr. Smith",
                diagnosis_codes=["Z00.00", "R73.9"] if lab_info["fasting"] else ["Z00.00"],
                ordered_at=datetime.combine(order_date, datetime.min.time()),
                result_date=datetime.combine(order_date + timedelta(days=2), datetime.min.time()) if status == "completed" else None,
                result_status="normal" if status == "completed" and random.random() > 0.2 else ("abnormal" if status == "completed" else None),
                result_summary="Results within normal limits" if status == "completed" else None,
            )
            db.add(clinical_order)
            db.flush()
            
            lab_order = LabOrder(
                order_id=clinical_order.order_id,
                tenant_id=tenant_id,
                specimen_type=lab_info["specimen"],
                fasting_required=lab_info["fasting"],
                lab_name="Quest Diagnostics",
                collected_at=datetime.combine(order_date + timedelta(days=1), datetime.min.time()) if status != "pending" else None,
            )
            db.add(lab_order)
            orders_created["lab"] += 1
        
        # Create 0-2 imaging orders per patient
        for _ in range(random.randint(0, 2)):
            imaging_info = random.choice(IMAGING_ORDERS)
            provider = random.choice(providers) if providers else None
            order_date = get_random_date_in_past(90)
            status = random.choices(["completed", "pending", "scheduled"], weights=[0.5, 0.3, 0.2])[0]
            
            clinical_order = ClinicalOrder(
                tenant_id=tenant_id,
                patient_context_id=patient_context_id,
                order_type="imaging",
                order_name=imaging_info["name"],
                order_code=imaging_info["code"],
                status=status,
                priority="routine",
                ordering_provider_id=provider.provider_id if provider else None,
                ordering_provider_name=provider.provider_name if provider else "Dr. Smith",
                performing_facility="Community Radiology Center",
                scheduled_date=order_date + timedelta(days=7) if status == "scheduled" else None,
                ordered_at=datetime.combine(order_date, datetime.min.time()),
            )
            db.add(clinical_order)
            db.flush()
            
            imaging_order = ImagingOrder(
                order_id=clinical_order.order_id,
                tenant_id=tenant_id,
                modality=imaging_info["modality"],
                body_part=imaging_info["body_part"],
                contrast=imaging_info.get("contrast", False),
                report_status="Final" if status == "completed" else None,
                impression="No acute findings" if status == "completed" else None,
            )
            db.add(imaging_order)
            orders_created["imaging"] += 1
        
        # Create 1-3 medication orders per patient
        for _ in range(random.randint(1, 3)):
            med_info = random.choice(MEDICATIONS)
            provider = random.choice(providers) if providers else None
            order_date = get_random_date_in_past(30)
            
            clinical_order = ClinicalOrder(
                tenant_id=tenant_id,
                patient_context_id=patient_context_id,
                order_type="medication",
                order_name=med_info["name"],
                status=random.choice(["completed", "pending"]),
                priority="routine",
                ordering_provider_id=provider.provider_id if provider else None,
                ordering_provider_name=provider.provider_name if provider else "Dr. Smith",
                ordered_at=datetime.combine(order_date, datetime.min.time()),
            )
            db.add(clinical_order)
            db.flush()
            
            medication_order = MedicationOrder(
                order_id=clinical_order.order_id,
                tenant_id=tenant_id,
                medication_name=med_info["name"],
                generic_name=med_info["generic"],
                dose=med_info["dose"],
                route=med_info["route"],
                frequency=med_info["frequency"],
                quantity=med_info["quantity"],
                refills=random.randint(0, 3),
                instructions=f"Take {med_info['dose']} {med_info['frequency']}",
                pharmacy_name="CVS Pharmacy",
                dispense_status=random.choice(["New", "Filled", "Picked Up"]),
                start_date=order_date,
                end_date=order_date + timedelta(days=30),
            )
            db.add(medication_order)
            orders_created["medication"] += 1
        
        # Create 0-1 referral order per patient
        if random.random() > 0.5:
            ref_info = random.choice(REFERRAL_SPECIALTIES)
            provider = random.choice(providers) if providers else None
            order_date = get_random_date_in_past(60)
            
            clinical_order = ClinicalOrder(
                tenant_id=tenant_id,
                patient_context_id=patient_context_id,
                order_type="referral",
                order_name=f"Referral to {ref_info['specialty']}",
                status=random.choice(["completed", "pending", "submitted"]),
                priority="routine",
                ordering_provider_id=provider.provider_id if provider else None,
                ordering_provider_name=provider.provider_name if provider else "Dr. Smith",
                performing_facility=ref_info["facility"],
                clinical_notes=ref_info["reason"],
                ordered_at=datetime.combine(order_date, datetime.min.time()),
            )
            db.add(clinical_order)
            db.flush()
            
            referral_order = ReferralOrder(
                order_id=clinical_order.order_id,
                tenant_id=tenant_id,
                specialty=ref_info["specialty"],
                referred_to_facility=ref_info["facility"],
                reason_for_referral=ref_info["reason"],
                auth_required=random.choice([True, False]),
                auth_status="Approved" if random.random() > 0.3 else "Pending",
                visits_authorized=random.randint(1, 6) if random.random() > 0.3 else None,
            )
            db.add(referral_order)
            orders_created["referral"] += 1
    
    db.commit()
    print(f"   Created {orders_created['lab']} lab orders")
    print(f"   Created {orders_created['imaging']} imaging orders")
    print(f"   Created {orders_created['medication']} medication orders")
    print(f"   Created {orders_created['referral']} referral orders")


def seed_billing(db, tenant_id, patients, providers):
    """Seed billing data for patients."""
    print("\n--- Seeding Billing Data ---")
    
    insurance_count = 0
    charge_count = 0
    claim_count = 0
    payment_count = 0
    
    for patient in patients:
        patient_context_id = patient.patient_context_id
        
        # Create insurance for each patient
        payer = random.choice(INSURANCE_PAYERS)
        
        insurance = PatientInsurance(
            tenant_id=tenant_id,
            patient_context_id=patient_context_id,
            coverage_type="primary",
            payer_name=payer["name"],
            payer_id=payer["payer_id"],
            policy_number=f"POL{random.randint(100000, 999999)}",
            group_number=f"GRP{random.randint(1000, 9999)}",
            plan_type=payer["plan_type"],
            copay_amount=Decimal(str(payer["copay"])),
            deductible=Decimal(str(random.choice([500, 1000, 1500, 2500]))),
            deductible_met=Decimal(str(random.randint(0, 1500))),
            verified=True,
            verified_at=datetime.now() - timedelta(days=random.randint(1, 30)),
            eligibility_status="Active",
            effective_date=date.today() - timedelta(days=random.randint(180, 365)),
        )
        db.add(insurance)
        db.flush()
        insurance_count += 1
        
        # Create 2-5 charges per patient
        charges = []
        total_charges = Decimal("0")
        
        for _ in range(random.randint(2, 5)):
            cpt_info = random.choice(CPT_CODES)
            service_date = get_random_date_in_past(60)
            charge_amount = Decimal(str(cpt_info["charge"]))
            total_charges += charge_amount
            
            provider = random.choice(providers) if providers else None
            
            charge = Charge(
                tenant_id=tenant_id,
                patient_context_id=patient_context_id,
                service_date=service_date,
                cpt_code=cpt_info["code"],
                description=cpt_info["description"],
                units=Decimal("1"),
                unit_charge=charge_amount,
                total_charge=charge_amount,
                rendering_provider_id=provider.provider_id if provider else None,
                rendering_provider_name=provider.provider_name if provider else "Dr. Smith",
                place_of_service="11",
                status=random.choice(["billed", "paid", "pending"]),
                posted_at=datetime.combine(service_date, datetime.min.time()),
            )
            db.add(charge)
            charges.append(charge)
            charge_count += 1
        
        db.flush()
        
        # Create a claim for half the patients
        if random.random() > 0.5 and charges:
            service_dates = [c.service_date for c in charges]
            claim_status = random.choice(["submitted", "paid", "pending", "denied"])
            
            paid_amount = Decimal("0")
            if claim_status == "paid":
                paid_amount = total_charges * Decimal("0.8")  # 80% payment
            
            claim = Claim(
                tenant_id=tenant_id,
                patient_context_id=patient_context_id,
                claim_number=f"CLM{random.randint(100000, 999999)}",
                insurance_id=insurance.insurance_id,
                payer_name=payer["name"],
                service_date_from=min(service_dates),
                service_date_to=max(service_dates),
                diagnosis_codes=["Z00.00", "R10.9"],
                total_charges=total_charges,
                allowed_amount=total_charges * Decimal("0.85") if claim_status in ["paid", "pending"] else None,
                paid_amount=paid_amount,
                patient_responsibility=total_charges - paid_amount if claim_status == "paid" else None,
                status=claim_status,
                submitted_at=datetime.now() - timedelta(days=random.randint(10, 45)),
                paid_at=datetime.now() - timedelta(days=random.randint(1, 10)) if claim_status == "paid" else None,
                denial_reason="Missing information" if claim_status == "denied" else None,
            )
            db.add(claim)
            db.flush()
            claim_count += 1
            
            # Update charges with claim_id
            for charge in charges:
                charge.claim_id = claim.claim_id
            
            # Create payment if claim is paid
            if claim_status == "paid":
                payment = Payment(
                    tenant_id=tenant_id,
                    patient_context_id=patient_context_id,
                    payment_source="insurance",
                    payer_name=payer["name"],
                    payment_date=date.today() - timedelta(days=random.randint(1, 10)),
                    amount=paid_amount,
                    payment_method="EFT",
                    reference_number=f"ERA{random.randint(100000, 999999)}",
                    claim_id=claim.claim_id,
                    posted_at=datetime.now(),
                )
                db.add(payment)
                payment_count += 1
        
        # Create patient payment for some patients
        if random.random() > 0.6:
            payment = Payment(
                tenant_id=tenant_id,
                patient_context_id=patient_context_id,
                payment_source="patient",
                payment_date=date.today() - timedelta(days=random.randint(1, 30)),
                amount=Decimal(str(payer["copay"])),
                payment_method=random.choice(["Credit Card", "Cash", "Check"]),
                check_number=f"{random.randint(1000, 9999)}" if random.random() > 0.5 else None,
                posted_at=datetime.now(),
            )
            db.add(payment)
            payment_count += 1
    
    db.commit()
    print(f"   Created {insurance_count} insurance records")
    print(f"   Created {charge_count} charges")
    print(f"   Created {claim_count} claims")
    print(f"   Created {payment_count} payments")


def seed_messages(db, tenant_id, patients, providers):
    """Seed messages for patients."""
    print("\n--- Seeding Messages ---")
    
    thread_count = 0
    message_count = 0
    
    # Create message templates
    for template in MESSAGE_TEMPLATES:
        existing = db.query(MessageTemplate).filter(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.name == template["name"]
        ).first()
        
        if not existing:
            msg_template = MessageTemplate(
                tenant_id=tenant_id,
                name=template["name"],
                category=template["category"],
                subject_template=template["subject"],
                body_template=template["body"],
                is_system=True,
            )
            db.add(msg_template)
    
    db.flush()
    print(f"   Created {len(MESSAGE_TEMPLATES)} message templates")
    
    # Create message threads for patients
    for patient in patients:
        patient_context_id = patient.patient_context_id
        
        # Create 1-3 message threads per patient
        for _ in range(random.randint(1, 3)):
            category = random.choice(["general", "clinical", "prescription", "appointment", "billing"])
            provider = random.choice(providers) if providers else None
            
            subjects = {
                "general": ["Question about my visit", "Follow-up question", "Thank you"],
                "clinical": ["Symptoms update", "Question about diagnosis", "Test results question"],
                "prescription": ["Refill request", "Medication side effects", "Need new prescription"],
                "appointment": ["Reschedule request", "Cancel appointment", "New appointment needed"],
                "billing": ["Bill question", "Payment plan request", "Insurance question"],
            }
            
            subject = random.choice(subjects[category])
            thread_status = random.choice(["open", "closed"])
            
            thread = MessageThread(
                tenant_id=tenant_id,
                patient_context_id=patient_context_id,
                subject=subject,
                category=category,
                thread_type="patient_portal",
                priority=random.choice(["normal", "high"]) if category == "clinical" else "normal",
                status=thread_status,
                assigned_pool=random.choice(["Nursing", "Front Desk", "Billing"]),
                message_count=0,
                unread_count=0,
            )
            db.add(thread)
            db.flush()
            thread_count += 1
            
            # Create initial message from patient
            message_bodies = {
                "general": "Hello, I have a question about my recent visit. Can someone please help me?",
                "clinical": "I wanted to update you on my symptoms. The medication seems to be helping but I still have some concerns.",
                "prescription": "I need a refill on my medication. Can you please send it to my pharmacy?",
                "appointment": "I need to reschedule my upcoming appointment. What times are available?",
                "billing": "I received a bill and I'm not sure what some of the charges are for. Can someone explain?",
            }
            
            patient_msg = Message(
                thread_id=thread.thread_id,
                tenant_id=tenant_id,
                sender_type="patient",
                sender_name="Patient",
                body=message_bodies[category],
                sent_at=datetime.now() - timedelta(days=random.randint(1, 14), hours=random.randint(0, 23)),
            )
            db.add(patient_msg)
            message_count += 1
            
            # Add staff response for some threads
            if random.random() > 0.3:
                staff_responses = {
                    "general": "Thank you for reaching out. I'd be happy to help answer your questions.",
                    "clinical": "Thank you for the update. I've reviewed your message and forwarded it to your provider.",
                    "prescription": "I've processed your refill request. It should be ready at your pharmacy within 24 hours.",
                    "appointment": "I can help you reschedule. We have availability tomorrow at 2pm or Thursday at 10am.",
                    "billing": "I'd be happy to explain your bill. The charges include your office visit and lab work.",
                }
                
                staff_msg = Message(
                    thread_id=thread.thread_id,
                    tenant_id=tenant_id,
                    sender_type="staff",
                    sender_name=provider.provider_name if provider else "Care Team",
                    body=staff_responses[category],
                    sent_at=datetime.now() - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23)),
                )
                db.add(staff_msg)
                message_count += 1
                thread.message_count = 2
            else:
                thread.message_count = 1
                thread.unread_count = 1
            
            thread.last_message_at = datetime.now() - timedelta(days=random.randint(0, 7))
    
    db.commit()
    print(f"   Created {thread_count} message threads")
    print(f"   Created {message_count} messages")


def main():
    """Main function to seed EMR data."""
    print("=" * 60)
    print("EMR Data Seeding (Orders, Billing, Messages)")
    print("=" * 60)
    
    db = get_db_session()
    tenant_id = DEFAULT_TENANT_ID
    
    # Get existing patients and providers
    patients = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).all()
    
    providers = db.query(Provider).filter(
        Provider.tenant_id == tenant_id,
        Provider.is_active == True
    ).all()
    
    print(f"\nFound {len(patients)} patients and {len(providers)} providers")
    
    if not patients:
        print("\nNo patients found! Please run seed_data.py first.")
        return
    
    # Seed data
    seed_orders(db, tenant_id, patients, providers)
    seed_billing(db, tenant_id, patients, providers)
    seed_messages(db, tenant_id, patients, providers)
    
    print("\n" + "=" * 60)
    print("EMR data seeding complete!")
    print("=" * 60)
    print("\nTo view the Unified EMR page:")
    print("  http://localhost:5001/mock-emr")
    print("\nAvailable tabs: Chart, Scheduling, Orders, Billing, Messages")


if __name__ == "__main__":
    main()
