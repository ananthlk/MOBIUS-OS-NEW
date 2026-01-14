/**
 * Session management utilities
 */

import { SessionId } from '../types';

const SESSION_STORAGE_KEY = 'current_session_id';

/**
 * Generate a new session ID (UUID v4)
 */
export function generateSessionId(): SessionId {
  return 'session_' + crypto.randomUUID();
}

/**
 * Get current session ID from storage, or generate a new one
 */
export async function getOrCreateSessionId(): Promise<SessionId> {
  return new Promise((resolve) => {
    chrome.storage.local.get([SESSION_STORAGE_KEY], (result) => {
      if (result[SESSION_STORAGE_KEY]) {
        resolve(result[SESSION_STORAGE_KEY]);
      } else {
        const newSessionId = generateSessionId();
        chrome.storage.local.set({ [SESSION_STORAGE_KEY]: newSessionId }, () => {
          resolve(newSessionId);
        });
      }
    });
  });
}

/**
 * Get current session ID (synchronous check)
 */
export async function getSessionId(): Promise<SessionId | null> {
  return new Promise((resolve) => {
    chrome.storage.local.get([SESSION_STORAGE_KEY], (result) => {
      resolve(result[SESSION_STORAGE_KEY] || null);
    });
  });
}
