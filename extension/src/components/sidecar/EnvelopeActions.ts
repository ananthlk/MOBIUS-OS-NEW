/**
 * EnvelopeActions — renders the proposed action set for the resolved
 * envelope (services/envelopes.ts). This is the "variable action zone";
 * the sidecar chrome around it stays constant.
 *
 * Propose-not-morph: actions are shown behind a "detected" chip and only
 * run on explicit click. `preview`/`collate`/`find_email` kinds are
 * shape-only placeholders and are visually marked as such.
 */

import type { Envelope, EnvelopeAction } from '../../services/envelopes';
import { ICONS } from './icons';

const PREVIEW_KINDS = new Set(['preview', 'collate', 'find_email']);

export function EnvelopeActions(
  envelope: Envelope,
  onAction: (action: EnvelopeAction) => void
): HTMLElement {
  const root = document.createElement('div');
  root.className = 'sidecar-envact';

  const chip = document.createElement('div');
  chip.className = 'sidecar-envact-chip';
  chip.style.color = envelope.accentVar;
  chip.style.borderColor = `color-mix(in srgb, ${envelope.accentVar} 40%, var(--mobius-border, #e2e8f0))`;
  chip.innerHTML = ICONS.page;
  const chipText = document.createElement('span');
  chipText.textContent = envelope.chipLabel;
  chip.appendChild(chipText);
  root.appendChild(chip);

  const propose = document.createElement('div');
  propose.className = 'sidecar-envact-propose';
  propose.textContent = envelope.propose;
  root.appendChild(propose);

  for (const action of envelope.actions) {
    const isPreview = PREVIEW_KINDS.has(action.kind);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className =
      'sidecar-envact-btn' +
      (action.primary ? ' primary' : '') +
      (isPreview ? ' preview' : '');

    const ic = document.createElement('span');
    ic.className = 'sidecar-envact-ic';
    ic.style.background = isPreview ? 'var(--mobius-text-muted, #64748b)' : envelope.accentVar;
    ic.innerHTML = ICONS[action.icon] || ICONS.mobius;
    btn.appendChild(ic);

    const tx = document.createElement('span');
    tx.className = 'sidecar-envact-tx';
    const label = document.createElement('span');
    label.className = 'sidecar-envact-label';
    label.textContent = action.label;
    tx.appendChild(label);
    if (action.sublabel) {
      const sub = document.createElement('small');
      sub.textContent = action.sublabel;
      tx.appendChild(sub);
    }
    btn.appendChild(tx);

    btn.addEventListener('click', () => onAction(action));
    root.appendChild(btn);
  }

  return root;
}
