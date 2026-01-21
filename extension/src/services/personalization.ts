/**
 * Personalization Service
 * 
 * Handles name interpolation and privacy mode for the Sidecar UI.
 * Ensures consistent, personalized text across Mini and Sidecar.
 */

import type { RecordContext, PrivacyContext } from '../types/record';

// Storage key for privacy mode preference
const PRIVACY_MODE_KEY = 'mobius.privacyMode';

/**
 * Get initials from a full name
 * "John Smith" -> "J.S."
 */
export function getInitials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 0) return '';
  
  return parts
    .map(part => part.charAt(0).toUpperCase())
    .join('.') + '.';
}

/**
 * Get display name based on privacy mode
 * Privacy ON: "J.S."
 * Privacy OFF: "John Smith"
 */
export function getDisplayName(record: RecordContext, isPrivate: boolean): string {
  if (isPrivate) {
    return getInitials(record.displayName);
  }
  return record.displayName;
}

/**
 * Get short name based on privacy mode
 * Privacy ON: "J."
 * Privacy OFF: "John"
 */
export function getShortName(record: RecordContext, isPrivate: boolean): string {
  if (isPrivate) {
    const firstName = record.shortName.split(/\s+/)[0];
    return firstName.charAt(0).toUpperCase() + '.';
  }
  return record.shortName;
}

/**
 * Get possessive form based on privacy mode
 * Privacy ON: "J.S.'s"
 * Privacy OFF: "John's"
 */
export function getPossessive(record: RecordContext, isPrivate: boolean): string {
  if (isPrivate) {
    return getInitials(record.displayName) + "'s";
  }
  return record.possessive;
}

/**
 * Template tokens that can be interpolated
 */
type TemplateTokens = {
  '{{name}}': string;
  '{{shortName}}': string;
  '{{possessive}}': string;
  '{{staffName}}': string;
  '{{staffShortName}}': string;
};

/**
 * Interpolate template with record context
 * 
 * @param template - Template string with {{tokens}}
 * @param context - Privacy context with record and optional staff info
 * @returns Interpolated string
 * 
 * @example
 * formatLabel("{{possessive}} insurance verified", context)
 * // Privacy OFF: "John's insurance verified"
 * // Privacy ON: "J.S.'s insurance verified"
 */
export function formatLabel(template: string, context: PrivacyContext): string {
  const { isPrivate, record, staff } = context;
  
  const tokens: TemplateTokens = {
    '{{name}}': getDisplayName(record, isPrivate),
    '{{shortName}}': getShortName(record, isPrivate),
    '{{possessive}}': getPossessive(record, isPrivate),
    '{{staffName}}': staff ? (isPrivate ? getInitials(staff.displayName) : staff.displayName) : 'Team member',
    '{{staffShortName}}': staff ? (isPrivate ? staff.shortName.charAt(0) + '.' : staff.shortName) : '',
  };
  
  let result = template;
  for (const [token, value] of Object.entries(tokens)) {
    result = result.replace(new RegExp(token.replace(/[{}]/g, '\\$&'), 'g'), value);
  }
  
  return result;
}

/**
 * Generate celebration text for wins
 */
export function getCelebrationText(
  milestoneName: string, 
  context: PrivacyContext,
  completedBy: 'user' | 'mobius' | 'external'
): string {
  const possessive = getPossessive(context.record, context.isPrivate);
  
  const templates: Record<string, Record<string, string>> = {
    'visit': {
      user: `Great work! ${possessive} visit is confirmed.`,
      mobius: `${possessive} visit has been confirmed.`,
      external: `${possessive} visit is now confirmed!`,
    },
    'eligibility': {
      user: `Nice! You verified ${possessive} insurance.`,
      mobius: `${possessive} insurance has been verified.`,
      external: `${possessive} insurance is confirmed!`,
    },
    'authorization': {
      user: `Excellent! ${possessive} authorization is secured.`,
      mobius: `${possessive} authorization has been approved!`,
      external: `${possessive} auth came through!`,
    },
    'documentation': {
      user: `Well done! ${possessive} documentation is ready.`,
      mobius: `${possessive} documentation is complete.`,
      external: `${possessive} docs are all set!`,
    },
  };
  
  const milestoneTemplates = templates[milestoneName.toLowerCase()] || templates['visit'];
  return milestoneTemplates[completedBy] || milestoneTemplates['external'];
}

/**
 * Privacy mode preference management
 */
export const PrivacyMode = {
  /**
   * Check if privacy mode is enabled
   */
  async isEnabled(): Promise<boolean> {
    return new Promise((resolve) => {
      if (typeof chrome !== 'undefined' && chrome.storage?.local) {
        chrome.storage.local.get([PRIVACY_MODE_KEY], (result) => {
          resolve(result[PRIVACY_MODE_KEY] === true);
        });
      } else {
        // Fallback for non-extension context
        resolve(localStorage.getItem(PRIVACY_MODE_KEY) === 'true');
      }
    });
  },
  
  /**
   * Set privacy mode
   */
  async setEnabled(enabled: boolean): Promise<void> {
    return new Promise((resolve) => {
      if (typeof chrome !== 'undefined' && chrome.storage?.local) {
        chrome.storage.local.set({ [PRIVACY_MODE_KEY]: enabled }, () => {
          resolve();
        });
      } else {
        localStorage.setItem(PRIVACY_MODE_KEY, String(enabled));
        resolve();
      }
    });
  },
  
  /**
   * Toggle privacy mode
   */
  async toggle(): Promise<boolean> {
    const current = await this.isEnabled();
    const newValue = !current;
    await this.setEnabled(newValue);
    return newValue;
  },
};

/**
 * Build a PrivacyContext from available data
 */
export function buildPrivacyContext(
  record: RecordContext,
  staffName?: string,
  isPrivate: boolean = false
): PrivacyContext {
  return {
    isPrivate,
    record,
    staff: staffName ? {
      displayName: staffName,
      shortName: staffName.split(/\s+/)[0] || staffName,
    } : undefined,
  };
}

/**
 * Create a RecordContext for a patient
 */
export function createPatientContext(
  id: string,
  fullName: string,
  firstName?: string
): RecordContext {
  const shortName = firstName || fullName.split(/\s+/)[0] || fullName;
  
  // Handle possessive form (simple English rules)
  const possessive = shortName.endsWith('s') 
    ? `${shortName}'` 
    : `${shortName}'s`;
  
  return {
    type: 'patient',
    id,
    displayName: fullName,
    shortName,
    possessive,
  };
}
