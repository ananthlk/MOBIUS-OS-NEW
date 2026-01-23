# Seed Data Structure Guide

This document outlines the database schema, table relationships, and data structure for seed scripts.

## Table Hierarchy & Relationships

```
Tenant (1)
  └── AppUser (N)
       └── UserPreference (1:1)
  
PatientContext (1)
  ├── PatientSnapshot (N) - versioned patient display data
  ├── PaymentProbability (1) - current probability assessment
  ├── ResolutionPlan (1) - active plan to resolve gaps
  │     ├── PlanStep (N) - questions/actions in the plan
  │     │     └── StepAnswer (N) - user answers to steps
  │     ├── PlanNote (N) - team notes
  │     └── PlanModification (N) - audit log
  └── MockEmrRecord (N) - clinical data
```

## Core Tables for Seed Data

### 1. Tenant & Users

**Tenant** (`tenant` table)
- `tenant_id` (UUID, PK)
- `tenant_name` (String)
- `created_at` (DateTime)

**AppUser** (`app_user` table)
- `user_id` (UUID, PK)
- `tenant_id` (UUID, FK → `tenant.tenant_id`)
- `email` (String, unique)
- `display_name` (String)
- `password_hash` (String)
- `role` (String) - "admin", "staff", etc.

**UserPreference** (`user_preference` table)
- `preference_id` (UUID, PK)
- `user_id` (UUID, FK → `app_user.user_id`, unique)
- `tone` (String) - "professional", "friendly", "concise"
- `greeting_enabled` (Boolean)
- `ai_experience_level` (String) - "none", "beginner", "regular"
- `autonomy_routine_tasks` (String) - "automatic", "confirm_first", "manual"
- `autonomy_sensitive_tasks` (String) - "automatic", "confirm_first", "manual"

---

### 2. Patient Context

**PatientContext** (`patient_context` table)
- `patient_context_id` (UUID, PK)
- `tenant_id` (UUID, FK → `tenant.tenant_id`)
- `patient_key` (String) - tokenized identifier, e.g., "demo_001"
- `attention_status` (String, nullable) - "resolved", "confirmed_unresolved", "unable_to_confirm"
- `attention_status_at` (DateTime, nullable)
- `attention_status_by_id` (UUID, FK → `app_user.user_id`, nullable)
- `created_at` (DateTime)
- `last_updated_at` (DateTime)

**PatientSnapshot** (`patient_snapshot` table)
- `patient_snapshot_id` (UUID, PK)
- `patient_context_id` (UUID, FK → `patient_context.patient_context_id`)
- `snapshot_version` (Integer) - increments with each update
- `display_name` (String) - e.g., "John Smith"
- `id_label` (String) - e.g., "MRN"
- `id_masked` (String) - e.g., "****1234"
- `dob` (Date, nullable)
- `verified` (Boolean)
- `data_complete` (Boolean)
- `critical_alert` (Boolean)
- `needs_review` (Boolean)
- `additional_info_available` (Boolean)
- `warnings` (JSONB) - array of warning strings
- `extended_data` (JSONB) - flexible additional data
- `created_at` (DateTime)
- `created_by` (String) - "user" or "system"
- `source` (String) - "ehr_sync", "manual", "api"

---

### 3. Payment Probability

**PaymentProbability** (`payment_probability` table)
- `probability_id` (UUID, PK)
- `patient_context_id` (UUID, FK → `patient_context.patient_context_id`)
- `target_date` (Date) - date for which probability is calculated
- `overall_probability` (Float) - 0.0 to 1.0
- `confidence` (Float) - how confident in the estimate
- `prob_appointment_attendance` (Float, nullable) - will patient show up?
- `prob_eligibility` (Float, nullable) - funding source aligned?
- `prob_coverage` (Float, nullable) - service reimbursable?
- `prob_no_errors` (Float, nullable) - no payor/provider errors?
- `lowest_factor` (String, nullable) - "eligibility", "coverage", "attendance", "errors"
- `lowest_factor_reason` (Text, nullable) - human-readable reason
- `problem_statement` (String, nullable) - e.g., "Verify eligibility - Missing Insurance Card"
- `problem_details` (JSONB, nullable) - array of issue objects
- `computed_at` (DateTime)
- `batch_job_id` (String, nullable)

**Batch Recommendation Fields** (for Workflow Mode UI):
- `agentic_confidence` (Float, nullable) - 0.0-1.0, Mobius confidence
- `recommended_mode` (String, nullable) - "mobius" | "together" | "manual"
- `recommendation_reason` (Text, nullable) - why batch recommends this mode
- `agentic_actions` (JSONB, nullable) - what Mobius would do: `["search_history", "check_medicaid", "send_portal"]`

