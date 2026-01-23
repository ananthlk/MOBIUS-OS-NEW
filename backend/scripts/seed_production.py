#!/usr/bin/env python3
"""
Production Database Seed Script for Mobius OS.

Creates essential initial data:
1. Default tenant
2. Admin user
3. Default roles
4. Sample patient data (optional)

Usage:
  # First time setup - creates tenant, admin, and sample data
  python scripts/seed_production.py

  # Only create tenant and admin (no sample data)
  python scripts/seed_production.py --minimal

  # Verify existing data
  python scripts/seed_production.py --verify

Environment:
  Requires DATABASE_MODE=cloud and Cloud SQL credentials.
"""

import sys
import os
import argparse
import uuid
from datetime import datetime, date, timedelta

# Ensure backend is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Suppress SQL logging for clean output
os.environ['FLASK_DEBUG'] = '0'

from app.db.postgres import get_db_session, init_db
from app.models import (
    Tenant, AppUser, Role, Application,
    PatientContext, PatientSnapshot
)
from app.models.probability import PaymentProbability
from app.models.resolution import ResolutionPlan, PlanStatus


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_TENANT = {
    "name": "Mobius Health System",
}

DEFAULT_ROLES = [
    {"name": "admin", "description": "System administrator"},
    {"name": "care_coordinator", "description": "Care coordination team member"},
    {"name": "billing_specialist", "description": "Billing and claims specialist"},
    {"name": "clinician", "description": "Clinical staff member"},
]

DEFAULT_ADMIN = {
    "email": "admin@mobiusos.health",
    "display_name": "System Admin",
    "role": "admin",
}

DEFAULT_APPLICATION = {
    "display_name": "Mobius OS",
}


# =============================================================================
# SEED FUNCTIONS
# =============================================================================

def create_tenant(db) -> Tenant:
    """Create or get default tenant."""
    tenant = db.query(Tenant).filter(
        Tenant.name == DEFAULT_TENANT["name"]
    ).first()
    
    if tenant:
        print(f"  ✓ Tenant exists: {tenant.name} ({tenant.tenant_id})")
        return tenant
    
    tenant = Tenant(
        tenant_id=uuid.uuid4(),
        name=DEFAULT_TENANT["name"],
        created_at=datetime.utcnow(),
    )
    db.add(tenant)
    db.flush()
    print(f"  ✓ Created tenant: {tenant.name} ({tenant.tenant_id})")
    return tenant


def create_roles(db) -> dict:
    """Create or get default roles."""
    roles = {}
    for role_def in DEFAULT_ROLES:
        role = db.query(Role).filter(Role.name == role_def["name"]).first()
        if not role:
            role = Role(
                role_id=uuid.uuid4(),
                name=role_def["name"],
                created_at=datetime.utcnow(),
            )
            db.add(role)
            db.flush()
            print(f"  ✓ Created role: {role.name}")
        else:
            print(f"  ✓ Role exists: {role.name}")
        roles[role_def["name"]] = role
    return roles


def create_admin_user(db, tenant: Tenant, roles: dict) -> AppUser:
    """Create or get admin user."""
    admin = db.query(AppUser).filter(
        AppUser.email == DEFAULT_ADMIN["email"]
    ).first()
    
    if admin:
        print(f"  ✓ Admin exists: {admin.email}")
        return admin
    
    admin_role = roles.get(DEFAULT_ADMIN["role"])
    admin = AppUser(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        role_id=admin_role.role_id if admin_role else None,
        email=DEFAULT_ADMIN["email"],
        display_name=DEFAULT_ADMIN["display_name"],
        status="active",
        created_at=datetime.utcnow(),
    )
    db.add(admin)
    db.flush()
    print(f"  ✓ Created admin: {admin.email}")
    return admin


def create_application(db) -> Application:
    """Create or get default application."""
    app = db.query(Application).filter(
        Application.display_name == DEFAULT_APPLICATION["display_name"]
    ).first()
    
    if app:
        print(f"  ✓ Application exists: {app.display_name}")
        return app
    
    app = Application(
        application_id=uuid.uuid4(),
        display_name=DEFAULT_APPLICATION["display_name"],
        created_at=datetime.utcnow(),
    )
    db.add(app)
    db.flush()
    print(f"  ✓ Created application: {app.display_name}")
    return app


