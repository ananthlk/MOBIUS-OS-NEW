#!/usr/bin/env python3
"""
Large dataset seeding script.

Creates 200 patients with various statuses for testing decision agents.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/seed_large_dataset.py
"""

import sys
import random
import logging
from pathlib import Path
from datetime import date, timedelta

# Suppress SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.agents.patient_data_agent import PatientDataAgent

# Sample data pools
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Dorothy", "Kevin", "Carol", "Brian", "Amanda", "George", "Melissa",
    "Timothy", "Deborah", "Ronald", "Stephanie", "Edward", "Rebecca", "Jason", "Sharon",
    "Jeffrey", "Laura", "Ryan", "Cynthia", "Jacob", "Kathleen", "Gary", "Amy",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Anna", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Emma", "Scott", "Nicole", "Brandon", "Helen",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
]

WARNING_TYPES = [
    "Insurance verification pending",
    "Allergies need update",
    "Medication reconciliation required",
    "Prior authorization pending",
    "Referral needed",
    "Lab results pending review",
    "Imaging results pending",
    "Follow-up appointment overdue",
    "Immunizations not current",
    "Contact information needs update",
    "Emergency contact missing",
    "Advance directive not on file",
    "Insurance about to expire",
    "Prescription renewal needed",
    "Specialist consult pending",
]

CRITICAL_ALERTS = [
    "Drug interaction alert - review medications",
    "Abnormal lab values - immediate attention",
    "Critical vital signs - urgent review",
    "Allergy alert - potential allergen prescribed",
    "Fall risk - high priority",
    "Sepsis screening positive",
    "Stroke symptoms reported",
    "Cardiac event suspected",
    "Severe adverse reaction reported",
    "Mental health crisis alert",
]


def generate_patient_key() -> str:
    """Generate a random 10-digit patient key."""
    return "".join([str(random.randint(0, 9)) for _ in range(10)])


def generate_dob() -> date:
    """Generate a random date of birth (18-95 years old)."""
    today = date.today()
    age_days = random.randint(18 * 365, 95 * 365)
    return today - timedelta(days=age_days)


def create_patient_profile(index: int) -> dict:
    """
    Create a patient profile with realistic distribution:
    - 40% verified + complete (GREEN)
    - 20% verified + warnings (YELLOW)
    - 15% unverified (GREY)
    - 10% has additional info (BLUE)
    - 10% critical alerts (RED)
    - 5% needs review
    """
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    patient_key = generate_patient_key()
    
    # Base profile
    profile = {
        "patient_key": patient_key,
        "display_name": f"{first_name} {last_name}",
        "id_label": random.choice(["MRN", "Patient ID", "Medical Record"]),
        "dob": generate_dob(),
        "verified": False,
        "data_complete": False,
        "critical_alert": False,
        "needs_review": False,
        "additional_info_available": False,
        "warnings": None,
    }
    
    # Determine status category based on distribution
    roll = random.random()
    
    if roll < 0.40:
        # GREEN: Verified + Complete (40%)
        profile["verified"] = True
        profile["data_complete"] = True
        
    elif roll < 0.60:
        # YELLOW: Verified + Warnings (20%)
        profile["verified"] = True
        profile["data_complete"] = random.choice([True, False])
        num_warnings = random.randint(1, 3)
        profile["warnings"] = random.sample(WARNING_TYPES, num_warnings)
        
    elif roll < 0.75:
        # GREY: Unverified (15%)
        profile["verified"] = False
        profile["data_complete"] = random.choice([True, False])
        
    elif roll < 0.85:
        # BLUE: Additional info available (10%)
        profile["verified"] = True
        profile["data_complete"] = True
        profile["additional_info_available"] = True
        
    elif roll < 0.95:
        # RED: Critical alerts (10%)
        profile["verified"] = random.choice([True, False])
        profile["data_complete"] = random.choice([True, False])
        profile["critical_alert"] = True
        profile["warnings"] = [random.choice(CRITICAL_ALERTS)]
        
    else:
        # Needs review (5%)
        profile["verified"] = True
        profile["data_complete"] = False
        profile["needs_review"] = True
        num_warnings = random.randint(0, 2)
        if num_warnings > 0:
            profile["warnings"] = random.sample(WARNING_TYPES, num_warnings)
    
    return profile


