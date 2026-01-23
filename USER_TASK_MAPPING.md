# User-Task Mapping Analysis

This document shows all users, their configured activities, and how they map to tasks (PlanSteps) in the system.

## Users and Their Activities

### 1. Alex Admin (`admin@demo.clinic`)
- **Role**: `admin`
- **Display Name**: Alex Admin
- **Activities** (ALL activities configured):
  - `verify_eligibility`
  - `check_in_patients`
  - `schedule_appointments`
  - `submit_claims`
  - `rework_denials`
  - `prior_authorization`
  - `patient_collections`
  - `post_payments`
  - `patient_outreach`
  - `document_notes`
  - `coordinate_referrals`
- **Special Status**: Admin users see **ALL tasks** regardless of activities (bypasses activity filtering)
- **Can See Tasks For**: All task types

---

### 2. Sam Scheduler (`scheduler@demo.clinic`)
- **Role**: (Not specified, likely `billing_specialist` or custom)
- **Display Name**: Sam Scheduler
- **Activities**:
  - `schedule_appointments`
  - `check_in_patients`
  - `patient_outreach`
- **Can See Tasks For**:
  - ✅ Attendance-related tasks (`schedule_appointments`, `patient_outreach`)
  - ✅ Check-in tasks (`check_in_patients`)
  - ❌ Eligibility verification tasks (only `verify_eligibility`)
  - ❌ Prior authorization tasks (only `prior_authorization`)
  - ❌ Claims/billing tasks (only `submit_claims`, `rework_denials`, etc.)

---

### 3. Eli Eligibility (`eligibility@demo.clinic`)
- **Role**: (Not specified, likely custom)
- **Display Name**: Eli Eligibility
- **Activities**:
  - `verify_eligibility`
  - `check_in_patients`
- **Can See Tasks For**:
  - ✅ Eligibility verification tasks (`verify_eligibility`)
  - ✅ Check-in tasks (`check_in_patients`)
  - ❌ Prior authorization tasks (only `prior_authorization`)
  - ❌ Scheduling tasks (only `schedule_appointments`, `patient_outreach`)
  - ❌ Claims/billing tasks

---

### 4. Claire Claims (`claims@demo.clinic`)
- **Role**: (Not specified, likely `billing_specialist`)
- **Display Name**: Claire Claims
- **Activities**:
  - `submit_claims`
  - `rework_denials`
  - `post_payments`
  - `patient_collections`
- **Can See Tasks For**:
  - ✅ Claims/billing tasks (`submit_claims`, `rework_denials`, `post_payments`, `patient_collections`)
  - ❌ Eligibility verification tasks (only `verify_eligibility`, `check_in_patients`)
  - ❌ Prior authorization tasks (only `prior_authorization`)
  - ❌ Scheduling tasks (only `schedule_appointments`, `patient_outreach`)

---

### 5. Dr. Casey Clinical (`clinical@demo.clinic`)
- **Role**: (Not specified, likely clinical role)
- **Display Name**: Dr. Casey Clinical
- **Activities**:
  - `prior_authorization`
  - `document_notes`
  - `coordinate_referrals`
- **Can See Tasks For**:
  - ✅ Prior authorization tasks (`prior_authorization`)
  - ✅ Documentation tasks (`document_notes`)
  - ✅ Referral coordination tasks (`coordinate_referrals`)
  - ❌ Eligibility verification tasks
  - ❌ Scheduling tasks
  - ❌ Claims/billing tasks

---

## Task Types and Their Assignable Activities

### Eligibility Tasks (FactorType: ELIGIBILITY)

| Step Code | Question | Assignable Activities |
|-----------|----------|----------------------|
| `insurance_card_uploaded` / `check_insurance_card` | "Insurance card on file?" | `["verify_eligibility", "check_in_patients"]` |
| `has_insurance` | "Does patient have active insurance?" | `["verify_eligibility", "check_in_patients"]` |
| `collect_payer` | "Enter insurance information" | `["verify_eligibility", "check_in_patients"]` |
| `verify_active` / `verify_active_coverage` | "Is coverage currently active?" | `["verify_eligibility"]` |
| `confirm_benefits` | "Are benefits confirmed for this visit type?" | `["verify_eligibility"]` |

**Who Can See These Tasks:**
- ✅ **Alex Admin** (sees all)
- ✅ **Eli Eligibility** (has `verify_eligibility` + `check_in_patients`)
- ✅ **Sam Scheduler** (has `check_in_patients` - can see tasks with both activities)
- ❌ **Claire Claims** (no matching activities)
- ❌ **Dr. Casey Clinical** (no matching activities)

---

### Coverage/Authorization Tasks (FactorType: COVERAGE)

| Step Code | Question | Assignable Activities |
|-----------|----------|----------------------|
| `check_auth_required` | "Is prior authorization required?" | `["prior_authorization"]` |
| `check_documentation` | "Is medical necessity documented?" / "Is clinical documentation sufficient?" | `["prior_authorization"]` or `["prior_authorization", "document_notes"]` |
| `submit_auth` | "Submit prior authorization request" | `["prior_authorization"]` |
| `track_status` | "Authorization decision received?" | `["prior_authorization"]` |

