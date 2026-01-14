/**
 * Per-mode layout definitions (client side).
 *
 * Sections are fixed (header/context/tasks/chat/footer), but each section can contain an ordered
 * list of component instances, including multiple instances for dynamic forms/buttons.
 */

import type { ModeLayout } from './uiLayout';

export function getLayoutForMode(mode: string): ModeLayout {
  const normalized = (mode || '').trim().toLowerCase();

  // Default layout: keep context summary + quick action like the current UI.
  const base: ModeLayout = {
    header: [],
    context: [
      {
        id: 'contextSummary_default',
        key: 'contextSummary',
        props: { summary: 'Chat mode active - ready to assist with questions and tasks.' },
      },
      {
        id: 'quickAction_default',
        key: 'quickActionButton',
        props: { label: 'Start Chat', onClick: () => console.log('Quick action clicked') },
      },
      // Examples of multi-instance (off by default via visibility if you prefer):
      // { id: 'record_patient', key: 'recordIdInput', props: { recordType: 'Patient ID', value: '', onChange: (...) => {} } },
      // { id: 'record_claim', key: 'recordIdInput', props: { recordType: 'Claim ID', value: '', onChange: (...) => {} } },
      // { id: 'buttons_primary', key: 'workflowButtons', props: { buttons: [...] } },
    ],
    tasks: [],
    chat: [],
    footer: [],
  };

  switch (normalized) {
    case 'chat':
      return base;
    default:
      return base;
  }
}

