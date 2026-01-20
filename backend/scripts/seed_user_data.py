#!/usr/bin/env python3
"""
Seed script for User Awareness Sprint.

Creates demo users with different activities and preferences
to test personalization features.

Run with: python scripts/seed_user_data.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from datetime import datetime

from app.db.postgres import get_db_session, init_db
from app.models.tenant import Tenant, AppUser, Role, AuthProviderLink
from app.models.activity import Activity, UserActivity
from app.models.probability import UserPreference
from app.services.auth_service import AuthService


# Default tenant ID
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def seed_tenant():
    """Ensure default tenant exists."""
    with get_db_session() as session:
        tenant = session.query(Tenant).filter(
            Tenant.tenant_id == DEFAULT_TENANT_ID
        ).first()
        
        if not tenant:
            tenant = Tenant(
                tenant_id=DEFAULT_TENANT_ID,
                name="Demo Healthcare Clinic"
            )
            session.add(tenant)
            session.commit()
            print(f"[seed] Created tenant: {tenant.name}")
        else:
            print(f"[seed] Tenant exists: {tenant.name}")
        
        return tenant


def seed_activities():
    """Create activities for user onboarding."""
    activities_data = [
        {"activity_code": "verify_eligibility", "label": "Verify Insurance Eligibility", "description": "Check patient insurance coverage and benefits", "display_order": 1},
        {"activity_code": "check_in_patients", "label": "Check In Patients", "description": "Patient check-in and registration", "display_order": 2},
        {"activity_code": "schedule_appointments", "label": "Schedule Appointments", "description": "Schedule and manage patient appointments", "display_order": 3},
        {"activity_code": "submit_claims", "label": "Submit Claims", "description": "Submit insurance claims for reimbursement", "display_order": 4},
        {"activity_code": "rework_denials", "label": "Rework Denied Claims", "description": "Appeal and rework denied insurance claims", "display_order": 5},
        {"activity_code": "prior_authorization", "label": "Prior Authorizations", "description": "Submit and track prior authorization requests", "display_order": 6},
        {"activity_code": "patient_collections", "label": "Patient Collections", "description": "Manage patient balances and collections", "display_order": 7},
        {"activity_code": "post_payments", "label": "Post Payments", "description": "Post insurance and patient payments", "display_order": 8},
        {"activity_code": "patient_outreach", "label": "Patient Outreach", "description": "Call and contact patients for follow-ups", "display_order": 9},
        {"activity_code": "document_notes", "label": "Document Clinical Notes", "description": "Create and manage clinical documentation", "display_order": 10},
        {"activity_code": "coordinate_referrals", "label": "Coordinate Referrals", "description": "Manage patient referrals to specialists", "display_order": 11},
    ]
    
    with get_db_session() as session:
        for act_data in activities_data:
            existing = session.query(Activity).filter(
                Activity.activity_code == act_data["activity_code"]
            ).first()
            
            if not existing:
                activity = Activity(
                    activity_code=act_data["activity_code"],
                    label=act_data["label"],
                    description=act_data["description"],
                    display_order=act_data["display_order"],
                    is_active=True,
                )
                session.add(activity)
                print(f"[seed] Created activity: {act_data['label']}")
            else:
                print(f"[seed] Activity exists: {act_data['label']}")
        
        session.commit()


def seed_roles():
    """Create demo roles."""
    roles_data = [
        {"name": "admin", "description": "System administrator"},
        {"name": "billing_specialist", "description": "Billing and claims"},
        {"name": "front_desk", "description": "Front desk / reception"},
        {"name": "care_coordinator", "description": "Care coordination"},
        {"name": "nurse", "description": "Clinical nursing staff"},
    ]
    
    with get_db_session() as session:
        for role_data in roles_data:
            existing = session.query(Role).filter(
                Role.name == role_data["name"]
            ).first()
            
            if not existing:
                role = Role(name=role_data["name"])
                session.add(role)
                print(f"[seed] Created role: {role_data['name']}")
        
        session.commit()


def seed_demo_users():
    """Create demo users with different activity profiles."""
    auth_service = AuthService()
    
    # Demo users with their activities
    users_data = [
        {
            "email": "sarah.chen@demo.clinic",
            "password": "demo1234",
            "display_name": "Sarah Chen",
            "first_name": "Sarah",
            "preferred_name": "Sarah",
            "timezone": "America/New_York",
            "activities": ["verify_eligibility", "submit_claims", "rework_denials"],
            "preferences": {
                "tone": "professional",
                "greeting_enabled": True,
                "ai_experience_level": "regular",
                "autonomy_routine_tasks": "automatic",
                "autonomy_sensitive_tasks": "confirm_first",
            }
        },
        {
            "email": "mike.johnson@demo.clinic",
            "password": "demo1234",
            "display_name": "Mike Johnson",
            "first_name": "Michael",
            "preferred_name": "Mike",
            "timezone": "America/Chicago",
            "activities": ["schedule_appointments", "check_in_patients", "patient_outreach"],
            "preferences": {
                "tone": "friendly",
                "greeting_enabled": True,
                "ai_experience_level": "beginner",
                "autonomy_routine_tasks": "confirm_first",
                "autonomy_sensitive_tasks": "manual",
            }
        },
        {
            "email": "dr.patel@demo.clinic",
            "password": "demo1234",
            "display_name": "Dr. Priya Patel",
            "first_name": "Priya",
            "preferred_name": "Dr. Patel",
            "timezone": "America/Los_Angeles",
            "activities": ["document_notes", "coordinate_referrals", "prior_authorization"],
            "preferences": {
                "tone": "concise",
                "greeting_enabled": False,
                "ai_experience_level": "regular",
                "autonomy_routine_tasks": "automatic",
                "autonomy_sensitive_tasks": "automatic",
            }
        },
        {
            "email": "lisa.wong@demo.clinic",
            "password": "demo1234",
            "display_name": "Lisa Wong",
            "first_name": "Lisa",
            "preferred_name": "Lisa",
            "timezone": "America/New_York",
            "activities": ["prior_authorization", "verify_eligibility"],
            "preferences": {
                "tone": "professional",
                "greeting_enabled": True,
                "ai_experience_level": "none",
                "autonomy_routine_tasks": "manual",
                "autonomy_sensitive_tasks": "manual",
            }
        },
    ]
    
    with get_db_session() as session:
        for user_data in users_data:
            # Check if user exists
            existing = session.query(AppUser).filter(
                AppUser.email == user_data["email"],
                AppUser.tenant_id == DEFAULT_TENANT_ID
            ).first()
            
            if existing:
                print(f"[seed] User exists: {user_data['email']}")
                user = existing
            else:
                # Create user
                user = AppUser(
                    tenant_id=DEFAULT_TENANT_ID,
                    email=user_data["email"],
                    password_hash=auth_service.hash_password(user_data["password"]),
                    display_name=user_data["display_name"],
                    first_name=user_data["first_name"],
                    preferred_name=user_data["preferred_name"],
                    timezone=user_data["timezone"],
                    locale="en-US",
                    status="active",
                    onboarding_completed_at=datetime.utcnow(),  # Pre-onboarded
                )
                session.add(user)
                session.flush()
                
                # Create auth provider link for email
                auth_link = AuthProviderLink(
                    user_id=user.user_id,
                    provider="email",
                    email=user_data["email"],
                )
                session.add(auth_link)
                
                print(f"[seed] Created user: {user_data['email']}")
            
            # Create or update preferences
            preference = session.query(UserPreference).filter(
                UserPreference.user_id == user.user_id
            ).first()
            
            if not preference:
                preference = UserPreference(user_id=user.user_id)
                session.add(preference)
            
            prefs = user_data["preferences"]
            preference.tone = prefs["tone"]
            preference.greeting_enabled = prefs["greeting_enabled"]
            preference.ai_experience_level = prefs["ai_experience_level"]
            preference.autonomy_routine_tasks = prefs["autonomy_routine_tasks"]
            preference.autonomy_sensitive_tasks = prefs["autonomy_sensitive_tasks"]
            
            # Clear existing activities and add new ones
            session.query(UserActivity).filter(
                UserActivity.user_id == user.user_id
            ).delete()
            
            for i, activity_code in enumerate(user_data["activities"]):
                activity = session.query(Activity).filter(
                    Activity.activity_code == activity_code
                ).first()
                
                if activity:
                    user_activity = UserActivity(
                        user_id=user.user_id,
                        activity_id=activity.activity_id,
                        is_primary=(i == 0),
                    )
                    session.add(user_activity)
                else:
                    print(f"[seed] Warning: Activity not found: {activity_code}")
        
        session.commit()
        print("[seed] Demo users seeded successfully")


def print_demo_credentials():
    """Print demo user credentials for testing."""
    print("\n" + "="*60)
    print("DEMO USER CREDENTIALS")
    print("="*60)
    print("""
User 1: Billing Specialist (experienced with AI)
  Email: sarah.chen@demo.clinic
  Password: demo1234
  Activities: eligibility, claims, denials
  AI Preference: Automatic for routine, confirm for sensitive

User 2: Front Desk (new to AI)
  Email: mike.johnson@demo.clinic
  Password: demo1234
  Activities: scheduling, check-in, outreach
  AI Preference: Confirm for routine, manual for sensitive

User 3: Provider (AI expert, concise)
  Email: dr.patel@demo.clinic
  Password: demo1234
  Activities: documentation, referrals, prior auth
  AI Preference: Automatic for all, greetings disabled

User 4: Prior Auth Specialist (no AI experience)
  Email: lisa.wong@demo.clinic
  Password: demo1234
  Activities: prior auth, eligibility
  AI Preference: Manual for all
""")
    print("="*60 + "\n")


def main():
    """Run seed script."""
    print("[seed] Starting user data seed...")
    
    # Ensure database is initialized
    init_db()
    
    # Seed data
    seed_tenant()
    seed_activities()  # Must be before users since users reference activities
    seed_roles()
    seed_demo_users()
    
    # Print credentials
    print_demo_credentials()
    
    print("[seed] Done!")


if __name__ == "__main__":
    main()