---

### 4. Resolution Plan

**ResolutionPlan** (`resolution_plan` table)
- `plan_id` (UUID, PK)
- `patient_context_id` (UUID, FK → `patient_context.patient_context_id`)
- `tenant_id` (UUID, FK → `tenant.tenant_id`)
- `gap_types` (JSONB) - array: `["eligibility", "coverage"]`
- `status` (String) - "draft", "active", "resolved", "escalated", "cancelled"
- `current_step_id` (UUID, FK → `plan_step.step_id`, nullable)
- `initial_probability` (Float, nullable)
- `current_probability` (Float, nullable)
- `target_probability` (Float, default=0.85)
- `created_at` (DateTime)
- `updated_at` (DateTime)
- `resolved_at` (DateTime, nullable)
- `resolved_by` (UUID, FK → `app_user.user_id`, nullable)
- `resolution_type` (String, nullable) - "verified", "self_pay", "cancelled", etc.
- `resolution_notes` (Text, nullable)
- `escalated_at` (DateTime, nullable)
- `escalated_to` (UUID, FK → `app_user.user_id`, nullable)
- `escalation_reason` (Text, nullable)
- `batch_job_id` (String, nullable)

**Workflow Mode Fields**:
- `workflow_mode` (String, nullable) - "mobius" | "together" | "manual"
- `workflow_mode_set_at` (DateTime, nullable)
- `workflow_mode_set_by` (UUID, FK → `app_user.user_id`, nullable)

**PlanStep** (`plan_step` table)
- `step_id` (UUID, PK)
- `plan_id` (UUID, FK → `resolution_plan.plan_id`)
- `template_id` (UUID, FK → `task_template.template_id`, nullable)
- `step_order` (Integer) - 1, 2, 3...
- `step_code` (String) - e.g., "has_insurance", "verify_active"
- `step_type` (String) - "question", "form", "confirmation", "action", "branch"
- `input_type` (String) - "single_choice", "multi_choice", "form", "confirmation", "branch_choice"
- `question_text` (String) - e.g., "No insurance information on file - how should we proceed?"
- `description` (Text, nullable)
- `answer_options` (JSONB, nullable) - array of option objects:
  ```json
  [
    {"code": "yes", "label": "Yes", "next_step_code": "collect_payer"},
    {"code": "no", "label": "No", "next_step_code": "self_pay_path"}
  ]
  ```
- `form_fields` (JSONB, nullable) - for form input type
- `can_system_answer` (Boolean) - can Mobius answer this?
- `system_suggestion` (JSONB, nullable) - Mobius suggestion if available
- `assignable_activities` (JSONB, nullable) - array of activity codes
- `assigned_to_user_id` (UUID, FK → `app_user.user_id`, nullable)
- `status` (String) - "pending", "current", "answered", "resolved", "skipped"
- `factor_type` (String, nullable) - "eligibility", "coverage", "attendance", "errors"
- `parent_step_id` (UUID, FK → `plan_step.step_id`, nullable) - for branching
- `is_branch` (Boolean) - is this a branch point?
- `created_at` (DateTime)
- `answered_at` (DateTime, nullable)
- `resolved_at` (DateTime, nullable)
- `completed_at` (DateTime, nullable) - legacy alias for resolved_at

**StepAnswer** (`step_answer` table)
- `answer_id` (UUID, PK)
- `step_id` (UUID, FK → `plan_step.step_id`)
- `answer_code` (String) - e.g., "yes", "no"
- `answer_details` (JSONB, nullable) - for form data
- `answered_by` (UUID, FK → `app_user.user_id`, nullable) - null if system answered
- `answer_mode` (String) - "agentic", "copilot", "user_driven"
- `created_at` (DateTime)

**PlanNote** (`plan_note` table)
- `note_id` (UUID, PK)
- `plan_id` (UUID, FK → `resolution_plan.plan_id`)
- `user_id` (UUID, FK → `app_user.user_id`)
- `note_text` (Text)
- `related_factor` (String, nullable) - "eligibility", "coverage", etc.
- `created_at` (DateTime)

---

## Data Flow & Consistency Rules

### 1. Patient Context Creation
```
1. Create Tenant (if not exists)
2. Create PatientContext with patient_key
3. Create PatientSnapshot (version 1) with display data
```

### 2. Payment Probability Creation
```
1. Must have PatientContext first
2. Create PaymentProbability linked to patient_context_id
3. Set problem_statement (this is what Mini shows)
4. Set batch recommendation fields (agentic_confidence, recommended_mode, etc.)
```

