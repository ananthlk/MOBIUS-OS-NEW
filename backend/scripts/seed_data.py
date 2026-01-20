#!/usr/bin/env python3
"""
Database seeding script.

Creates default tenant, sample patient data, patient_ids (ID translation layer),
and mock_emr (clinical data) for development/testing.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/seed_data.py
"""

import sys
import random
import hashlib
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.agents.patient_data_agent import PatientDataAgent
from app.db.postgres import get_db_session
from app.models.patient_ids import PatientId
from app.models.mock_emr import MockEmrRecord
from app.models.patient import PatientContext


# Sample data for patient_ids (ID translation layer)
PATIENT_IDS_DATA = {
    "1234567890": [  # Jane Doe
        {"id_type": "mrn", "id_value": "MRN-00123456", "source_system": "mock_emr", "is_primary": True},
        {"id_type": "insurance", "id_value": "BCX-445566", "source_system": "blue_cross", "is_primary": True},
    ],
    "9876543210": [  # John Smith
        {"id_type": "mrn", "id_value": "MRN-00987654", "source_system": "mock_emr", "is_primary": True},
        {"id_type": "insurance", "id_value": "AET-778899", "source_system": "aetna", "is_primary": True},
    ],
    "1234500000": [  # Janet Doe
        {"id_type": "mrn", "id_value": "MRN-00123450", "source_system": "mock_emr", "is_primary": True},
    ],
    "5551200001": [  # Jimmy Dean
        {"id_type": "mrn", "id_value": "MRN-00555120", "source_system": "mock_emr", "is_primary": True},
        {"id_type": "insurance", "id_value": "MCR-112233", "source_system": "medicare", "is_primary": True},
    ],
    "7778889999": [  # Sarah Johnson
        {"id_type": "mrn", "id_value": "MRN-00777888", "source_system": "mock_emr", "is_primary": True},
        {"id_type": "insurance", "id_value": "UHC-334455", "source_system": "united_health", "is_primary": True},
    ],
}

# Sample data for mock_emr (clinical data)
MOCK_EMR_DATA = {
    "1234567890": {  # Jane Doe
        "allergies": ["Penicillin"],
        "medications": [
            {"name": "Lisinopril", "dose": "10mg", "frequency": "Daily"},
        ],
        "vitals": {"bp": "118/76", "hr": 68, "temp": 98.4, "weight_lbs": 142, "height_in": 64},
        "recent_visits": [
            {"date": "2026-01-10", "type": "Annual Physical", "provider": "Dr. Emily Williams", "reason": "Routine checkup"},
        ],
        "primary_care_provider": "Dr. Emily Williams",
        "emergency_contact_name": "John Doe",
        "emergency_contact_phone": "555-123-4567",
        "emergency_contact_relation": "Spouse",
        "blood_type": "A+",
    },
    "9876543210": {  # John Smith
        "allergies": ["Sulfa", "Latex"],
        "medications": [
            {"name": "Metformin", "dose": "500mg", "frequency": "BID"},
            {"name": "Atorvastatin", "dose": "20mg", "frequency": "Daily"},
        ],
        "vitals": {"bp": "132/84", "hr": 78, "temp": 98.6, "weight_lbs": 195, "height_in": 70},
        "recent_visits": [
            {"date": "2026-01-05", "type": "Follow-up", "provider": "Dr. Robert Johnson", "reason": "Diabetes management"},
            {"date": "2025-12-15", "type": "Lab Work", "provider": "Lab Corp", "reason": "A1C test"},
        ],
        "primary_care_provider": "Dr. Robert Johnson",
        "emergency_contact_name": "Mary Smith",
        "emergency_contact_phone": "555-987-6543",
        "emergency_contact_relation": "Wife",
        "blood_type": "O+",
    },
    "1234500000": {  # Janet Doe
        "allergies": [],
        "medications": [],
        "vitals": {"bp": "125/82", "hr": 72, "temp": 98.6, "weight_lbs": 155, "height_in": 66},
        "recent_visits": [],
        "primary_care_provider": "Dr. Michael Brown",
        "emergency_contact_name": "Jane Doe",
        "emergency_contact_phone": "555-111-2222",
        "emergency_contact_relation": "Sister",
        "blood_type": "A-",
    },
    "5551200001": {  # Jimmy Dean - Critical
        "allergies": ["Penicillin", "Aspirin", "Codeine"],
        "medications": [
            {"name": "Warfarin", "dose": "5mg", "frequency": "Daily"},
        ],
        "vitals": {"bp": "158/98", "hr": 92, "temp": 99.1, "weight_lbs": 210, "height_in": 68},
        "recent_visits": [
            {"date": "2026-01-15", "type": "Urgent Care", "provider": "Dr. Adams", "reason": "Drug interaction review - CRITICAL"},
            {"date": "2026-01-12", "type": "ER Visit", "provider": "Metro Hospital", "reason": "Chest pain evaluation"},
        ],
        "primary_care_provider": "Dr. Sarah Miller",
        "emergency_contact_name": "Betty Dean",
        "emergency_contact_phone": "555-444-5555",
        "emergency_contact_relation": "Wife",
        "blood_type": "B-",
    },
    "7778889999": {  # Sarah Johnson
        "allergies": ["Shellfish"],
        "medications": [
            {"name": "Levothyroxine", "dose": "50mcg", "frequency": "Daily"},
        ],
        "vitals": {"bp": "110/70", "hr": 65, "temp": 98.2, "weight_lbs": 135, "height_in": 65},
        "recent_visits": [
            {"date": "2026-01-08", "type": "Specialist", "provider": "Dr. Chen", "reason": "Thyroid follow-up"},
        ],
        "primary_care_provider": "Dr. Lisa Park",
        "emergency_contact_name": "Tom Johnson",
        "emergency_contact_phone": "555-666-7777",
        "emergency_contact_relation": "Husband",
        "blood_type": "AB+",
    },
}


