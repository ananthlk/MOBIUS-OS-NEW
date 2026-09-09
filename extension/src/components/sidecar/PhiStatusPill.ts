/**
 * PhiStatusPill — the HIPAA acknowledgement toggle (Phase 2.3).
 *
 * The explicit-acknowledgement control: OFF (default) means Mobius asks for
 * consent before reading a page; turning it ON is the attestation, so the
 * per-read prompts stop for this site. Clicking it IS the consent record.
 * The authoritative server-side PHI gate still runs regardless — this only
 * governs the client-side prompt.
 */

export interface PhiStatusPillOpts {
  acknowledged: boolean;
  onToggle: (next: boolean) => void;
}

export function PhiStatusPill(opts: PhiStatusPillOpts): HTMLElement {
  const pill = document.createElement('button');
  pill.type = 'button';
  pill.className = 'sidecar-phi-pill ' + (opts.acknowledged ? 'on' : 'off');
  const title = opts.acknowledged
    ? 'PHI acknowledged for this site — Mobius won’t ask before each read. Click to turn off.'
    : 'PHI off — Mobius asks for consent before reading a page. Click to acknowledge PHI for this site and stop the prompts.';
  pill.setAttribute('title', title);
  // Screen-reader meaning is otherwise hover-only; expose the toggle state and
  // a full-sentence label so the attestation is legible without a pointer.
  pill.setAttribute('aria-pressed', String(opts.acknowledged));
  pill.setAttribute(
    'aria-label',
    opts.acknowledged
      ? 'PHI acknowledged for this site. Activate to remove the acknowledgement.'
      : 'PHI prompts on. Activate to acknowledge PHI for this site and stop the prompts.'
  );

  const dot = document.createElement('span');
  dot.className = 'sidecar-phi-dot';
  pill.appendChild(dot);

  const label = document.createElement('span');
  label.textContent = opts.acknowledged ? 'PHI on' : 'PHI off';
  pill.appendChild(label);

  pill.addEventListener('click', () => opts.onToggle(!opts.acknowledged));
  return pill;
}