def main():
    print("=" * 70)
    print("Mobius OS - Large Dataset Seeding (200 patients)")
    print("=" * 70)
    
    # Initialize agent
    agent = PatientDataAgent()
    
    # Step 1: Ensure default tenant
    print("\n1. Ensuring default tenant exists...")
    tenant = agent.ensure_default_tenant()
    print(f"   Tenant ID: {tenant.tenant_id}")
    
    # Step 2: Generate and insert 200 patients
    print("\n2. Generating 200 patient records...")
    
    # Track statistics
    stats = {
        "green": 0,   # verified + complete
        "yellow": 0,  # has warnings
        "grey": 0,    # unverified
        "blue": 0,    # additional info
        "red": 0,     # critical
    }
    
    created_count = 0
    
    for i in range(200):
        profile = create_patient_profile(i)
        
        try:
            snapshot = agent.create_or_update_patient(
                tenant_id=tenant.tenant_id,
                source="seed_large",
                created_by="seed_large_dataset.py",
                **profile,
            )
            created_count += 1
            
            # Track stats
            if profile["critical_alert"]:
                stats["red"] += 1
            elif profile["additional_info_available"]:
                stats["blue"] += 1
            elif profile["warnings"]:
                stats["yellow"] += 1
            elif not profile["verified"]:
                stats["grey"] += 1
            else:
                stats["green"] += 1
            
            # Progress indicator
            if (i + 1) % 20 == 0:
                print(f"   Progress: {i + 1}/200 patients created...")
                
        except Exception as e:
            print(f"   Error creating patient {i + 1}: {e}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("Seeding Complete!")
    print("=" * 70)
    print(f"\nTotal patients created: {created_count}")
    print(f"\nDistribution by expected proceed indicator:")
    print(f"   GREEN  (verified + complete):    {stats['green']:3d} ({stats['green']/2:.1f}%)")
    print(f"   YELLOW (has warnings):           {stats['yellow']:3d} ({stats['yellow']/2:.1f}%)")
    print(f"   GREY   (unverified):             {stats['grey']:3d} ({stats['grey']/2:.1f}%)")
    print(f"   BLUE   (additional info):        {stats['blue']:3d} ({stats['blue']/2:.1f}%)")
    print(f"   RED    (critical alert):         {stats['red']:3d} ({stats['red']/2:.1f}%)")
    
    # Sample query
    print("\n" + "-" * 70)
    print("Sample patients:")
    print("-" * 70)
    
    # Show a few sample patients
    import uuid
    sample_contexts = agent.db.query(agent.db.query.__self__.query.__self__.__class__.__mro__[0]).from_statement(
        agent.db.execute.__self__.execute.__func__.__self__.execute(
            "SELECT * FROM patient_context WHERE tenant_id = :tid ORDER BY created_at DESC LIMIT 5",
            {"tid": tenant.tenant_id}
        )
    )
    
    # Simpler approach - just query directly
    from app.models.patient import PatientContext
    samples = agent.db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant.tenant_id
    ).order_by(PatientContext.created_at.desc()).limit(5).all()
    
    for ctx in samples:
        snapshot = agent.get_latest_snapshot(ctx.patient_context_id)
        if snapshot:
            status = "GREEN" if snapshot.verified and snapshot.data_complete else \
                     "RED" if snapshot.critical_alert else \
                     "YELLOW" if snapshot.warnings else \
                     "BLUE" if snapshot.additional_info_available else "GREY"
            print(f"   {snapshot.display_name:<25} ({snapshot.id_masked}) - {status}")
    
    print("\n" + "=" * 70)
    print("To test, run:")
    print('  curl -X POST http://localhost:5001/api/v1/mini/patient/search?q=Smith')
    print("=" * 70)


if __name__ == "__main__":
    main()