def seed_patient_ids(db, tenant_id):
    """Seed patient_ids table with MRN and insurance ID mappings."""
    print("\n3. Seeding patient_ids (ID translation layer)...")
    
    created_count = 0
    for patient_key, id_records in PATIENT_IDS_DATA.items():
        # Find the patient_context for this patient_key
        context = db.query(PatientContext).filter(
            PatientContext.tenant_id == tenant_id,
            PatientContext.patient_key == patient_key,
        ).first()
        
        if not context:
            print(f"   WARNING: Patient context not found for {patient_key}")
            continue
        
        for id_data in id_records:
            # Check if this ID already exists
            existing = db.query(PatientId).filter(
                PatientId.id_type == id_data["id_type"],
                PatientId.id_value == id_data["id_value"],
            ).first()
            
            if existing:
                print(f"   - Skipping existing: {id_data['id_type']}={id_data['id_value']}")
                continue
            
            patient_id = PatientId(
                patient_context_id=context.patient_context_id,
                id_type=id_data["id_type"],
                id_value=id_data["id_value"],
                source_system=id_data.get("source_system"),
                is_primary=id_data.get("is_primary", False),
                created_at=datetime.utcnow(),
            )
            db.add(patient_id)
            created_count += 1
            print(f"   + {id_data['id_type']}={id_data['id_value']} -> {patient_key}")
    
    db.commit()
    print(f"\n   Created {created_count} patient ID records")


def seed_patient_ids_for_all_patients(db, tenant_id):
    """Generate patient_ids (MRN) for ALL patients that don't have them yet."""
    print("\n3b. Generating patient_ids for remaining patients...")
    
    # Get all patient contexts for this tenant
    contexts = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).all()
    
    total = len(contexts)
    created_count = 0
    skipped_count = 0
    
    for context in contexts:
        # Check if this patient already has an MRN
        existing_mrn = db.query(PatientId).filter(
            PatientId.patient_context_id == context.patient_context_id,
            PatientId.id_type == "mrn",
        ).first()
        
        if existing_mrn:
            skipped_count += 1
            continue
        
        # Generate MRN from patient_key (deterministic)
        # Take last 8 digits of patient_key hash for MRN
        mrn_num = int(hashlib.md5(context.patient_key.encode()).hexdigest(), 16) % 100000000
        mrn_value = f"MRN-{mrn_num:08d}"
        
        # Check if this MRN already exists (collision check)
        existing = db.query(PatientId).filter(
            PatientId.id_type == "mrn",
            PatientId.id_value == mrn_value,
        ).first()
        
        if existing:
            # Add suffix to make unique
            mrn_value = f"MRN-{mrn_num:08d}-{context.patient_key[-4:]}"
        
        patient_id = PatientId(
            patient_context_id=context.patient_context_id,
            id_type="mrn",
            id_value=mrn_value,
            source_system="mock_emr",
            is_primary=True,
            created_at=datetime.utcnow(),
        )
        db.add(patient_id)
        created_count += 1
        
        # Commit in batches
        if created_count % 100 == 0:
            print(f"   ... processed {created_count} patients")
            db.commit()
    
    db.commit()
    print(f"\n   Generated {created_count} new MRN records")
    print(f"   Skipped {skipped_count} patients (already had MRN)")


