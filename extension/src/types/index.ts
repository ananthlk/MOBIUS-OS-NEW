/**
 * Type definitions for Mobius OS
 */

export type SessionId = string;
export type MessageId = string;
export type UserId = string;

export type Status = 'idle' | 'processing';
export type StatusIndicatorStatus = 'proceed' | 'pending' | 'error' | 'green' | 'yellow' | 'red' | 'blue' | 'grey';
export type TaskType = 'normal' | 'shared' | 'backend';
export type LLMChoice = 'Gemini' | 'GPT-4' | 'Claude';
export type AgentMode = 'Agentic' | 'Co-pilot' | 'Manual';

// UI visibility controls (27 components)
export type UiComponentKey =
  | 'clientLogo'
  | 'mobiusLogo'
  | 'statusIndicator'
  | 'modeBadge'
  | 'alertButton'
  | 'settingsButton'
  | 'contextDisplay'
  | 'contextSummary'
  | 'quickActionButton'
  | 'tasksPanel'
  | 'taskItem'
  | 'thinkingBox'
  | 'systemMessage'
  | 'userMessage'
  | 'feedbackComponent'
  | 'guidanceActions'
  | 'chatInput'
  | 'chatTools'
  | 'recordIdInput'
  | 'workflowButtons'
  | 'userDetails'
  | 'preferencesPanel'
  | 'chatMessage'
  | 'header'
  | 'chatArea'
  | 'collapsiblePanel'
  | 'dropdownMenu';

export type UiVisibilityDefaults = Record<UiComponentKey, boolean>;
export type UiVisibilityOverrides = Partial<UiVisibilityDefaults>;

export interface AgentMessage {
  kind: 'replayed' | 'acknowledgement' | string;
  content: string;
  ui_overrides?: UiVisibilityOverrides;
}

export interface Message {
  id: MessageId;
  content: string;
  timestamp: string;
  sessionId: SessionId;
  type: 'user' | 'system';
  thinkingBox?: ThinkingBoxContent;
  feedbackComponent?: boolean;
  guidanceActions?: GuidanceAction[];
}

export interface SystemMessage extends Message {
  type: 'system';
  thinkingBox?: ThinkingBoxContent;
  feedbackComponent?: boolean;
  guidanceActions?: GuidanceAction[];
}

export interface UserMessage extends Message {
  type: 'user';
}

export interface ThinkingBoxContent {
  content: string[];
  isCollapsed: boolean;
}

export interface GuidanceAction {
  label: string;
  onClick: () => void;
  actionType?: string;
}

export interface Task {
  id: string;
  label: string;
  checked: boolean;
  disabled: boolean;
  type: TaskType;
}

export interface Context {
  context: string;
  status: StatusIndicatorStatus;
  mode: string;
}

export interface ChatResponse {
  success: boolean;
  session_id: SessionId;
  replayed: string;
  acknowledgement: string;
  captured: {
    message: string;
    session_id: SessionId;
    timestamp: string;
    context: Record<string, any>;
  };

  ui_defaults?: UiVisibilityDefaults;
  messages?: AgentMessage[];
}

// =============================================================================
// Patient Context Detection Types
// =============================================================================

/**
 * Types of patient identifiers that can be detected on webpages
 */
export type PatientIdType = 'mrn' | 'insurance' | 'patient_key' | 'lab_id' | 'unknown';

/**
 * Confidence level of a detection
 */
export type DetectionConfidence = 'high' | 'medium' | 'low';

/**
 * Source hint for detected patient identifiers (EMR system)
 */
export type EmrSourceHint = 'epic' | 'cerner' | 'athena' | 'allscripts' | 'netsmart' | 'qualifacts' | 'legacy' | 'url' | 'text' | 'unknown' | 'selected' | 'context' | 'mock_emr';

/**
 * A patient identifier detected from a webpage
 */
export interface DetectedPatient {
  id_type: PatientIdType;
  id_value: string;
  source_hint?: EmrSourceHint;
  confidence: DetectionConfidence;
  detected_at?: string;
}

/**
 * Configuration for a data attribute pattern
 */
export interface DataAttributePattern {
  attr: string;
  type: PatientIdType;
  source: EmrSourceHint;
  /** Optional selector to narrow search scope */
  selector?: string;
}

/**
 * Configuration for a URL pattern
 */
export interface UrlPattern {
  regex: RegExp | string;
  type: PatientIdType;
  /** Capture group index (default: 1) */
  captureGroup?: number;
}

/**
 * Configuration for a DOM text pattern
 */
export interface TextPattern {
  regex: RegExp | string;
  type: PatientIdType;
  /** Capture group index (default: 1) */
  captureGroup?: number;
  /** CSS selector to limit text search scope */
  selector?: string;
}

/**
 * Complete pattern configuration for detection
 */
export interface PatternConfig {
  dataAttributes: DataAttributePattern[];
  urlPatterns: UrlPattern[];
  textPatterns: TextPattern[];
}

/**
 * Options for the PatientContextDetector
 */
export interface PatientContextDetectorOptions {
  /** Debounce time in milliseconds (default: 500) */
  debounceMs?: number;
  /** Detection strategies to use in priority order */
  strategies?: Array<'dataAttributes' | 'url' | 'domText'>;
  /** Custom patterns (merged with defaults) */
  customPatterns?: Partial<PatternConfig>;
  /** Whether to auto-start detection on initialization */
  autoStart?: boolean;
  /** Whether to observe DOM mutations */
  observeMutations?: boolean;
}

/**
 * Event types emitted by PatientContextDetector
 */
