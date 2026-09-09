/**
 * Consent service (Phase 2.3) — the per-read permission that decays.
 *
 * Stage 1 (today): ask every read (the ack card). Stage 2: "Always on this
 * site" stores a ConsentGrant so non-PHI reads skip the modal. Stage 3
 * (automatic, BAA-covered) is server-driven and not implemented client-side.
 *
 * PHI is never covered by a silent grant: a read whose content the local
 * screen flags as PHI always shows the acknowledgement (the attestation),
 * even on a granted site. Grants persist in chrome.storage.local today;
 * per the schema they SHOULD migrate to mobius-user (auditable). See
 * PHASE2_SPEC § persistence.
 */

import type { ConsentGrant } from '../types/sidebar';

const KEY = 'mobius.consent.grants';

function readGrants(): Promise<ConsentGrant[]> {
  return new Promise((resolve) => {
    try {
      chrome.storage.local.get([KEY], (items) => {
        const list = items?.[KEY];
        resolve(Array.isArray(list) ? (list as ConsentGrant[]) : []);
      });
    } catch {
      resolve([]);
    }
  });
}

/** The stored grant for a host, or null. */
export async function getConsentGrant(host: string): Promise<ConsentGrant | null> {
  const h = (host || '').toLowerCase();
  const grants = await readGrants();
  return grants.find((g) => g.host === h) || null;
}

/** Record a "site" grant for a host (idempotent — replaces any prior one). */
export async function saveConsentGrant(host: string, phiAttested: boolean): Promise<void> {
  const h = (host || '').toLowerCase();
  if (!h) return;
  const grants = (await readGrants()).filter((g) => g.host !== h);
  grants.push({ host: h, scope: 'site', grantedAt: new Date().toISOString(), phiAttested });
  return new Promise((resolve) => {
    try {
      chrome.storage.local.set({ [KEY]: grants }, () => resolve());
    } catch {
      resolve();
    }
  });
}

/** Remove a host's grant (used by "disable on this site" / revoke). */
export async function revokeConsentGrant(host: string): Promise<void> {
  const h = (host || '').toLowerCase();
  const grants = (await readGrants()).filter((g) => g.host !== h);
  return new Promise((resolve) => {
    try {
      chrome.storage.local.set({ [KEY]: grants }, () => resolve());
    } catch {
      resolve();
    }
  });
}