# Sample data pools for generating random clinical data
ALLERGY_POOL = [
    "Penicillin", "Sulfa", "Aspirin", "Ibuprofen", "Codeine", "Morphine",
    "Latex", "Shellfish", "Peanuts", "Tree Nuts", "Eggs", "Milk", "Soy",
    "Wheat", "Fish", "Sesame", "Bee Stings", "Contrast Dye", "Lidocaine"
]

MEDICATION_POOL = [
    {"name": "Lisinopril", "doses": ["5mg", "10mg", "20mg"], "freq": "Daily"},
    {"name": "Metformin", "doses": ["500mg", "850mg", "1000mg"], "freq": "BID"},
    {"name": "Atorvastatin", "doses": ["10mg", "20mg", "40mg"], "freq": "Daily"},
    {"name": "Omeprazole", "doses": ["20mg", "40mg"], "freq": "Daily"},
    {"name": "Amlodipine", "doses": ["5mg", "10mg"], "freq": "Daily"},
    {"name": "Metoprolol", "doses": ["25mg", "50mg", "100mg"], "freq": "BID"},
    {"name": "Levothyroxine", "doses": ["25mcg", "50mcg", "75mcg", "100mcg"], "freq": "Daily"},
    {"name": "Gabapentin", "doses": ["100mg", "300mg", "600mg"], "freq": "TID"},
    {"name": "Hydrochlorothiazide", "doses": ["12.5mg", "25mg"], "freq": "Daily"},
    {"name": "Losartan", "doses": ["25mg", "50mg", "100mg"], "freq": "Daily"},
    {"name": "Simvastatin", "doses": ["10mg", "20mg", "40mg"], "freq": "Daily"},
    {"name": "Pantoprazole", "doses": ["20mg", "40mg"], "freq": "Daily"},
    {"name": "Furosemide", "doses": ["20mg", "40mg", "80mg"], "freq": "Daily"},
    {"name": "Prednisone", "doses": ["5mg", "10mg", "20mg"], "freq": "Daily"},
    {"name": "Tramadol", "doses": ["50mg", "100mg"], "freq": "Q6H PRN"},
]

PROVIDER_POOL = [
    "Dr. Emily Williams", "Dr. Robert Johnson", "Dr. Sarah Miller", "Dr. Michael Brown",
    "Dr. Lisa Park", "Dr. James Chen", "Dr. Maria Garcia", "Dr. David Lee",
    "Dr. Jennifer Adams", "Dr. Christopher Taylor", "Dr. Amanda White", "Dr. Thomas Moore",
    "Dr. Elizabeth Clark", "Dr. Daniel Martinez", "Dr. Susan Anderson", "Dr. Richard Wilson"
]

BLOOD_TYPES = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

VISIT_TYPES = [
    "Annual Physical", "Follow-up", "Sick Visit", "Lab Work", "Specialist Referral",
    "Urgent Care", "Medication Review", "Preventive Care", "Chronic Care Management"
]

RELATIONS = ["Spouse", "Parent", "Child", "Sibling", "Friend", "Partner"]


