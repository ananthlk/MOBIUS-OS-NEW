/**
 * Envelope registry — the mode-aware "shape" the sidecar takes per surface.
 *
 * An envelope is a DATA definition (not a code path): a detected surface +
 * the signed-in role resolve to one envelope, whose `actions` fill the
 * sidecar's action zone. The constant chrome (identity, ask bar, consent
 * gesture) never changes — only this action set does, and it is always
 * PROPOSED (shown behind a "detected" chip), never silently executed.
 *
 * This registry is deliberately client-side for the first slice. It has the
 * same shape a server-served manifest would (see fetchDetectionConfig), so
 * it lifts to a backend endpoint later with no consumer change.
 *
 * Actions marked `kind: 'preview'` are shape-only placeholders — the surface
 * is recognized but the flow isn't built yet. Everything else is wired to a
 * real flow in content.ts (ask / synthesize / compose_reply run through the
 * existing read-page → PHI-screen → chat pipeline).
 */

// Contract lives in the schema of record (types/sidebar.ts); this module
// is the registry + resolution logic over those types.
import type { SurfaceType, Role, ActionKind, EnvelopeAction, Envelope } from '../types/sidebar';

export type { SurfaceType, Role, ActionKind, EnvelopeAction, Envelope };
/** @deprecated alias — use SurfaceType. */
export type Surface = SurfaceType;

const WEB: Envelope = {
  id: 'web',
  chipLabel: 'Web page',
  accentVar: 'var(--mobius-text-muted, #64748b)',
  propose: 'On this page you can…',
  actions: [
    {
      // The dominant web action: fetch the doc the user is looking at (in their
      // authenticated session, reaching robots/auth-blocked content) and file
      // it for retrieval — without it ever landing on their device.
      id: 'web-ingest',
      label: 'Add this document to Mobius',
      sublabel: 'Fetched in your browser, filed for retrieval — never saved to your device',
      icon: 'page',
      kind: 'ingest',
      primary: true,
    },
    {
      id: 'web-synthesize',
      label: 'Summarize this page',
      sublabel: 'Key points + how it applies',
      icon: 'bulb',
      kind: 'synthesize',
      prompt:
        'Summarize the attached page: the key points and how they apply to a Florida behavioral-health RCM workflow.',
    },
  ],
};

const EMAIL: Envelope = {
  id: 'email',
  chipLabel: 'Email detected',
  accentVar: 'var(--mobius-indigo, #5b5ef4)',
  propose: 'On this thread you can…',
  actions: [
    {
      id: 'email-reply',
      label: 'Compose a reply',
      sublabel: 'Drafts from the thread + your corpus',
      icon: 'mobius',
      kind: 'compose_reply',
      prompt:
        'Draft a professional reply to the email thread on the attached page. Match the sender’s tone, address every open question, and keep it concise.',
      primary: true,
    },
    {
      id: 'email-summarize',
      label: 'Summarize this thread',
      sublabel: 'Who needs what, by when',
      icon: 'bulb',
      kind: 'synthesize',
      prompt:
        'Summarize the email thread on the attached page: what is being asked, who owns each item, and any deadlines.',
    },
    {
      id: 'email-find',
      label: 'Find an email',
      sublabel: 'Search this mailbox (preview)',
      icon: 'page',
      kind: 'find_email',
    },
  ],
};

// RCM / clearinghouse — recognized, flows not built yet. Shape-only.
const RCM: Envelope = {
  id: 'rcm',
  chipLabel: 'Clearinghouse',
  accentVar: 'var(--mobius-info, #0891b2)',
  propose: 'Claim workflow (preview) —',
  actions: [
    {
      id: 'rcm-explain',
      label: 'Explain this denial',
      sublabel: 'CARC/RARC → next action (preview)',
      icon: 'bulb',
      kind: 'preview',
    },
    {
      id: 'rcm-status',
      label: 'Check claim status',
      sublabel: 'Preview',
      icon: 'clock',
      kind: 'preview',
    },
  ],
};

// EMR is handled by the existing patient scaffold (readiness/plan/etc.),
// so its registry entry is intentionally action-light: the scaffold IS the
// envelope. Kept here so resolveEnvelope always returns a definition.
const EMR: Envelope = {
  id: 'emr',
  chipLabel: 'EMR',
  accentVar: 'var(--mobius-warning, #f59e0b)',
  propose: 'Patient workspace',
  actions: [],
};

const REGISTRY: Record<Surface, Envelope> = { web: WEB, email: EMAIL, rcm: RCM, emr: EMR };

/**
 * Resolve the envelope for a surface + role. Role currently tunes ordering
 * only (light input, per design) — every action stays available regardless.
 */
export function resolveEnvelope(surface: Surface, role: Role): Envelope {
  const base = REGISTRY[surface] || WEB;
  // Light role nudge: a biller on an email leads with summarize (triage)
  // rather than compose. Never removes actions — only reorders the lead.
  if (surface === 'email' && role === 'biller') {
    const actions = [...base.actions].sort((a, b) =>
      a.kind === 'synthesize' ? -1 : b.kind === 'synthesize' ? 1 : 0
    );
    return { ...base, actions };
  }
  return base;
}

/** Coarse role from the mobius-user activity set. Light by design. */
export function deriveRole(activities: string[] | undefined): Role {
  const a = new Set(activities || []);
  if (a.has('submit_claims') || a.has('rework_denials') || a.has('post_payments')) return 'biller';
  if (a.has('document_notes') || a.has('coordinate_referrals')) return 'clinician';
  if (a.has('check_in_patients') || a.has('schedule_appointments') || a.has('verify_eligibility'))
    return 'front_desk';
  return 'unknown';
}

/**
 * Default "Preferred" pins for a role, used to seed a new user's drawer so
 * the surface arrives useful before they customize. Persisted per-user once
 * they edit (see PHASE2_SPEC persistence surfaces).
 */
export function defaultPreferred(role: Role): { id: string; label: string }[] {
  switch (role) {
    case 'biller':
      return [
        { id: 'check-claim', label: 'Check a claim' },
        { id: 'retrieve-patient', label: 'Look up a patient' },
      ];
    case 'clinician':
      return [
        { id: 'summarize-chart', label: 'Summarize chart' },
        { id: 'new-note', label: 'New note' },
      ];
    case 'front_desk':
      return [
        { id: 'verify-eligibility', label: 'Verify eligibility' },
        { id: 'retrieve-patient', label: 'Look up a patient' },
      ];
    default:
      return [
        { id: 'search-policy', label: 'Search policy' },
        { id: 'retrieve-patient', label: 'Look up a patient' },
      ];
  }
}
