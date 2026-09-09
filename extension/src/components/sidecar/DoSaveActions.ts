/**
 * DoSaveActions — the Phase 2 action core.
 *
 * Two verbs (Do = the promoted #1 Suggested action; Save = contribute) over
 * a three-tier drawer: Suggested (this page, from the envelope) · Preferred
 * (the user's pins, stable everywhere) · Anything (the chat, rendered
 * separately). Propose-not-morph: everything here is a proposal, nothing
 * auto-runs.
 */

import type { Envelope, EnvelopeAction } from '../../services/envelopes';
import type { PreferredItem } from '../../types/sidebar';
export type { PreferredItem };

export interface DoSaveOpts {
  /** Run the promoted action (Do). */
  onDo: (action: EnvelopeAction) => void;
  /** Contribute (Save) — resolves scope by offer, not a form. */
  onSave: () => void;
  /** Run any drawer action. */
  onAction: (action: EnvelopeAction) => void;
  /** Focus the chat (when there's no promoted action). */
  onAsk: () => void;
  preferred: PreferredItem[];
  onPreferred: (item: PreferredItem) => void;
  onCustomize: () => void;
}

export function DoSaveActions(envelope: Envelope, opts: DoSaveOpts): HTMLElement {
  const root = document.createElement('div');
  root.className = 'sidecar-dosave';

  const actionable = envelope.actions.filter((a) => a.kind !== 'preview');
  const promoted = actionable[0];
  const suggested = envelope.actions.filter((a) => a.id !== promoted?.id);

  // --- verbs ---
  const verbs = document.createElement('div');
  verbs.className = 'ds-verbs';

  const doBtn = document.createElement('button');
  doBtn.type = 'button';
  doBtn.className = 'ds-verb do';
  doBtn.innerHTML = `<span class="ds-vt">↘ Do</span><span class="ds-vs">${
    promoted ? escapeHtml(promoted.label) : 'Ask Mobius'
  }</span>`;
  doBtn.addEventListener('click', () => (promoted ? opts.onDo(promoted) : opts.onAsk()));
  verbs.appendChild(doBtn);

  const saveBtn = document.createElement('button');
  saveBtn.type = 'button';
  saveBtn.className = 'ds-verb save';
  saveBtn.innerHTML = `<span class="ds-vt">↗ Save</span><span class="ds-vs">Keep &amp; file</span>`;
  saveBtn.addEventListener('click', () => opts.onSave());
  verbs.appendChild(saveBtn);

  root.appendChild(verbs);

  // --- drawer ---
  const drawer = document.createElement('div');
  drawer.className = 'ds-drawer';

  if (suggested.length) {
    drawer.appendChild(groupHead('Suggested · this page'));
    const row = document.createElement('div');
    row.className = 'ds-row';
    for (const a of suggested) {
      const chip = mkChip(a.label);
      chip.addEventListener('click', () => opts.onAction(a));
      row.appendChild(chip);
    }
    drawer.appendChild(row);
  }

  const prefHead = groupHead('Preferred · yours');
  const customize = document.createElement('span');
  customize.className = 'ds-customize';
  customize.textContent = '✎ customize';
  customize.addEventListener('click', () => opts.onCustomize());
  prefHead.appendChild(customize);
  drawer.appendChild(prefHead);

  const prow = document.createElement('div');
  prow.className = 'ds-row';
  for (const p of opts.preferred) {
    const chip = mkChip(p.label, true);
    chip.addEventListener('click', () => opts.onPreferred(p));
    prow.appendChild(chip);
  }
  const pin = mkChip('+ pin');
  pin.classList.add('pin');
  pin.addEventListener('click', () => opts.onCustomize());
  prow.appendChild(pin);
  drawer.appendChild(prow);

  root.appendChild(drawer);
  return root;
}

function groupHead(label: string): HTMLElement {
  const h = document.createElement('div');
  h.className = 'ds-grp';
  const s = document.createElement('span');
  s.className = 'ds-grp-lbl';
  s.textContent = label;
  h.appendChild(s);
  return h;
}

function mkChip(label: string, preferred = false): HTMLElement {
  const c = document.createElement('button');
  c.type = 'button';
  c.className = 'ds-chip' + (preferred ? ' pref' : '');
  c.textContent = label;
  return c;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] || c));
}
