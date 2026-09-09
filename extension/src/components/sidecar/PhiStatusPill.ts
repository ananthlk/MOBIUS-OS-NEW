/**
 * PhiStatusPill — the HIPAA status indicator (Phase 2.3).
 *
 * A STATUS, not a control: green when no patient information is in the
 * current context, amber when a patient/PHI is detected. Consent itself is
 * the per-read permission moment (the ack card), never a mode you pre-set —
 * so this pill only reports, it doesn't toggle.
 */

export function PhiStatusPill(present: boolean): HTMLElement {
  const pill = document.createElement('span');
  pill.className = 'sidecar-phi-pill' + (present ? ' on' : ' off');
  pill.setAttribute(
    'title',
    present
      ? 'Patient information may be in view. Reading the page will ask for consent and log an attestation.'
      : 'No patient information detected in this context.'
  );

  const dot = document.createElement('span');
  dot.className = 'sidecar-phi-dot';
  pill.appendChild(dot);

  const label = document.createElement('span');
  label.textContent = present ? 'PHI' : 'PHI off';
  pill.appendChild(label);

  return pill;
}
