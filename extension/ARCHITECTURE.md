# Mobius Extension — architecture & schema (Phase 2)

Input for technical review. Pairs with `PHASE2_SPEC.md` (product spec) and
`src/types/sidebar.ts` (the schema of record).

## Module map

The extension is layered: **contract → services → components → orchestrator**.
Dependencies point downward only; components never import each other's internals.

```
 types/sidebar.ts ............ SCHEMA OF RECORD (contract). No imports.
   ▲            ▲
 services/                    components/sidecar/
   envelopes.ts  registry+resolve      SidecarContextStrip   "what I know" strip
   chat.ts       ask/poll + PHI attach DoSaveActions         Do/Save + drawer
   phiScreen.ts  local PHI screen      FloatingRecommendation draggable nudge
   auth.ts       mobius-user + proxy   SidecarSignIn         signed-out state
   api.ts        os-backend calls      QuickChat             chat + consent cards
   toastManager  alerts poll           CollapsibleSection    panel chrome
                                        icons.ts              shared SVG set
        ▲                                      ▲
        └──────────── content.ts (orchestrator) ───────────┘
             boots, resolves envelope, wires callbacks,
             owns initSidecarUI / renderSignedOutSidebar
```

- **Contract** (`types/sidebar.ts`): all shared types + `SIDEBAR_SCHEMA_VERSION`
  + `PERSISTED_KEYS`. Emulates the mobius-chat schema style (documented fields,
  `Literal` unions). Zero imports → no cycles. Candidate to lift into
  `mobius-contracts` so chat and the extension share one definition.
- **Services** (pure logic, no DOM): each owns one concern and is unit-testable.
  `envelopes` (surface×role→actions), `chat` (the ask pipeline + PHI attach),
  `phiScreen` (zero-egress local screen), `auth` (identity via the bg proxy).
- **Components** (pure view): take data + callbacks, return an `HTMLElement`,
  hold no app state, do no I/O. Swappable and independently renderable.
- **Orchestrator** (`content.ts`): the only place services and components meet.
  Owns lifecycle and wiring; every render path is wrapped in `try/catch` so one
  failing zone can't blank the panel.

## Data flow (one render)

```
detect surface (chat.classifyPageSource) + role (envelopes.deriveRole)
        → envelopes.resolveEnvelope() → Envelope
        → DoSaveActions(Envelope): Do = actions[0], Suggested = rest,
                                    Preferred = defaultPreferred(role)|persisted
        → deriveRecommendation(state) → FloatingRecommendation (if a gap)
Do/action → runEnvelopeAction → capturePageText → phiScreen (local, 0 egress)
        → consent card → chat.askMobius (bg proxy → mobius-chat, server PHI gate)
```

## Persistence surfaces  ◆ = flagged for review

`PERSISTED_KEYS` in the schema is the single registry. `scope` decides where a
key SHOULD live:

| Key | Shape | Scope | Notes |
|---|---|---|---|
| `mobius.allowedDomains` | `string[]` | local | per-device is fine |
| `mobius.ui.collapsedSections` | `Record<string,bool>` | local | per-device convenience |
| `mobius.chat.threadId` | `string` | local | rolling extension thread |
| `mobius.recommendationPos` | `{x,y}` | local | floating card position |
| `mobius.theme` / `.density` / `.notificationsEnabled` | prefs | local | per-device |
| **◆ `mobius.preferred`** | `PreferredItem[]` | **user** | the user's pinned actions — SHOULD follow the account across devices → **mobius-user**, not chrome.storage |
| **◆ `mobius.consent.grants`** | `ConsentGrant[]` | **user** | read-permission grants (site/automatic). Compliance-relevant; SHOULD be server-recorded, not only local. PHI attestations MUST be server-logged regardless |
| `mobius.auth.accessToken` | token | session | bg proxy managed |
| `mobius.auth.refreshToken` | token | local | bg proxy managed |

**The two ◆ rows are the key review question:** Preferred pins and consent
grants are *user identity*, not device state. Today they'd sit in
`chrome.storage.local` (per-device). They should migrate to **mobius-user** so
they roam and, for consent, are auditable. Flagged here rather than silently
shipped local.

## Open items for the technical review

1. **`mobius-contracts` lift** — should `types/sidebar.ts` become a shared
   contract package entry so chat/extension share the envelope + surface types?
2. **Preferred + consent persistence** → mobius-user (the ◆ rows above).
3. **`system_context` fix** (separate thread) — move attached page content from
   the chat `message` body into `system_context` to trigger Round 0 and skip the
   robots re-fetch; **blocked on** the chat PHI gate covering that field
   (confirmed today it scans `message` only). Cross-team with chat/PHI seats.
4. **Recommendation sourcing** — 2.2 derives from `care_readiness`; wire to
   explicit backend recommendation objects (missed-visit, benefits) as they land.
5. **Product-awareness** — this schema + spec should be filed with the
   product-awareness agent so it's RAG-ready. (Could not coordinate live this
   session; SendMessage unavailable.)

## Test status

Each increment verified end-to-end in the local harness (sign-in → render →
interaction). Unit tests for the pure services/components are a review follow-up
(`jest` is already configured).
