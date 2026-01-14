/**
 * Per-mode layout definitions (client side).
 *
 * Sections are fixed (header/context/tasks/chat/footer), but each section can contain an ordered
 * list of component instances, including multiple instances for dynamic forms/buttons.
 */

import type { ModeLayout } from './uiLayout';
import type { RecordType } from '../components/input/RecordIDInput';

export type ModeLayoutContext = {
  recordType: RecordType;
  recordId: string;
  onRecordChange: (recordType: RecordType, value: string) => void;
  workflowButtons: { label: string; onClick: () => void }[];
};

export function getLayoutForMode(mode: string, ctx: ModeLayoutContext): ModeLayout {
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
      // Form inputs / actions (multi-instance capable).
      {
        id: 'record_default',
        key: 'recordIdInput',
        props: {
          recordType: ctx.recordType,
          value: ctx.recordId,
          onChange: ctx.onRecordChange,
        },
      },
      {
        id: 'workflow_default',
        key: 'workflowButtons',
        props: {
          buttons: ctx.workflowButtons,
        },
      },
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