### 3. Resolution Plan Creation
```
1. Must have PatientContext first
2. Create ResolutionPlan with gap_types
3. Create PlanSteps (ordered by step_order)
4. First PlanStep.question_text should match PaymentProbability.problem_statement
5. Set PlanStep.can_system_answer based on whether Mobius can handle
6. Set PlanStep.factor_type for grouping
```

### 4. Consistency Requirements

**Critical Consistency:**
- `PaymentProbability.problem_statement` must match the first `PlanStep.question_text` (or be derived from it)
- `PlanStep.answer_options` must include all options that appear in UI
- `PlanStep.can_system_answer` must be `True` for steps Mobius can handle
- `PlanStep.factor_type` must match the gap type (eligibility, coverage, attendance, errors)

**Workflow Mode Consistency:**
- If `PaymentProbability.recommended_mode = "mobius"`, then at least one `PlanStep` should have `can_system_answer = True`
- `PaymentProbability.agentic_actions` should list actions that Mobius can perform
- `PlanStep` options should align with what Mobius can do

---

## Seed Data Structure Example

```python
SCENARIO = {
    # Patient Info
    "patient_key": "demo_001",
    "patient_name": "John Smith",
    "patient_id_masked": "****1234",
    "dob": date(1980, 1, 15),
    
    # Payment Probability
    "probability": {
        "overall_probability": 0.35,
        "prob_eligibility": 0.20,
        "prob_coverage": 0.70,
        "prob_attendance": 0.85,
        "prob_no_errors": 0.90,
        "lowest_factor": "eligibility",
        "lowest_factor_reason": "No insurance information on file",
        "problem_statement": "Verify eligibility - Missing Insurance Card",  # MUST match first step
        "problem_details": [
            {
                "issue": "eligibility",
                "action": "Verify eligibility",
                "reason": "Missing Insurance Card",
                "severity": "high"
            }
        ],
        # Batch Recommendation
        "agentic_confidence": 0.82,
        "recommended_mode": "mobius",
        "recommendation_reason": "High success rate for insurance lookup, multiple automated options available",
        "agentic_actions": ["search_history", "check_medicaid", "send_portal"]
    },
    
    # Resolution Plan
    "plan": {
        "gap_types": ["eligibility"],
        "status": "active",
        "steps": [
            {
                "step_order": 1,
                "step_code": "no_insurance_triage",
                "question_text": "Verify eligibility - Missing Insurance Card",  # MUST match problem_statement
                "factor_type": "eligibility",
                "can_system_answer": True,  # Mobius can handle this
                "answer_options": [
                    {"code": "patient_has_info", "label": "Patient has insurance - collect info"},
                    {"code": "search_history", "label": "Search patient history for prior coverage"},
                    {"code": "check_medicaid", "label": "Check Medicaid/Medicare eligibility"},
                    {"code": "self_pay", "label": "Patient is self-pay"}
                ],
                "status": "current"
            },
            {
                "step_order": 2,
                "step_code": "contact_for_insurance",
                "question_text": "Contact patient to collect insurance information?",
                "factor_type": "eligibility",
                "can_system_answer": True,  # Mobius can handle this
                "answer_options": [
                    {"code": "send_portal", "label": "Send portal message"},
                    {"code": "send_sms", "label": "Send SMS request"},
                    {"code": "call_patient", "label": "Call patient directly"},
                    {"code": "wait_checkin", "label": "Collect at check-in"}
                ],
                "status": "pending"
            }
        ]
    }
}
```

---

## Factor Types & Gap Types

**Factor Types** (for `PlanStep.factor_type`):
- `"eligibility"` - Insurance eligibility issues
- `"coverage"` - Coverage/benefit issues
- `"attendance"` - Patient attendance/confirmation
- `"errors"` - Billing/documentation errors

**Gap Types** (for `ResolutionPlan.gap_types`):
- Same as factor types: `["eligibility", "coverage", "attendance", "errors"]`

---

## Mobius Capability Flags

**`PlanStep.can_system_answer`**:
- `True` = Mobius can handle this step automatically
- `False` = Requires user action

**`PaymentProbability.recommended_mode`**:
- `"mobius"` = Mobius can handle most/all steps → show "Accept" in Mini
- `"together"` = Mix of Mobius and user tasks → only show "Review" in Mini
- `"manual"` = Mostly user tasks → only show "Review" in Mini

