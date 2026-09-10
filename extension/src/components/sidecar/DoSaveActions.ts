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
  /** Save — resolves scope by offer over the envelope's `save`-group actions,
   *  not a form. Corpus is live (fetch-to-RAG); bookmark scopes are proposed. */
  onSave: (saveActions: EnvelopeAction[]) => void;
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

  // DO = act-in-place; SAVE = persist. Actions default to `do` when untagged.
  const isSave = (a: EnvelopeAction) => a.group === 'save';
  const doActions = envelope.actions.filter((a) => !isSave(a) && a.kind !== 'preview');
  const saveActions = envelope.actions.filter(isSave);
  const promoted = doActions[0];
  // Suggested drawer = the rest of the DO actions (Save has its own verb).
  const suggested = envelope.actions.filter((a) => !isSave(a) && a.id !== promoted?.id);

  // --- verbs ---
  const verbs = document.createElement('div');
  verbs.className = 'ds-verbs';

  // Do — the ACTION is the primary label (not the word "Do"); a small
  // "Suggested" eyebrow marks it as the promoted guess. No decorative arrow.
  const doBtn = document.createElement('button');
  doBtn.type = 'button';
  doBtn.className = 'ds-verb do';
  doBtn.innerHTML = promoted
    ? `<span class="ds-eyebrow">Suggested</span><span class="ds-vt">${escapeHtml(promoted.label)}</span>`
    : `<span class="ds-vt">Ask Mobius</span>`;
  doBtn.addEventListener('click', () => (promoted ? opts.onDo(promoted) : opts.onAsk()));
  verbs.appendChild(doBtn);

  // Save — persist this page. Live when the envelope offers a save scope
  // (corpus is the built fetch-to-RAG lane); otherwise a visible "Soon" stub.
  const saveBtn = document.createElement('button');
  saveBtn.type = 'button';
  if (saveActions.length) {
    saveBtn.className = 'ds-verb save';
    saveBtn.title = 'Save this page — to the corpus or a bookmark';
    saveBtn.innerHTML = `<span class="ds-vt">Save</span><span class="ds-vs">to Mobius</span>`;
    saveBtn.addEventListener('click', () => opts.onSave(saveActions));
  } else {
    saveBtn.className = 'ds-verb save disabled';
    saveBtn.disabled = true;
    saveBtn.title = 'Save & file — coming soon';
    saveBtn.innerHTML = `<span class="ds-vt">Save</span><span class="ds-vs">Soon</span>`;
  }
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

  // No separate "customize" affordance — the "+ pin" chip below already opens
  // the same customize flow, so a second control here was redundant.
  drawer.appendChild(groupHead('Preferred · yours'));

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