export type PatientDetectionEvent = 
  | 'patientDetected'
  | 'patientChanged'
  | 'patientCleared'
  | 'detectionError';

/**
 * Callback for patient detection events
 */
export type PatientDetectionCallback = (patient: DetectedPatient | null, event: PatientDetectionEvent) => void;

/**
 * Response from the backend context detection endpoint
 */
export interface ContextDetectionResponse {
  found: boolean;
  patient_context_id?: string;
  patient_key?: string;
  display_name?: string;
  id_masked?: string;
  /** Tenant-specific pattern overrides (if any) */
  detection_config?: PatternConfig;
}

/**
 * Request payload for context detection
 */
export interface ContextDetectionRequest {
  id_type: PatientIdType;
  id_value: string;
  source_hint?: EmrSourceHint;
  domain?: string;
  tenant_id?: string;
}

/**
 * Resolved patient context (combination of detected + backend lookup)
 */
export interface ResolvedPatientContext {
  found: boolean;
  detected: DetectedPatient;
  patient_context_id?: string;
  patient_key?: string;
  display_name?: string;
  id_masked?: string;
}


// =============================================================================
// User Context Detection Types (User Awareness Sprint)
// =============================================================================

/**
 * Types of user identifiers that can be detected
 */
export type UserIdType = 'user_id' | 'staff_id' | 'email' | 'name' | 'unknown';

/**
 * A user identifier detected from a webpage
 */
export interface DetectedUser {
  id_type: UserIdType;
  id_value: string;
  display_name?: string;
  email?: string;
  source: 'dataAttributes' | 'domSelectors' | 'url';
}

/**
 * Options for the UserContextDetector
 */
export interface UserContextDetectorOptions {
  /** Debounce time in milliseconds (default: 500) */
  debounceMs?: number;
  /** Detection strategies to use in priority order */
  strategies?: Array<'dataAttributes' | 'domSelectors' | 'url'>;
  /** Custom patterns (merged with defaults) */
  customPatterns?: Record<string, unknown>;
  /** Whether to auto-start detection on initialization */
  autoStart?: boolean;
}

/**
 * Event types emitted by UserContextDetector
 */
export type UserDetectionEvent = 
  | 'userDetected'
  | 'userChanged'
  | 'userCleared'
  | 'detectionError';

/**
 * Callback for user detection events
 */
export type UserDetectionCallback = (user: DetectedUser | null, event: UserDetectionEvent) => void;


// =============================================================================
// Authentication Types (User Awareness Sprint)
// =============================================================================

/**
 * Authentication state
 */
export type AuthState = 'unauthenticated' | 'authenticated' | 'onboarding';

/**
 * User profile from backend
 */
export interface UserProfile {
  user_id: string;
  tenant_id: string;
  email?: string;
  display_name?: string;
  first_name?: string;
  preferred_name?: string;
  greeting_name: string;
  avatar_url?: string;
  timezone: string;
  locale: string;
  is_onboarded: boolean;
  activities: string[];
  tone: 'professional' | 'friendly' | 'concise';
  greeting_enabled: boolean;
  autonomy_routine_tasks?: 'automatic' | 'confirm_first' | 'manual';
  autonomy_sensitive_tasks?: 'automatic' | 'confirm_first' | 'manual';
}

/**
 * Authentication tokens
 */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

/**
 * Personalization data from backend
 */
export interface PersonalizationData {
  greeting: string | null;
  tone: string;
  quick_actions: Array<{ code: string; label: string; from_activity?: string }>;
  prioritized_fields: string[];
  default_execution_mode: {
    routine: 'agentic' | 'copilot' | 'user_driven';
    sensitive: 'agentic' | 'copilot' | 'user_driven';
  };
  activities?: Array<{ code: string; label: string }>;
}

/**
 * Mini status response with user awareness fields
 */
/**
 * Resolution plan step for Mini display
 */
export interface ResolutionPlanStep {
  step_id: string;
  step_code: string;
  question_text: string;
  step_type: string;
  input_type: string;
  answer_options?: Array<{
    code: string;
    label: string;
    next_step_code?: string;
    description?: string;
  }>;
  system_suggestion?: {
    answer?: string;
    source?: string;
    payer?: string;
    confidence?: number;
  };
  factor_type?: string;
}

/**
 * Resolution plan for Mini display
 */
export interface ResolutionPlan {
  plan_id: string;
  gap_types: string[];
  status: string;  // 'active' or 'resolved'
  factors: Record<string, {
    done: number;
    total: number;
    status: string;
  }>;
  current_step?: ResolutionPlanStep;
  actions_for_user: number;
  // Resolved plan fields
  resolution_type?: string;
  resolution_notes?: string;
  resolved_at?: string;
}

export interface MiniStatusResponse {
  ok: boolean;
  session_id: string;
  surface: string;
  system_response_id?: string;
  authenticated: boolean;
  user?: {
    user_id: string;
    display_name?: string;
    greeting_name?: string;
    is_onboarded: boolean;
    activities: string[];
  };
  personalization?: PersonalizationData;
  patient?: {
    found: boolean;
    display_name?: string;
    id_masked?: string;
  };
  needs_attention: {
    color: string;
    problem_statement?: string;
    user_status?: string;
  };
  proceed: {
    indicator: string;
    color: string;
    text: string;
  };
  has_tasks: boolean;
  task_count: number;
  tasking?: {
    text: string;
    summary: string;
    needs_ack: boolean;
    color: string;
    mode: string;
    mode_text: string;
  };
  // Resolution Plan: Action-centric UI
  resolution_plan?: ResolutionPlan;
  actions_for_user: number;
  mode?: string;
  computed_at: string;
}