def generate_random_emr_data(patient_key: str, display_name: str) -> dict:
    """Generate deterministic random EMR data based on patient_key hash."""
    # Use patient_key hash for deterministic randomness
    seed = int(hashlib.md5(patient_key.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    
    # Generate allergies (0-3)
    num_allergies = rng.randint(0, 3)
    allergies = rng.sample(ALLERGY_POOL, num_allergies) if num_allergies > 0 else []
    
    # Generate medications (0-4)
    num_meds = rng.randint(0, 4)
    medications = []
    if num_meds > 0:
        med_samples = rng.sample(MEDICATION_POOL, num_meds)
        for med in med_samples:
            medications.append({
                "name": med["name"],
                "dose": rng.choice(med["doses"]),
                "frequency": med["freq"]
            })
    
    # Generate vitals
    vitals = {
        "bp": f"{rng.randint(100, 150)}/{rng.randint(60, 95)}",
        "hr": rng.randint(55, 100),
        "temp": round(rng.uniform(97.5, 99.5), 1),
        "weight_lbs": rng.randint(110, 250),
        "height_in": rng.randint(60, 76)
    }
    
    # Generate recent visits (0-2)
    num_visits = rng.randint(0, 2)
    recent_visits = []
    if num_visits > 0:
        for i in range(num_visits):
            day = rng.randint(1, 28)
            month = rng.randint(1, 12)
            recent_visits.append({
                "date": f"2025-{month:02d}-{day:02d}",
                "type": rng.choice(VISIT_TYPES),
                "provider": rng.choice(PROVIDER_POOL),
                "reason": "Routine visit"
            })
    
    # Generate emergency contact
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Mary", "Robert", "Lisa"]
    last_name = display_name.split()[-1] if display_name else "Doe"
    ec_first = rng.choice(first_names)
    
    return {
        "allergies": allergies,
        "medications": medications,
        "vitals": vitals,
        "recent_visits": recent_visits,
        "primary_care_provider": rng.choice(PROVIDER_POOL),
        "emergency_contact_name": f"{ec_first} {last_name}",
        "emergency_contact_phone": f"555-{rng.randint(100,999)}-{rng.randint(1000,9999)}",
        "emergency_contact_relation": rng.choice(RELATIONS),
        "blood_type": rng.choice(BLOOD_TYPES),
    }


def seed_mock_emr(db, tenant_id):
    """Seed mock_emr table with clinical data for predefined patients."""
    print("\n4. Seeding mock_emr (clinical data for predefined patients)...")
    
    created_count = 0
    for patient_key, emr_data in MOCK_EMR_DATA.items():
        # Find the patient_context for this patient_key
        context = db.query(PatientContext).filter(
            PatientContext.tenant_id == tenant_id,
            PatientContext.patient_key == patient_key,
        ).first()
        
        if not context:
            print(f"   WARNING: Patient context not found for {patient_key}")
            continue
        
        # Check if mock_emr record already exists
        existing = db.query(MockEmrRecord).filter(
            MockEmrRecord.patient_context_id == context.patient_context_id,
        ).first()
        
        if existing:
            print(f"   - Skipping existing mock_emr for {patient_key}")
            continue
        
        mock_emr = MockEmrRecord(
            patient_context_id=context.patient_context_id,
            allergies=emr_data.get("allergies"),
            medications=emr_data.get("medications"),
            vitals=emr_data.get("vitals"),
            recent_visits=emr_data.get("recent_visits"),
            primary_care_provider=emr_data.get("primary_care_provider"),
            emergency_contact_name=emr_data.get("emergency_contact_name"),
            emergency_contact_phone=emr_data.get("emergency_contact_phone"),
            emergency_contact_relation=emr_data.get("emergency_contact_relation"),
            blood_type=emr_data.get("blood_type"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(mock_emr)
        created_count += 1
        
        # Get display name for logging
        from app.models.patient import PatientSnapshot
        snapshot = db.query(PatientSnapshot).filter(
            PatientSnapshot.patient_context_id == context.patient_context_id
        ).order_by(PatientSnapshot.snapshot_version.desc()).first()
        name = snapshot.display_name if snapshot else patient_key
        
        allergy_count = len(emr_data.get("allergies", []))
        med_count = len(emr_data.get("medications", []))
        print(f"   + {name}: {allergy_count} allergies, {med_count} meds, blood type {emr_data.get('blood_type', 'N/A')}")
    
    db.commit()
    print(f"\n   Created {created_count} mock_emr records")


def seed_mock_emr_for_all_patients(db, tenant_id):
    """Generate mock_emr data for ALL patients that don't have it yet."""
    print("\n5. Generating mock_emr data for remaining patients...")
    
    from app.models.patient import PatientSnapshot
    
    # Get all patient contexts for this tenant
    contexts = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).all()
    
    total = len(contexts)
    created_count = 0
    skipped_count = 0
    
    for i, context in enumerate(contexts):
        # Check if mock_emr record already exists
        existing = db.query(MockEmrRecord).filter(
            MockEmrRecord.patient_context_id == context.patient_context_id,
        ).first()
        
        if existing:
            skipped_count += 1
            continue
        
        # Get display name
        snapshot = db.query(PatientSnapshot).filter(
            PatientSnapshot.patient_context_id == context.patient_context_id
        ).order_by(PatientSnapshot.snapshot_version.desc()).first()
        display_name = snapshot.display_name if snapshot else "Unknown"
        
        # Generate random EMR data
        emr_data = generate_random_emr_data(context.patient_key, display_name)
        
        mock_emr = MockEmrRecord(
            patient_context_id=context.patient_context_id,
            allergies=emr_data.get("allergies"),
            medications=emr_data.get("medications"),
            vitals=emr_data.get("vitals"),
            recent_visits=emr_data.get("recent_visits"),
            primary_care_provider=emr_data.get("primary_care_provider"),
            emergency_contact_name=emr_data.get("emergency_contact_name"),
            emergency_contact_phone=emr_data.get("emergency_contact_phone"),
            emergency_contact_relation=emr_data.get("emergency_contact_relation"),
            blood_type=emr_data.get("blood_type"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(mock_emr)
        created_count += 1
        
        # Progress indicator every 100 patients
        if created_count % 100 == 0:
            print(f"   ... processed {created_count} patients")
            db.commit()  # Commit in batches
    
    db.commit()
    print(f"\n   Generated {created_count} new mock_emr records")
    print(f"   Skipped {skipped_count} patients (already had data)")
    print(f"   Total patients: {total}")


def main():
    print("=" * 60)
    print("Mobius OS - Database Seeding")
    print("=" * 60)
    
    # Initialize agent and get DB session
    agent = PatientDataAgent()
    db = get_db_session()
    
    # Step 1: Ensure default tenant
    print("\n1. Creating default tenant...")
    tenant = agent.ensure_default_tenant()
    print(f"   Tenant ID: {tenant.tenant_id}")
    print(f"   Tenant Name: {tenant.name}")
    
    # Step 1b: Ensure default user (needed for acknowledgements)
    print("\n1b. Creating default user...")
    user = agent.ensure_default_user(tenant.tenant_id)
    print(f"   User ID: {user.user_id}")
    print(f"   User Email: {user.email}")
    
    # Step 2: Seed sample patients (patient_context + patient_snapshot)
    print("\n2. Seeding sample patients...")
    snapshots = agent.seed_sample_patients(tenant.tenant_id)
    
    print(f"\n   Created {len(snapshots)} patients:")
    for snapshot in snapshots:
        status = []
        if snapshot.verified:
            status.append("verified")
        if snapshot.data_complete:
            status.append("complete")
        if snapshot.critical_alert:
            status.append("CRITICAL")
        if snapshot.warnings:
            status.append(f"{len(snapshot.warnings)} warnings")
        
        status_str = ", ".join(status) if status else "pending verification"
        print(f"   - {snapshot.display_name} ({snapshot.id_masked}): {status_str}")
    
    # Step 3: Seed patient_ids (ID translation layer for predefined patients)
    seed_patient_ids(db, tenant.tenant_id)
    
    # Step 3b: Generate patient_ids for ALL remaining patients
    seed_patient_ids_for_all_patients(db, tenant.tenant_id)
    
    # Step 4: Seed mock_emr (clinical data for predefined patients)
    seed_mock_emr(db, tenant.tenant_id)
    
    # Step 5: Generate mock_emr data for ALL remaining patients
    seed_mock_emr_for_all_patients(db, tenant.tenant_id)
    
    print("\n" + "=" * 60)
    print("Seeding complete!")
    print("=" * 60)
    
    # Show how to query
    print("\nTo test patient lookup:")
    print('  curl -X POST http://localhost:5001/api/v1/mini/status \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"session_id": "test", "patient_key": "1234567890"}\'')
    
    print("\nTo view mock EMR page:")
    print("  http://localhost:5001/mock-emr")


if __name__ == "__main__":
    main()