**`PaymentProbability.agentic_actions`**:
- Array of action codes that Mobius will perform
- Only include actions Mobius can actually do
- Examples: `["search_history", "check_medicaid", "send_portal", "run_eligibility_check"]`

---

## Common Seed Data Patterns

### Pattern 1: No Insurance Info (Eligibility)
```python
{
    "problem_statement": "No insurance information on file - how should we proceed?",
    "recommended_mode": "mobius",
    "agentic_actions": ["search_history", "check_medicaid", "send_portal"],
    "steps": [
        {
            "question_text": "No insurance information on file - how should we proceed?",
            "can_system_answer": True,
            "answer_options": [
                {"code": "search_history", "label": "Search patient history"},
                {"code": "check_medicaid", "label": "Check Medicaid eligibility"},
                {"code": "send_portal", "label": "Send portal request"},
                {"code": "self_pay", "label": "Patient is self-pay"}
            ]
        }
    ]
}
```

### Pattern 2: Expired Coverage (Eligibility)
```python
{
    "problem_statement": "Insurance coverage expired - has patient renewed?",
    "recommended_mode": "mobius",
    "agentic_actions": ["run_eligibility_check"],
    "steps": [
        {
            "question_text": "Insurance coverage expired - has patient renewed?",
            "can_system_answer": True,
            "answer_options": [
                {"code": "yes_renewed", "label": "Yes - Patient renewed"},
                {"code": "no_lapsed", "label": "No - Coverage lapsed"},
                {"code": "unknown", "label": "Unknown - Need to verify"}
            ]
        },
        {
            "question_text": "If coverage lapsed, explore alternatives?",
            "can_system_answer": False,  # User must decide
            "answer_options": [
                {"code": "new_employer", "label": "Check new employer coverage"},
                {"code": "marketplace", "label": "Explore marketplace"},
                {"code": "medicaid", "label": "Screen for Medicaid"},
                {"code": "self_pay", "label": "Discuss self-pay"}
            ]
        }
    ]
}
```

### Pattern 3: Unconfirmed Appointment (Attendance)
```python
{
    "problem_statement": "Appointment in 3 days - patient hasn't confirmed yet",
    "recommended_mode": "mobius",
    "agentic_actions": ["send_sms_reminder"],
    "steps": [
        {
            "question_text": "Appointment in 3 days - patient hasn't confirmed yet",
            "can_system_answer": True,
            "answer_options": [
                {"code": "send_reminder", "label": "Send SMS reminder"},
                {"code": "call_patient", "label": "Call patient to confirm"},
                {"code": "flag_at_risk", "label": "No response - flag as at-risk"}
            ]
        }
    ]
}
```

---

## Key Validation Rules

1. **Problem Statement Consistency**: `PaymentProbability.problem_statement` must match first `PlanStep.question_text`
2. **Mobius Actions**: Only include actions in `agentic_actions` that Mobius can actually perform
3. **Answer Options**: All options in `PlanStep.answer_options` must be valid choices
4. **Can System Answer**: If `can_system_answer = True`, the step should appear in "Mobius can handle" section
5. **Workflow Mode**: 
   - If `recommended_mode = "mobius"`, at least one step should have `can_system_answer = True`
   - If `recommended_mode = "together"`, mix of `can_system_answer = True/False`
   - If `recommended_mode = "manual"`, mostly `can_system_answer = False`

---

## Foreign Key Dependencies

**Create in this order:**
1. `Tenant` (if not exists)
2. `AppUser` (requires Tenant)
3. `PatientContext` (requires Tenant)
4. `PatientSnapshot` (requires PatientContext)
5. `PaymentProbability` (requires PatientContext)
6. `ResolutionPlan` (requires PatientContext, Tenant)
7. `PlanStep` (requires ResolutionPlan)
8. `StepAnswer` (requires PlanStep, AppUser)
9. `PlanNote` (requires ResolutionPlan, AppUser)

---

## Notes for Seed Script Writers

1. **Always create PatientContext first** - it's the anchor for all patient data
2. **Create PatientSnapshot** - Mini needs this for display
3. **Create PaymentProbability** - Mini needs this for status display
4. **Create ResolutionPlan** - Sidecar needs this for bottlenecks
5. **Ensure problem_statement matches first step** - critical for data integrity
6. **Set can_system_answer correctly** - affects UI grouping in "Do together" mode
7. **Include all answer options** - Sidecar shows all options, filtered by mode
8. **Set factor_type** - used for grouping in UI
9. **Set workflow_mode fields** - enables Mini recommendation UI
10. **Use consistent patient_key format** - e.g., "demo_001", "demo_002"
