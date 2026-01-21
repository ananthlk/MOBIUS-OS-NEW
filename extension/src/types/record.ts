/**
 * Sidecar Contract Types
 * 
 * These types define the contract between the batch job (data provider)
 * and the Sidecar UI (data consumer). The batch job populates all state;
 * the Sidecar displays it and captures user decisions.
 */

// =============================================================================
// Record Context (Generic - Patient, Claim, Visit, etc.)
// =============================================================================

/**
 * Type of record being viewed
 */
export type RecordType = 'patient' | 'claim' | 'visit' | 'authorization' | 'order';

/**
 * Generic record context - works for any record type
 */
export interface RecordContext {
  type: RecordType;
  id: string;
  displayName: string;        // "John Smith" or "Claim #12345"
  shortName: string;          // "John" or "12345"
  possessive: string;         // "John's" or "Claim's"
}

/**
 * Privacy context for name display
 */
export interface PrivacyContext {
  isPrivate: boolean;         // Privacy mode enabled
  record: RecordContext;
  staff?: {
    displayName: string;      // "Sarah"
    shortName: string;        // "S."
  };
}

// =============================================================================
// Care Readiness (StatusBar)
// =============================================================================

/**
 * Factor status for care readiness
 */
export type FactorStatusType = 'complete' | 'in_progress' | 'blocked' | 'pending';

/**
 * Individual factor in care readiness
 */
export interface FactorStatus {
  status: FactorStatusType;
  completed_at?: string;      // ISO timestamp
  completed_by?: 'user' | 'mobius' | 'external';
  blocking_reason?: string;   // If blocked
}

/**
 * Care readiness data for StatusBar gradient
 */
export interface CareReadiness {
  position: number;           // 0-100, current position on journey
  start_position?: number;    // 0-100, where we started (for journey visualization)
  direction: 'improving' | 'declining' | 'stable';
  factors: {
    visit_confirmed: FactorStatus;
    eligibility_verified: FactorStatus;
    authorization_secured: FactorStatus;
    documentation_ready: FactorStatus;
  };
}

// =============================================================================
// Bottlenecks / Questions (BottleneckCard)
// =============================================================================

/**
 * Answer option for a question
 */
export interface AnswerOption {
  id: string;                 // 'yes', 'no', 'not_sure'
  label: string;              // 'Yes', 'No', 'Not sure'
  next_step_code?: string;    // For branching logic
  description?: string;       // Optional tooltip
}

/**
 * Data source types for hierarchy resolution
 */
export type SourceType = 'user' | 'page' | 'backend' | 'batch';

/**
 * Source tracking for a bottleneck's data
 */
export interface BottleneckSources {
  batch?: { value: string; updated_at: string };
  page?: { value: string; detected_at: string };
  user?: { value: string; set_at: string };
  backend?: { value: string; fetched_at: string };
}

/**
 * Execution mode for Mobius
 */
export type ExecutionMode = 'agentic' | 'copilot';

/**
 * A bottleneck/question that needs resolution
 * Uses question format for consistency with Mini
 */
export interface Bottleneck {
  id: string;
  milestone_id: string;
  
  // Question (consistent with Mini)
  question_text: string;           // "Is insurance info on file?"
  answer_options: AnswerOption[];  // [{id: 'yes', label: 'Yes'}, ...]
  selected_answer?: string;        // Previously selected answer code (for persistence)
  status?: string;                 // "pending" | "current" | "answered" | "resolved"
  
  // Context
  description?: string;            // Additional context
  blocking_reason?: string;        // What's blocked
  
  // Mobius capability (batch job determines this)
  mobius_can_handle: boolean;      // Can Mobius answer/resolve this?
  mobius_mode?: ExecutionMode;     // If yes, which mode?
  mobius_action?: string;          // "Will check via 270/271"
  estimated_duration?: string;     // "~2 minutes" or "1-3 days"
  
  // Source tracking
  sources: BottleneckSources;
}

/**
 * A resolved step shown in history/More Info
 */
export interface ResolvedStep extends Bottleneck {
  resolved_at?: string;
}

// =============================================================================
// Milestones & Journey (ContextExpander)
// =============================================================================

/**
 * Milestone types
 */
export type MilestoneType = 'visit' | 'eligibility' | 'authorization' | 'documentation';

/**
 * Milestone status
 */
export type MilestoneStatus = 'complete' | 'in_progress' | 'blocked' | 'pending';

/**
 * A substep within a milestone
 */
export interface Substep {
  id: string;
  label: string;                   // "Verify coverage dates"
  status: 'complete' | 'current' | 'pending';
  completed_at?: string;
  completed_by?: 'user' | 'mobius';
}

/**
 * An entry in the journey/history timeline
 */
export interface HistoryEntry {
  timestamp: string;
  actor: 'user' | 'mobius' | 'payer' | 'system';
  actor_name?: string;             // "Sarah" or "Mobius"
  action: string;                  // "Submitted authorization request"
  artifact?: {
    type: 'document' | 'confirmation' | 'reference';
    label: string;                 // "Auth #12345"
    url?: string;
  };
}

/**
 * A milestone in the care journey
 */
export interface Milestone {
  id: string;
  type: MilestoneType;
  
  // Display
  label: string;                   // "John's insurance verified"
  status: MilestoneStatus;
  
