/**
 * Authorization log client (Phase 2.3 / compliance).
 *
 * Records every PHI authorization the user makes — keyed by a task id — to the
 * mobius-os backend's correlation table (POST /api/v1/authorizations), which
 * owns provenance and forwards the attestation to the PHI agent's compliance
 * log by the same task id. See docs/PHI_AUTHORIZATION_LOG_CONTRACT.md.
 *
 * PHI-safe: sends host + full URL (the backend hashes the URL and keeps only
 * the host) + MASKED identifier labels — never raw text. Best-effort with a
 * short timeout so it never blocks the UI; failures are logged, not thrown.
 */

import { API_V1_URL } from '../config';
import { getAuthService } from './auth';
import { trace } from './traceLog';

export type AuthorizationAction =
  | 'phi_ack_on'
  | 'phi_ack_off'
  | 'read_ack'
  | 'read_auto'
  | 'override_send'
  | 'site_grant';

export interface AuthorizationRecord {
  taskId: string;
  action: AuthorizationAction;
  phiPresent?: boolean;
  /** MASKED identifier labels, e.g. ["MRN","Date of Birth"] — never raw. */
  phiLabels?: string[];
  /** Downstream chat correlation id, when this authorization drove a send. */
  chatCorrelationId?: string;
}

export async function recordAuthorization(rec: AuthorizationRecord): Promise<void> {
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    try {
      const token = await getAuthService().getAccessToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    } catch {
      // anonymous is allowed; the backend flags unattributed records
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    trace('authz', `record ${rec.action} → POST /authorizations`, rec.taskId);
    try {
      const resp = await fetch(`${API_V1_URL}/authorizations`, {
        method: 'POST',
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          task_id: rec.taskId,
          action: rec.action,
          surface: 'extension',
          origin_host: location.hostname,
          origin_url: location.href,
          phi_present: !!rec.phiPresent,
          phi_labels: rec.phiLabels || null,
          chat_correlation_id: rec.chatCorrelationId || null,
        }),
      });
      const body = await resp.json().catch(() => null);
      if (resp.ok && body?.ok) {
        trace(
          'net',
          `authorization stored ✓ ${resp.status}${body.attributed ? ' · attributed' : ' · anon'}${
            body.hipaa_log_forwarded ? ' · hipaa-log' : ''
          }`,
          rec.taskId
        );
      } else {
        trace('error', `authorization store FAILED · HTTP ${resp.status}`, rec.taskId);
      }
    } finally {
      clearTimeout(timeout);
    }
  } catch (err) {
    trace('error', `authorization store error: ${err instanceof Error ? err.message : String(err)}`, rec.taskId);
    console.error('[Mobius] recordAuthorization failed (non-fatal):', err);
  }
}