**Who Can See These Tasks:**
- ✅ **Alex Admin** (sees all)
- ✅ **Dr. Casey Clinical** (has `prior_authorization` + `document_notes`)
- ❌ **Eli Eligibility** (no `prior_authorization`)
- ❌ **Sam Scheduler** (no `prior_authorization`)
- ❌ **Claire Claims** (no `prior_authorization`)

---

### Attendance/Scheduling Tasks (FactorType: ATTENDANCE)

| Step Code | Question | Assignable Activities |
|-----------|----------|----------------------|
| `confirm_appointment` | "Has patient confirmed their appointment?" | `["schedule_appointments", "patient_outreach"]` |
| `check_transportation` / `assess_transportation` | "Does patient have transportation?" | `["schedule_appointments", "patient_outreach"]` |
| `check_satisfaction` | "Is patient satisfied with care?" | `["schedule_appointments", "patient_outreach"]` |
| `verify_timing` | "Does the appointment time still work?" | `["schedule_appointments", "patient_outreach"]` |
| `send_reminder` | "Send appointment reminder?" | `["schedule_appointments"]` |

**Who Can See These Tasks:**
- ✅ **Alex Admin** (sees all)
- ✅ **Sam Scheduler** (has `schedule_appointments` + `patient_outreach`)
- ❌ **Eli Eligibility** (no scheduling activities)
- ❌ **Claire Claims** (no scheduling activities)
- ❌ **Dr. Casey Clinical** (no scheduling activities)

---

## Mapping Summary Matrix

| User | Eligibility Tasks | Coverage Tasks | Attendance Tasks | Claims/Billing Tasks |
|------|------------------|----------------|------------------|---------------------|
| **Alex Admin** | ✅ ALL | ✅ ALL | ✅ ALL | ✅ ALL |
| **Eli Eligibility** | ✅ YES | ❌ NO | ❌ NO | ❌ NO |
| **Sam Scheduler** | ⚠️ PARTIAL* | ❌ NO | ✅ YES | ❌ NO |
| **Claire Claims** | ❌ NO | ❌ NO | ❌ NO | ✅ YES** |
| **Dr. Casey Clinical** | ❌ NO | ✅ YES | ❌ NO | ❌ NO |

\* Sam can see eligibility tasks that require `check_in_patients` (e.g., "Insurance card on file?") but NOT tasks that require only `verify_eligibility` (e.g., "Is coverage currently active?").

\*\* Note: Claims/billing tasks are not explicitly defined in the seed data shown, but Claire has activities for `submit_claims`, `rework_denials`, `post_payments`, `patient_collections`.

---

## Potential Issues / Mismatches

### 1. **Sam Scheduler** - Partial Eligibility Access
- **Issue**: Sam has `check_in_patients` but not `verify_eligibility`
- **Impact**: Can see tasks like "Insurance card on file?" (requires both activities) but NOT "Is coverage currently active?" (requires only `verify_eligibility`)
- **Recommendation**: If Sam should see all eligibility tasks, add `verify_eligibility` to their activities

### 2. **Claire Claims** - No Tasks Defined
- **Issue**: Claire has billing/claims activities but no corresponding PlanSteps are defined in the seed data
- **Impact**: Claire may not see any tasks if only eligibility/coverage/attendance tasks exist
- **Recommendation**: Add billing/claims-related PlanSteps with `assignable_activities: ["submit_claims", "rework_denials", "post_payments", "patient_collections"]`

### 3. **Dr. Casey Clinical** - Documentation Tasks
- **Issue**: Some documentation tasks require `["prior_authorization", "document_notes"]` but Dr. Casey has both
- **Status**: ✅ Correctly mapped - Dr. Casey can see these tasks

### 4. **Admin Override**
- **Status**: ✅ Correctly implemented - Admin users bypass activity filtering and see ALL tasks

---

## Activity Code Reference

All activity codes used in the system:
- `verify_eligibility` - Insurance verification
- `check_in_patients` - Patient check-in
- `schedule_appointments` - Appointment scheduling
- `submit_claims` - Claims submission
- `rework_denials` - Denial rework
- `prior_authorization` - Prior authorization
- `patient_collections` - Patient collections
- `post_payments` - Payment posting
- `patient_outreach` - Patient outreach
- `document_notes` - Clinical documentation
- `coordinate_referrals` - Referral coordination

---

## How Task Matching Works

1. **For Admin Users**: 
   - All tasks are shown (bypasses activity filtering)
   - `is_admin = True` → all steps match

2. **For Regular Users**:
   - System checks if `user_activities` (from `UserActivity` table) overlap with `step.assignable_activities`
   - If there's ANY overlap, the step is shown to the user
   - If no overlap, the step is hidden (user sees "Waiting on another team member" if other users have tasks)

3. **Example**:
   - Step: `assignable_activities = ["verify_eligibility", "check_in_patients"]`
   - User: `user_activities = ["check_in_patients", "schedule_appointments"]`
   - Overlap: `["check_in_patients"]` → ✅ User CAN see this task

---

## Recommendations

1. **Add Billing/Claims Tasks**: Create PlanSteps for claims-related work so Claire Claims can see tasks
2. **Review Sam's Activities**: Decide if Sam should have `verify_eligibility` to see all eligibility tasks
3. **Verify Role Assignments**: Ensure all users have appropriate roles assigned in the database
4. **Test Edge Cases**: Test what happens when a user has NO activities configured (should show problem statement, not "waiting")
