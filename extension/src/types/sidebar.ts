/**
 * Sidebar contract (Phase 2) — the schema of record for the Mobius
 * extension's side panel.
 *
 * Mirrors the mobius-chat schema convention (documented fields, `Literal`
 * unions, an explicit version) so it reads like `app/planner/schemas.py`
 * and can lift into the shared `mobius_contracts` package alongside the
 * chat / envelope contracts. Every module below imports its types from
 * here rather than redefining them — one contract, many consumers.
 *
 * Persistence: types marked "◆ persisted" are stored across sessions; see
 * `PERSISTED_KEYS` and PHASE2_SPEC.md § persistence.
 */

export const SIDEBAR_SCHEMA_VERSION = '2.0.0';

// ── Surface & role (derived, never asked) ──────────────────────────────────

/** Detected page surface. Hostname-derived; see `chat.classifyPageSource`. */
export type SurfaceType = 'email' | 'emr' | 'rcm' | 'web';

/** Coarse user role from mobius-user activities. Light input — tunes the
 *  promoted action and seeds Preferred, never gates capability. */
export type Role = 'front_desk' | 'biller' | 'clinician' | 'unknown';

// ── Actions & envelopes (the "drawer" catalog) ─────────────────────────────

/** What an action does when invoked. `preview` = recognized, not yet built. */
export type ActionKind =
  | 'ask'
  | 'synthesize'
  | 'compose_reply'
  | 'find_email'
  | 'collate'
  | 'preview';

/** ICONS keys (components/sidecar/icons.ts) an action may render with. */
export type IconKey = 'mobius' | 'page' | 'bulb' | 'person' | 'warning' | 'clock' | 'together';

/** One catalog action. Do = the promoted action[0]; the rest are Suggested. */
export interface EnvelopeAction {
  /** Stable id, unique within an envelope. */
  id: string;
  /** User-facing label. */
  label: string;
  /** Optional one-line sublabel. */
  sublabel?: string;
  /** Icon glyph key. */
  icon: IconKey;
  /** Behavior class. */
  kind: ActionKind;
  /** Preset chat prompt for synthesize/compose_reply flows. */
  prompt?: string;
  /** Marks the surface's headline action (promoted into Do). */
  primary?: boolean;
}

/** The resolved shape for a surface × role. Data, not a code path. */
export interface Envelope {
  id: SurfaceType;
  /** Chip text behind the "detected" marker. */
  chipLabel: string;
  /** A `var(--mobius-*)` accent token. */
  accentVar: string;
  /** The "On this page you can…" lead line. */
  propose: string;
  /** Ordered actions; [0] is promoted into Do. */
  actions: EnvelopeAction[];
}

/** ◆ persisted — a user's pinned drawer action (Preferred tier). */
export interface PreferredItem {
  id: string;
  label: string;
  /** Where it came from — role seed vs an explicit user pin. */
  source?: 'seed' | 'pinned';
}

// ── Context strip ("what I know") ──────────────────────────────────────────

/** The derived, static context shown for glance-confirmation. */
export interface ContextInfo {
  surface: SurfaceType;
  /** Surface glyph (✉ / ▤ / ◱ / 🌐). */
  glyph: string;
  /** Identity: email sender · web title · patient name (+masked MRN). */
  title: string;
  /** Prettified role, omitted when unknown. */
  role?: string;
  /** True when a patient/MRN is detected on the surface. */
  patientDetected?: boolean;
}

// ── Recommendation banner (proactive, one at a time) ───────────────────────

export type RecommendationTemper = 'opportunity' | 'correction';

/** A proactive nudge sourced from backend intelligence — including the
 *  care-readiness signal, surfaced AS a recommendation rather than its own
 *  bar (payment probability, care-readiness factors, missed-visit patterns,
 *  benefit eligibility all feed this). Rendered as a banner with a permanent
 *  place in the panel body (below the context strip). One at a time; more
 *  queue. */
export interface Recommendation {
  id: string;
  temper: RecommendationTemper;
  /** Short imperative message (may contain <b> emphasis, sanitized). */
  message: string;
  /** Primary action label, e.g. "Refer", "Verify now". */
  actionLabel: string;
  /** Opaque token echoed back on accept/dismiss for the learning loop. */
  correlationId?: string;
}


// ── Tasks (pull, quiet) ────────────────────────────────────────────────────

export type TaskScope = 'user' | 'patient';

/** A to-do surfaced in the tasks badge/list. */
export interface TaskItem {
  id: string;
  scope: TaskScope;
  label: string;
  /** Patient key when scope === 'patient'. */
  patientKey?: string;
}

// ── Consent (per-read permission that decays) ──────────────────────────────

/** How the current read was authorized. */
export type ConsentScope = 'once' | 'site' | 'automatic';

/** ◆ persisted (site/automatic only) — a stored read-permission grant.
 *  `once` grants are never persisted. PHI reads always log an attestation. */
export interface ConsentGrant {
  host: string;
  scope: Exclude<ConsentScope, 'once'>;
  /** ISO timestamp the grant was recorded. */
  grantedAt: string;
  /** True if PHI was present when granted (attestation recorded server-side). */
  phiAttested: boolean;
}

// ── Persisted state (the durable surfaces) ─────────────────────────────────

/** ◆ persisted — everything the sidebar remembers across sessions. Each
 *  field maps to a key in `PERSISTED_KEYS`. Stored in chrome.storage.local
 *  today; the ◆ user-scoped fields SHOULD migrate to mobius-user so they
 *  follow the account across devices (see PHASE2_SPEC § persistence). */
export interface PersistedSidebarState {
  schemaVersion: string;
  /** Sites the extension is enabled on. */
  allowedDomains: string[];
  /** The user's pinned Preferred actions. */
  preferred: PreferredItem[];
  /** Per-panel collapse state. */
  collapsedSections: Record<string, boolean>;
  /** Rolling chat thread id for the extension surface. */
  chatThreadId?: string;
  /** Stored read-permission grants (site/automatic). */
  consentGrants: ConsentGrant[];
  /** UI prefs. */
  theme?: string;
  density?: string;
  notificationsEnabled?: boolean;
}

/**
 * Canonical chrome.storage keys. Central list so no module invents a key.
 * `scope: local` = per-device; `scope: user` = SHOULD live in mobius-user.
 */
export const PERSISTED_KEYS = {
  allowedDomains: { key: 'mobius.allowedDomains', scope: 'local' },
  preferred: { key: 'mobius.preferred', scope: 'user' },
  collapsedSections: { key: 'mobius.ui.collapsedSections', scope: 'local' },
  chatThreadId: { key: 'mobius.chat.threadId', scope: 'local' },
  consentGrants: { key: 'mobius.consent.grants', scope: 'user' },
  theme: { key: 'mobius.theme', scope: 'local' },
  density: { key: 'mobius.density', scope: 'local' },
  notifications: { key: 'mobius.notificationsEnabled', scope: 'local' },
  // Auth tokens (managed by services/auth via the background proxy).
  accessToken: { key: 'mobius.auth.accessToken', scope: 'session' },
  refreshToken: { key: 'mobius.auth.refreshToken', scope: 'local' },
} as const;
