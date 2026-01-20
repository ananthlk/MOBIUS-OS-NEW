/**
 * API service for backend communication.
 *
 * Separate paths for Mini vs Sidecar (PRD surface separation),
 * both referencing the same underlying patient state.
 */

import { 
  SessionId, 
  ChatResponse, 
  DetectedPatient, 
  ContextDetectionRequest, 
  ContextDetectionResponse,
  ResolvedPatientContext,
  PatternConfig,
  MiniStatusResponse as MiniStatusResponseType,
  UserProfile,
} from '../types';
import { getAuthService } from './auth';

const API_BASE_URL = 'http://localhost:5001/api/v1';

// =============================================================================
// Authenticated Fetch Helper
// =============================================================================

/**
 * Make an authenticated API request.
 * Automatically adds Authorization header if user is logged in.
 */
async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const authService = getAuthService();
  const token = await authService.getAccessToken();
  
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  return fetch(url, {
    ...options,
    headers,
  });
}

// =============================================================================
// Chat Mode (existing)
// =============================================================================

/**
 * Send a chat message to the backend.
 */
export async function sendChatMessage(
  message: string,
  sessionId: SessionId
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/modes/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to send message');
  }

  return response.json();
}

// =============================================================================
// Mini Surface (/api/v1/mini/*)
// =============================================================================

type MiniStatusColor = 'green' | 'yellow' | 'grey' | 'blue' | 'red';

export type ExecutionMode = 'agentic' | 'copilot' | 'user_driven';

export type AttentionStatus = 'resolved' | 'confirmed_unresolved' | 'unable_to_confirm' | null;

export type MiniStatusResponse = {
  ok: true;
  session_id: SessionId;
  surface: 'mini';
  patient?: {
    found: boolean;
    display_name?: string;
    id_masked?: string;
  };
  // New "Needs Attention" format
  needs_attention?: {
    color: MiniStatusColor;
    problem_statement: string | null;
    user_status: AttentionStatus;
  };
  // Legacy proceed (kept for backwards compatibility)
  proceed: { color: MiniStatusColor; text: string };
  // Legacy tasking (kept for backwards compatibility, now hidden in UI)
  tasking?: { 
    color: MiniStatusColor; 
    text: string;
    mode?: ExecutionMode;
    mode_text?: string;
  };
  // Task info for badge
  has_tasks?: boolean;
  task_count?: number;
  // Mode (for sidecar)
  mode?: ExecutionMode;
};

export async function fetchMiniStatus(
  sessionId: SessionId,
  patientKey?: string
): Promise<MiniStatusResponse> {
  // Use authenticated fetch to include user context
  const response = await authenticatedFetch(`${API_BASE_URL}/mini/status`, {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, patient_key: patientKey }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to fetch mini status');
  }

  return response.json();
}

export type MiniAckResponse = {
  ok: true;
  session_id: SessionId;
  surface: 'mini';
  submission: {
    note: string;
    override_proceed?: string;
    override_tasking?: string;
    attention_status?: AttentionStatus;
    submitted_at?: string;
  };
  open_sidecar?: boolean;  // Signal to open sidecar
};

/**
 * Submit acknowledgement from Mini (Send action).
 */
export async function submitMiniAck(
  sessionId: SessionId,
  note: string,
  options?: {
    patientKey?: string;
    overrideProceed?: string;
    overrideTasking?: string;
    attentionStatus?: AttentionStatus;
  }
): Promise<MiniAckResponse> {
  const response = await fetch(`${API_BASE_URL}/mini/ack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      note,
      patient_key: options?.patientKey,
      override_proceed: options?.overrideProceed,
      override_tasking: options?.overrideTasking,
      attention_status: options?.attentionStatus,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to submit acknowledgement');
  }

  return response.json();
}

/**
 * Submit attention status change from Mini (workflow action).
 * This is a valid acknowledgement even without a note.
 */
export async function submitAttentionStatus(
  sessionId: SessionId,
  patientKey: string,
  attentionStatus: AttentionStatus
): Promise<MiniAckResponse> {
  const response = await fetch(`${API_BASE_URL}/mini/ack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      patient_key: patientKey,
      attention_status: attentionStatus,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to update attention status');
  }

  return response.json();
}

