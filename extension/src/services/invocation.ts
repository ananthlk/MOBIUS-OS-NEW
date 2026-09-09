/**
 * Invocation ids (Phase 2.3 / compliance).
 *
 * Every user-initiated invocation that could touch PHI (a page read, a PHI
 * acknowledgement, an override send) gets a task id — the correlation key
 * that ties the authorization to where it originated. The extension records
 * the authorization under this id (services/authorizationLog); the PHI
 * agent's compliance log stores the attestation under the SAME id, so the
 * two join. Prefix marks the surface of origin.
 */

export function newTaskId(): string {
  const rand =
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return `ext_${rand}`;
}
