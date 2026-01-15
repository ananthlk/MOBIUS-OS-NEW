/**
 * Client-side UI defaults per mode.
 *
 * The UI (client) is the source of truth for default visibility of the 27 component keys.
 * The backend should only send per-message ui_overrides.
 */

import type { UiVisibilityDefaults } from '../types';

function allVisible(): UiVisibilityDefaults {
  return {
    clientLogo: true,
    mobiusLogo: true,
    statusIndicator: true,
    modeBadge: true,
    alertButton: true,
    settingsButton: true,
    contextDisplay: true,
    contextSummary: true,
    quickActionButton: true,
    tasksPanel: true,
    taskItem: true,
    thinkingBox: true,
    systemMessage: true,
    userMessage: true,
    feedbackComponent: true,
    guidanceActions: true,
    chatInput: true,
    chatTools: true,
    recordIdInput: true,
    workflowButtons: true,
    userDetails: true,
    preferencesPanel: true,
    chatMessage: true,
    header: true,
    chatArea: true,
    collapsiblePanel: true,
    dropdownMenu: true,
  };
}

/**
 * Return a full 27-key defaults map for a given mode label.
 * Mode matching is case-insensitive.
 */
export function getUiDefaultsForMode(mode: string): UiVisibilityDefaults {
  const normalized = (mode || '').trim().toLowerCase();
  const base = allVisible();

  // v1: start with Chat. Add new modes by extending this switch.
  switch (normalized) {
    case 'chat':
      return {
        ...base,
        // Chat defaults: keep feedback off unless a server message enables it per-message.
        feedbackComponent: false,
        // Chat defaults: keep scaffolding off unless the server explicitly enables it.
        thinkingBox: false,
        guidanceActions: false,
      };
    default:
      return base;
  }
}