/**
 * Report a new issue from Mini widget.
 * Creates a UserReportedIssue for batch job processing.
 */
export async function reportIssue(
  sessionId: SessionId,
  patientKey: string,
  issueText: string
): Promise<{ ok: true; issue_id: string }> {
  const response = await fetch(`${API_BASE_URL}/mini/issue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      patient_key: patientKey,
      issue_text: issueText,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to report issue');
  }

  return response.json();
}

/**
 * Submit a note from Mini (legacy, use submitMiniAck instead).
 * @deprecated Use submitMiniAck
 */
export async function submitMiniNote(
  sessionId: SessionId,
  note: string,
  patient?: { name?: string; id?: string }
): Promise<{ ok: true; session_id: SessionId; note: string }> {
  const response = await fetch(`${API_BASE_URL}/mini/note`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, note, patient: patient || {} }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to submit note');
  }

  return response.json();
}

export type MiniPatientSearchResult = { name: string; id: string };

export async function searchMiniPatients(
  query: string,
  limit = 8
): Promise<{ ok: true; q: string; results: MiniPatientSearchResult[] }> {
  const q = (query || '').trim();
  const url = new URL(`${API_BASE_URL}/mini/patient/search`);
  url.searchParams.set('q', q);
  url.searchParams.set('limit', String(limit));

  const response = await fetch(url.toString(), { method: 'GET' });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to search patients');
  }
  return response.json();
}

// =============================================================================
// Sidecar Surface (/api/v1/sidecar/*)
// =============================================================================

export type SidecarPatientState = {
  found: boolean;
  patient_key?: string;
  snapshot?: {
    display_name?: string;
    id_label?: string;
    id_masked?: string;
  };
  system_response?: {
    proceed_indicator: MiniStatusColor;
    execution_mode?: string;
    tasking_summary?: string;
    computed_at?: string;
  };
};

export type SidecarStateResponse = {
  ok: true;
  session_id: SessionId;
  surface: 'sidecar';
  patient_state: SidecarPatientState;
  history: Array<{
    event_type: string;
    created_at: string;
    payload?: Record<string, unknown>;
  }>;
  inbox_preview: {
    open_count: number;
    assignments: Array<{
      assignment_id: string;
      patient_key: string;
      reason_code?: string;
    }>;
  };
};

/**
 * Get full patient state for Sidecar.
 */
export async function fetchSidecarState(
  sessionId: SessionId,
  patientKey?: string
): Promise<SidecarStateResponse> {
  const response = await fetch(`${API_BASE_URL}/sidecar/state`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, patient_key: patientKey }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to fetch sidecar state');
  }

  return response.json();
}

export type SidecarAckResponse = {
  ok: true;
  session_id: SessionId;
  surface: 'sidecar';
  submission: {
    note: string;
    override_proceed?: string;
    override_tasking?: string;
    submitted_at?: string;
  };
};

/**
 * Submit acknowledgement from Sidecar (Send action).
 */
export async function submitSidecarAck(
  sessionId: SessionId,
  note: string,
  options?: {
    patientKey?: string;
    overrideProceed?: string;
    overrideTasking?: string;
  }
): Promise<SidecarAckResponse> {
  const response = await fetch(`${API_BASE_URL}/sidecar/ack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      note,
      patient_key: options?.patientKey,
      override_proceed: options?.overrideProceed,
      override_tasking: options?.overrideTasking,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to submit acknowledgement');
  }

  return response.json();
}

export type SidecarHistoryResponse = {
  ok: true;
  session_id: SessionId;
  patient_key?: string;
  events: Array<{
    event_type: string;
    created_at: string;
    payload?: Record<string, unknown>;
  }>;
  has_more: boolean;
};

