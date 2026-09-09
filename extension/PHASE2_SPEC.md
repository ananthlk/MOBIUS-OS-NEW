# Phase 2 — Sidebar spec (LOCKED 2026-09-09)

The extension is two modes (icon ↔ side panel, shipped in Phase 1). Phase 2
rebuilds the **side panel body** around a Do/Save core. Design reference:
the "Complete Sidebar" artifact. This file is the source of truth for the build.

## Zones, top to bottom

1. **Header** — client badge · Mobius wordmark · **PHI status pill** · **⋯ menu** · close (‹).
   - The PHI pill is a *status*, not a control: green when no PHI in context,
     amber when PHI is detected or scope is patient. Consent happens per-read
     (see Consent), not as a mode you pre-set.
2. **Context strip ("what I know")** — derived, static: surface glyph · identity
   (email sender / web title / patient+MRN) · role · `wrong?` (corrects the
   *detection*) · **tasks badge** (quiet, pull) on the right.
3. **Recommendation banner** — proactive, prominent, ONE at a time. Two tempers:
   `opportunity` (violet) and `correction` (amber). Sourced from backend
   intelligence the platform already computes (payment probability, care-readiness
   factors, missed-visit patterns, benefit eligibility). Dismiss/act is logged.
4. **Do / Save** — the two verbs.
   - **Do** = the #1 *Suggested* action, promoted. Runs instantly when the result
     is a draft/answer the user still controls; shows a one-line confirm when it
     acts on an external system (keyed to reversibility).
   - **Save** = contribute. Resolves the one un-derivable field (where it lands)
     by *offering a recommendation* (e.g. "AHCA policy → Org library?"), never a
     blank picker. Low confidence → default to "Just for me", promote later.
5. **Drawer** — three tiers of decreasing certainty:
   - **Suggested · this page** — context-derived, shifts per surface (from the
     envelope engine). Do is this list's #1.
   - **Preferred · yours** — user-pinned 2–3, stable everywhere. Customizable
     (pin / customize). Seeded by role for new users; the learning loop proposes
     pins from usage. Dedupe against Suggested (Preferred wins).
   - **Anything** — the chat line ("Ask Mobius anything…").
6. **Chat (Anything)** — freeform, pinned to the bottom, constant across surfaces.

## ⋯ menu (carried-forward settings)

- **Engine**: Model (LLM profile) · Mode (Auto/Fast/Deep → think-mode).
- **Appearance & alerts**: Notifications · Theme · Text size (density) · View.
- **Utilities**: Activity & trace · History · General settings · Help.
- **Disable on this site** (destructive, set apart).

## Consent (per-read permission that decays)

One consent object, weight tied to BAA maturity:
1. **Ask every time** — modal on each read (today). When PHI is present, the
   modal *is* the HIPAA attestation (logged). Uses the local PHI screen
   (`phiScreen.ts`, zero egress) to preview, then the authoritative server gate.
2. **Remember per site/org** — "Always on this site" stores the grant.
3. **Automatic** — where the BAA covers the surface, no prompt (still logged).

## Learning loop (invisible)

Every Do/Save/decline/dismiss is logged. Manifests only as: righter promoted Do,
better Preferred-pin suggestions, better recommendation targeting. Never a report
in the panel.

## Build order (each increment tested before the next)

- **2.1 Body layout** — context strip + Do/Save + Suggested/Preferred drawer +
  chat, replacing the panel stack. Reuse the envelope engine for Suggested/Do.
- **2.2 Recommendation banner + tasks badge** — surface backend recommendations.
- **2.3 Consent modal + PHI status pill** — per-read permission.
- **2.4 ⋯ menu consolidation** — settings into one menu.
- **2.5 Mini-code deletion** — remove the ~965-line dead mini render path
  (deferred from Phase 1).