  // Substeps (batch computes these)
  substeps: Substep[];
  
  // Journey/history (batch records these)
  history: HistoryEntry[];
}

// =============================================================================
// Knowledge Context (QuickChat)
// =============================================================================

/**
 * Policy excerpt from payer manual
 */
export interface PolicyExcerpt {
  topic: string;                   // "Prior Auth Requirements"
  content: string;                 // Relevant excerpt
  source: string;                  // "Blue Cross Medical Policy 2024"
}

/**
 * Relevant patient history entry
 */
export interface RelevantHistory {
  date: string;
  summary: string;                 // "Previous MRI approved 6mo ago"
}

/**
 * Knowledge context for chat (backend provides this)
 */
export interface KnowledgeContext {
  // Payer info
  payer: {
    name: string;
    phone?: string;
    portal_url?: string;
    avg_response_time?: string;    // "2-3 business days"
  };
  
  // Relevant policy sections (batch extracts these)
  policy_excerpts: PolicyExcerpt[];
  
  // Patient history relevant to this encounter
  relevant_history: RelevantHistory[];
}

// =============================================================================
// Alerts & Toasts (AlertIndicator, UpdateToast)
// =============================================================================

/**
 * Alert types
 */
export type AlertType = 'win' | 'update' | 'reminder' | 'conflict';

/**
 * Alert priority
 */
export type AlertPriority = 'high' | 'normal';

/**
 * An alert for the user (feeds toasts and badge)
 */
export interface Alert {
  id: string;
  type: AlertType;
  priority: AlertPriority;
  created_at: string;
  read: boolean;
  
  // Display
  title: string;                   // "John's auth approved!"
  subtitle?: string;               // "Blue Cross confirmed 2hrs ago"
  
  // Patient context (for cross-patient toasts)
  patient_key?: string;
  patient_name?: string;
  
  // Action (optional)
  action?: {
    label: string;                 // "View details"
    target: 'sidecar' | 'external';
    url?: string;
  };
}

/**
 * Toast display data (derived from Alert)
 */
export interface Toast {
  id: string;
  type: AlertType;
  title: string;
  subtitle?: string;
  patient_key?: string;            // For "click to jump"
  auto_dismiss_ms?: number;        // 5000 for wins, 3000 for updates
  actions?: Array<{
    id: string;
    label: string;
  }>;
}

// =============================================================================
// User Ownership (Task tracking)
// =============================================================================

/**
 * Task ownership status
 */
export type OwnershipStatus = 'active' | 'resolved' | 'reminder_sent';

/**
 * A task the user has taken ownership of
 */
export interface UserOwnedTask {
  id: string;
  bottleneck_id: string;
  question_text: string;           // For display
  patient_key: string;
  patient_name?: string;
  assigned_at: string;
  
  // Batch monitors and updates these
  status: OwnershipStatus;
  resolution_detected?: {
    detected_at: string;
    signal: string;                // "Auth approved in payer portal"
  };
  reminder_sent_at?: string;
}

// =============================================================================
// Full Sidecar State Response (API Contract)
// =============================================================================

/**
 * Complete response from /api/v1/sidecar/state
 * This is the main contract between batch job and Sidecar UI
 */
export interface SidecarStateResponse {
  ok: boolean;
  session_id: string;
  surface: 'sidecar';
  
  // Patient/record context
  record: RecordContext;
  
  // Care readiness (for StatusBar)
  care_readiness: CareReadiness;
  
  // Bottlenecks/questions (for BottleneckCard) - unresolved steps
  bottlenecks: Bottleneck[];       // pending, current, answered (not yet resolved)
  
  // Resolved steps (for More Info history)
  resolved_steps: ResolvedStep[];  // resolved, skipped
  
  // Milestones (for ContextExpander)
  milestones: Milestone[];
  
  // Knowledge context (for QuickChat)
  knowledge_context: KnowledgeContext;
  
  // Alerts (for AlertIndicator badge)
  alerts: Alert[];
  
  // User-owned tasks
  user_owned_tasks: UserOwnedTask[];
  
  // Timestamp
  computed_at: string;
}

/**
 * Response from /api/v1/user/alerts (all patients)
 */
export interface UserAlertsResponse {
  ok: boolean;
  alerts: Alert[];
  unread_count: number;
}

// =============================================================================
// API Request Types
// =============================================================================

/**
 * Request to answer a question
 */
export interface AnswerRequest {
  session_id: string;
  patient_key: string;
  bottleneck_id: string;
  answer_id: string;               // 'yes', 'no', etc.
}

/**
 * Request to add a note
 */
export interface NoteRequest {
  session_id: string;
  patient_key: string;
  bottleneck_id: string;
  note_text: string;
}

/**
 * Request to assign to Mobius
 */
export interface AssignRequest {
  session_id: string;
  patient_key: string;
  bottleneck_id: string;
  mode: ExecutionMode;
}

/**
 * Request to bulk assign to Mobius
 */
export interface BulkAssignRequest {
  session_id: string;
  patient_key: string;
  bottleneck_ids: string[];
}

/**
 * Request to take ownership
 */
export interface OwnRequest {
  session_id: string;
  patient_key: string;
  bottleneck_id: string;
  initial_note?: string;
}
