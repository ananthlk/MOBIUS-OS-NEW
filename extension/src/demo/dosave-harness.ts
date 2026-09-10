/**
 * Standalone harness for the corrected Do/Save action core — renders the REAL
 * compiled `DoSaveActions` + `showSaveOffer` over the REAL `web` envelope, with
 * the REAL sidebar.css, so the Do/Save split can be seen without auth or a live
 * host page. Demo-only; not shipped in the extension bundle.
 */
import '../styles/sidebar.css';
import { resolveEnvelope } from '../services/envelopes';
import type { EnvelopeAction } from '../types/sidebar';
import { DoSaveActions } from '../components/sidecar/DoSaveActions';
import { showSaveOffer, SaveOfferRow } from '../components/sidecar/SaveOffer';

const envelope = resolveEnvelope('web', 'biller');

const mount = document.getElementById('mount')!;
const log = document.getElementById('log')!;
const say = (m: string) => {
  log.textContent = m;
};

const preferred = [
  { id: 'check-claim', label: 'Check a claim' },
  { id: 'retrieve-patient', label: 'Look up a patient' },
];

function runAction(action: EnvelopeAction) {
  if (action.kind === 'ingest') {
    say(`▶ Save → corpus: "${action.label}" — would fetch the page in-session and file it for retrieval (PHI-gated).`);
  } else if (action.kind === 'synthesize') {
    say(`▶ Do: "${action.label}" — would summarize the page in chat.`);
  } else if (action.kind === 'ask') {
    say(`▶ Do: "${action.label}" — would focus the ask bar scoped to this page.`);
  } else {
    say(`▶ ${action.label}`);
  }
}

const ds = DoSaveActions(envelope, {
  onDo: (a) => runAction(a),
  onSave: (saveActions) => {
    const rows: SaveOfferRow[] = [
      ...saveActions.map((a) => ({ kind: 'live' as const, action: a })),
      { kind: 'soon', label: 'Bookmark for me', sublabel: 'A pointer in my library — no bytes fetched' },
      { kind: 'soon', label: 'Bookmark on a patient', sublabel: 'Attach this source to a patient record' },
      { kind: 'soon', label: 'Track as a system source', sublabel: 'Watch this page for changes' },
    ];
    showSaveOffer(rows, (a) => runAction(a));
  },
  onAction: (a) => runAction(a),
  onAsk: () => say('▶ Ask Mobius'),
  preferred,
  onPreferred: (p) => say(`▶ Preferred: ${p.label}`),
  onCustomize: () => say('▶ + pin (customize)'),
});

mount.appendChild(ds);
say('Ready — the DO verb runs "Summarize"; the SAVE verb opens the scope offer.');