def create_sample_patients(db, tenant: Tenant, count: int = 3):
    """Create sample patients for initial testing."""
    
    sample_patients = [
        {
            "name": "Maria Gonzalez",
            "mrn": "MRN-DEMO001",
            "probability": 0.92,
            "factor": "attendance",
            "problem": "Preparing Maria for her visit",
        },
        {
            "name": "James Walker", 
            "mrn": "MRN-DEMO002",
            "probability": 0.72,
            "factor": "eligibility",
            "problem": "Verifying James's insurance coverage",
        },
        {
            "name": "Tanya Brooks",
            "mrn": "MRN-DEMO003", 
            "probability": 0.45,
            "factor": "attendance",
            "problem": "Re-engaging Tanya for upcoming appointment",
        },
    ]
    
    for i, patient_data in enumerate(sample_patients[:count]):
        # Check if patient exists
        existing = db.query(PatientContext).filter(
            PatientContext.patient_key == f"demo_{patient_data['mrn']}"
        ).first()
        
        if existing:
            print(f"  ✓ Patient exists: {patient_data['name']}")
            continue
        
        # Create patient context
        patient = PatientContext(
            tenant_id=tenant.tenant_id,
            patient_key=f"demo_{patient_data['mrn']}",
            created_at=datetime.utcnow(),
        )
        db.add(patient)
        db.flush()
        
        # Create snapshot
        snapshot = PatientSnapshot(
            patient_context_id=patient.patient_context_id,
            display_name=patient_data["name"],
            id_label="MRN",
            id_masked=f"****{patient_data['mrn'][-4:]}",
            verified=True,
            data_complete=True,
        )
        db.add(snapshot)
        
        # Create probability
        prob = PaymentProbability(
            patient_context_id=patient.patient_context_id,
            target_date=date.today() + timedelta(days=7),
            overall_probability=patient_data["probability"],
            confidence=0.85,
            prob_appointment_attendance=patient_data["probability"] if patient_data["factor"] == "attendance" else 0.90,
            prob_eligibility=patient_data["probability"] if patient_data["factor"] == "eligibility" else 0.88,
            prob_coverage=0.85,
            prob_no_errors=0.90,
            lowest_factor=patient_data["factor"],
            problem_statement=patient_data["problem"],
            batch_job_id="production_seed",
        )
        db.add(prob)
        
        # Create resolution plan
        plan = ResolutionPlan(
            patient_context_id=patient.patient_context_id,
            tenant_id=tenant.tenant_id,
            gap_types=[patient_data["factor"]],
            status=PlanStatus.ACTIVE,
            initial_probability=patient_data["probability"],
            current_probability=patient_data["probability"],
            target_probability=0.90,
        )
        db.add(plan)
        
        print(f"  ✓ Created patient: {patient_data['name']} (prob={patient_data['probability']})")
    
    db.flush()


def verify_data(db):
    """Verify production data integrity."""
    print("\n=== DATA VERIFICATION ===")
    
    tenant_count = db.query(Tenant).count()
    user_count = db.query(AppUser).count()
    role_count = db.query(Role).count()
    patient_count = db.query(PatientContext).count()
    plan_count = db.query(ResolutionPlan).count()
    prob_count = db.query(PaymentProbability).count()
    
    print(f"  Tenants: {tenant_count}")
    print(f"  Users: {user_count}")
    print(f"  Roles: {role_count}")
    print(f"  Patients: {patient_count}")
    print(f"  Resolution Plans: {plan_count}")
    print(f"  Probabilities: {prob_count}")
    
    if tenant_count == 0:
        print("\n  ⚠ No tenant found! Run seed without --verify first.")
        return False
    
    print("\n  ✓ Data verification passed")
    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Seed production database")
    parser.add_argument("--minimal", action="store_true", 
                        help="Only create tenant and admin (no sample data)")
    parser.add_argument("--verify", action="store_true",
                        help="Only verify existing data")
    args = parser.parse_args()
    
    print("=" * 60)
    print("MOBIUS OS - PRODUCTION DATABASE SEED")
    print("=" * 60)
    
    # Show environment
    from app.config import config
    print(f"\nDatabase Mode: {config.DATABASE_MODE}")
    
    if config.DATABASE_MODE != "cloud":
        print("\n⚠ WARNING: DATABASE_MODE is not 'cloud'")
        print("  Set DATABASE_MODE=cloud for production database")
        response = input("  Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    # Initialize database connection
    init_db()
    db = get_db_session()
    
    try:
        if args.verify:
            verify_data(db)
            return
        
        print("\n--- Creating Core Data ---")
        tenant = create_tenant(db)
        roles = create_roles(db)
        admin = create_admin_user(db, tenant, roles)
        app = create_application(db)
        
        if not args.minimal:
            print("\n--- Creating Sample Patients ---")
            create_sample_patients(db, tenant, count=3)
        
        db.commit()
        
        print("\n" + "=" * 60)
        print("✓ PRODUCTION SEED COMPLETE")
        print("=" * 60)
        
        print(f"\nTenant ID: {tenant.tenant_id}")
        print(f"Admin Email: {admin.email}")
        print(f"\nVerify at: /health endpoint")
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