/**
 * Get event history for Sidecar.
 */
export async function fetchSidecarHistory(
  sessionId: SessionId,
  patientKey?: string,
  limit = 50
): Promise<SidecarHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/sidecar/history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, patient_key: patientKey, limit }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to fetch history');
  }

  return response.json();
}

export type SidecarInboxResponse = {
  ok: true;
  session_id: SessionId;
  assignments: Array<{
    assignment_id: string;
    patient_key: string;
    reason_code?: string;
    created_at: string;
    status: string;
  }>;
};

/**
 * Get user inbox (open assignments) for Sidecar.
 */
export async function fetchSidecarInbox(
  sessionId: SessionId,
  userId?: string
): Promise<SidecarInboxResponse> {
  const response = await fetch(`${API_BASE_URL}/sidecar/inbox`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, user_id: userId }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to fetch inbox');
  }

  return response.json();
}

// =============================================================================
// Context Detection (/api/v1/context/*)
// =============================================================================

/**
 * Resolve a detected patient identifier to internal Mobius context.
 * 
 * This is called by the PatientContextDetector when it detects a potential
 * patient identifier on the current webpage.
 * 
 * @param detected - The detected patient identifier from the webpage
 * @param tenantId - Optional tenant ID
 * @returns Resolved patient context with internal IDs and display info
 */
export async function resolvePatientContext(
  detected: DetectedPatient,
  tenantId?: string
): Promise<ResolvedPatientContext> {
  const domain = window.location.hostname;
  
  const requestBody: ContextDetectionRequest = {
    id_type: detected.id_type,
    id_value: detected.id_value,
    source_hint: detected.source_hint,
    domain,
    tenant_id: tenantId,
  };

  try {
    const response = await fetch(`${API_BASE_URL}/context/detect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to resolve patient context');
    }

    const data: ContextDetectionResponse = await response.json();

    return {
      found: data.found,
      detected,
      patient_context_id: data.patient_context_id,
      patient_key: data.patient_key,
      display_name: data.display_name,
      id_masked: data.id_masked,
    };
  } catch (error) {
    console.error('[API] Error resolving patient context:', error);
    return {
      found: false,
      detected,
    };
  }
}

/**
 * Get tenant-specific detection configuration for a domain.
 * 
 * This allows tenants to customize detection patterns for their specific
 * EMR systems or custom implementations.
 * 
 * @param domain - The domain to get configuration for
 * @param tenantId - Optional tenant ID
 * @returns Pattern configuration or null if no custom config exists
 */
export async function fetchDetectionConfig(
  domain: string,
  tenantId?: string
): Promise<PatternConfig | null> {
  const url = new URL(`${API_BASE_URL}/context/config`);
  url.searchParams.set('domain', domain);
  if (tenantId) {
    url.searchParams.set('tenant_id', tenantId);
  }

  try {
    const response = await fetch(url.toString(), { method: 'GET' });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to fetch detection config');
    }

    const data = await response.json();
    return data.has_config ? data.patterns : null;
  } catch (error) {
    console.error('[API] Error fetching detection config:', error);
    return null;
  }
}

/**
 * Simple patient lookup by ID type and value.
 * 
 * @param idType - Type of identifier (mrn, insurance, patient_key, etc.)
 * @param idValue - The identifier value
 * @param tenantId - Optional tenant ID
 * @returns Context detection response
 */
export async function lookupPatientById(
  idType: string,
  idValue: string,
  tenantId?: string
): Promise<ContextDetectionResponse> {
  const url = new URL(`${API_BASE_URL}/context/lookup`);
  url.searchParams.set('id_type', idType);
  url.searchParams.set('id_value', idValue);
  if (tenantId) {
    url.searchParams.set('tenant_id', tenantId);
  }

  const response = await fetch(url.toString(), { method: 'GET' });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to lookup patient');
  }

  return response.json();
}
