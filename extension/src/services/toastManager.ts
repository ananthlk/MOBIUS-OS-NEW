/**
 * Toast Manager Service
 * 
 * Global service for managing toast notifications.
 * Runs independently of sidecar/mini state.
 * Toasts appear in top-right corner of browser window.
 */

import type { Alert, Toast, AlertType, UserAlertsResponse } from '../types/record';
import { getAuthHeader } from './auth';

// Configuration
const POLL_INTERVAL_MS = 30000;  // 30 seconds
const TOAST_CONTAINER_ID = 'mobius-toast-container';
const NOTIFICATIONS_ENABLED_KEY = 'mobius.notificationsEnabled';

// Auto-dismiss durations by type
const AUTO_DISMISS_MS: Record<AlertType, number> = {
  win: 5000,        // 5 seconds for celebrations
  update: 3000,     // 3 seconds for updates
  reminder: 0,      // Don't auto-dismiss reminders (need action)
  conflict: 0,      // Don't auto-dismiss conflicts (need resolution)
};

// State
let isInitialized = false;
let isPolling = false;
let pollIntervalId: number | null = null;
let previousAlertIds = new Set<string>();
let toastQueue: Toast[] = [];
let activeToasts: Map<string, HTMLElement> = new Map();
let notificationsEnabled = true;

// Callbacks
type ToastActionCallback = (toastId: string, actionId: string) => void;
type JumpToPatientCallback = (patientKey: string) => void;

let onToastAction: ToastActionCallback | null = null;
let onJumpToPatient: JumpToPatientCallback | null = null;

/**
 * Initialize the toast manager
 * Should be called once on extension load
 */
export async function init(options?: {
  onAction?: ToastActionCallback;
  onJumpToPatient?: JumpToPatientCallback;
}): Promise<void> {
  if (isInitialized) {
    console.log('[ToastManager] Already initialized');
    return;
  }
  
  console.log('[ToastManager] Initializing...');
  
  // Set callbacks
  if (options?.onAction) onToastAction = options.onAction;
  if (options?.onJumpToPatient) onJumpToPatient = options.onJumpToPatient;
  
  // Load notification preference
  notificationsEnabled = await loadNotificationPreference();
  
  // Create toast container
  createToastContainer();
  
  isInitialized = true;
  console.log('[ToastManager] Initialized, notifications enabled:', notificationsEnabled);
}

/**
 * Start polling for alerts
 */
export function startPolling(): void {
  if (isPolling) {
    console.log('[ToastManager] Already polling');
    return;
  }
  
  console.log('[ToastManager] Starting polling...');
  isPolling = true;
  
  // Poll immediately, then on interval
  void pollForAlerts();
  pollIntervalId = window.setInterval(() => {
    void pollForAlerts();
  }, POLL_INTERVAL_MS);
}

/**
 * Stop polling for alerts
 */
export function stopPolling(): void {
  if (!isPolling) return;
  
  console.log('[ToastManager] Stopping polling...');
  isPolling = false;
  
  if (pollIntervalId !== null) {
    window.clearInterval(pollIntervalId);
    pollIntervalId = null;
  }
}

/**
 * Show a toast notification
 */
export function show(toast: Toast): void {
  if (!isInitialized) {
    console.warn('[ToastManager] Not initialized, queueing toast');
    toastQueue.push(toast);
    return;
  }
  
  if (!notificationsEnabled && toast.type !== 'conflict') {
    // Still show conflicts even when notifications disabled
    console.log('[ToastManager] Notifications disabled, skipping toast:', toast.id);
    return;
  }
  
  renderToast(toast);
}

/**
 * Dismiss a toast
 */
export function dismiss(id: string): void {
  const element = activeToasts.get(id);
  if (!element) return;
  
  // Animate out
  element.classList.add('mobius-toast-exit');
  
  setTimeout(() => {
    element.remove();
    activeToasts.delete(id);
  }, 300);
}

/**
 * Dismiss all toasts
 */
export function dismissAll(): void {
  for (const id of activeToasts.keys()) {
    dismiss(id);
  }
}

/**
 * Jump to a patient's sidecar
 */
export function jumpToPatient(patientKey: string): void {
  if (onJumpToPatient) {
    onJumpToPatient(patientKey);
  } else {
    console.warn('[ToastManager] No jump-to-patient callback registered');
  }
}

/**
 * Set notifications enabled/disabled
 */
export async function setEnabled(enabled: boolean): Promise<void> {
  notificationsEnabled = enabled;
  await saveNotificationPreference(enabled);
  
  if (!enabled) {
    // Dismiss non-critical toasts when disabling
    for (const [id, element] of activeToasts.entries()) {
      const type = element.dataset.type as AlertType;
      if (type !== 'conflict' && type !== 'reminder') {
        dismiss(id);
      }
    }
  }
}

/**
 * Check if notifications are enabled
 */
export function isEnabled(): boolean {
  return notificationsEnabled;
}

// =============================================================================
// Internal Functions
// =============================================================================

/**
 * Create the toast container element
 */
function createToastContainer(): void {
  // Remove existing container if present
  const existing = document.getElementById(TOAST_CONTAINER_ID);
  if (existing) existing.remove();
  
  const container = document.createElement('div');
  container.id = TOAST_CONTAINER_ID;
  container.setAttribute('style', `
    position: fixed !important;
    top: 16px !important;
    right: 16px !important;
    z-index: 2147483647 !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 8px !important;
    pointer-events: none !important;
    max-width: 320px !important;
  `);
  
  document.body.appendChild(container);
  
  // Add styles
  addToastStyles();
}

/**
 * Get emoji for toast type
 */
function getToastEmoji(type: AlertType): string {
  switch (type) {
    case 'win': return '🎉';
    case 'update': return '✓';
    case 'reminder': return '⏰';
    case 'conflict': return '⚠️';
    default: return '📋';
  }
}

/**
 * Add toast CSS styles - minimal tag style
 */
function addToastStyles(): void {
  const styleId = 'mobius-toast-styles';
  if (document.getElementById(styleId)) return;
  
  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `
    .mobius-toast {
      pointer-events: auto !important;
      background: rgba(255, 255, 255, 0.95) !important;
      backdrop-filter: blur(8px) !important;
      border-radius: 6px !important;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
      padding: 6px 10px !important;
      display: flex !important;
      align-items: center !important;
      gap: 6px !important;
      cursor: pointer !important;
      animation: mobius-toast-enter 0.2s ease-out !important;
      border: 1px solid rgba(11, 18, 32, 0.08) !important;
      max-width: 260px !important;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }
    
    .mobius-toast-emoji {
      font-size: 14px !important;
      line-height: 1 !important;
      flex-shrink: 0 !important;
    }
    
    .mobius-toast-content {
      flex: 1 !important;
      min-width: 0 !important;
    }
    
    .mobius-toast-title {
      font-weight: 500 !important;
      font-size: 10px !important;
      color: #0b1220 !important;
      margin: 0 !important;
      line-height: 1.3 !important;
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
    }
    
    .mobius-toast-subtitle {
      font-size: 9px !important;
      color: rgba(91, 102, 122, 0.7) !important;
      margin: 0 !important;
      line-height: 1.3 !important;
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
    }
    
    .mobius-toast-close {
      background: none !important;
      border: none !important;
      cursor: pointer !important;
      color: rgba(91, 102, 122, 0.4) !important;
      font-size: 12px !important;
      line-height: 1 !important;
      padding: 0 !important;
      margin-left: 2px !important;
      flex-shrink: 0 !important;
    }
    
    .mobius-toast-close:hover {
      color: rgba(91, 102, 122, 0.7) !important;
    }
    
    .mobius-toast-exit {
      animation: mobius-toast-exit 0.2s ease-in forwards !important;
    }
    
    @keyframes mobius-toast-enter {
      from {
        opacity: 0;
        transform: translateY(-8px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    @keyframes mobius-toast-exit {
      from {
        opacity: 1;
        transform: translateY(0);
      }
      to {
        opacity: 0;
        transform: translateY(-8px);
      }
    }
  `;
  
  document.head.appendChild(style);
}

/**
 * Render a toast to the DOM - minimal tag style with emoji
 */
function renderToast(toast: Toast): void {
  const container = document.getElementById(TOAST_CONTAINER_ID);
  if (!container) {
    console.error('[ToastManager] Container not found');
    return;
  }
  
  // Don't show duplicate toasts
  if (activeToasts.has(toast.id)) {
    return;
  }
  
  const element = document.createElement('div');
  element.className = 'mobius-toast';
  element.dataset.type = toast.type;
  element.dataset.id = toast.id;
  
  // Emoji indicator
  const emoji = document.createElement('span');
  emoji.className = 'mobius-toast-emoji';
  emoji.textContent = getToastEmoji(toast.type);
  element.appendChild(emoji);
  
  // Content wrapper
  const content = document.createElement('div');
  content.className = 'mobius-toast-content';
  
  // Title - simplified format
  const title = document.createElement('div');
  title.className = 'mobius-toast-title';
  title.textContent = toast.title;
  content.appendChild(title);
  
  // Subtitle (patient name)
  if (toast.subtitle) {
    const subtitle = document.createElement('div');
    subtitle.className = 'mobius-toast-subtitle';
    subtitle.textContent = toast.subtitle;
    content.appendChild(subtitle);
  }
  
  element.appendChild(content);
  
  // Close button
  const closeBtn = document.createElement('button');
  closeBtn.className = 'mobius-toast-close';
  closeBtn.innerHTML = '×';
  closeBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dismiss(toast.id);
  });
  element.appendChild(closeBtn);
  
  // Click to jump to patient
  if (toast.patient_key) {
    element.addEventListener('click', () => {
      jumpToPatient(toast.patient_key!);
      dismiss(toast.id);
    });
  }
  
  // Add to DOM
  container.appendChild(element);
  activeToasts.set(toast.id, element);
  
  // Auto-dismiss
  const autoDismissMs = toast.auto_dismiss_ms ?? AUTO_DISMISS_MS[toast.type];
  if (autoDismissMs > 0) {
    setTimeout(() => {
      dismiss(toast.id);
    }, autoDismissMs);
  }
}

/**
 * Poll for new alerts from backend
 */
async function pollForAlerts(): Promise<void> {
  try {
    const authHeader = await getAuthHeader();
    if (!authHeader) {
      // Not authenticated, skip polling
      return;
    }
    
    const response = await fetch('/api/v1/user/alerts', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...authHeader,
      },
    });
    
    if (!response.ok) {
      console.error('[ToastManager] Failed to fetch alerts:', response.status);
      return;
    }
    
    const data: UserAlertsResponse = await response.json();
    
    // Find new alerts
    const newAlerts = data.alerts.filter(alert => !previousAlertIds.has(alert.id));
    
    // Update previous IDs
    previousAlertIds = new Set(data.alerts.map(a => a.id));
    
    // Show toasts for new alerts
    for (const alert of newAlerts) {
      const toast = alertToToast(alert);
      show(toast);
    }
    
  } catch (error) {
    console.error('[ToastManager] Error polling alerts:', error);
  }
}

/**
 * Convert an Alert to a Toast
 */
function alertToToast(alert: Alert): Toast {
  const toast: Toast = {
    id: alert.id,
    type: alert.type,
    title: alert.title,
    subtitle: alert.subtitle,
    patient_key: alert.patient_key,
    auto_dismiss_ms: AUTO_DISMISS_MS[alert.type],
  };
  
  // Add actions for reminders
  if (alert.type === 'reminder') {
    toast.actions = [
      { id: 'still_on_it', label: 'Still on it' },
      { id: 'hand_to_mobius', label: 'Hand to Mobius' },
    ];
  }
  
  return toast;
}

/**
 * Load notification preference from storage
 */
async function loadNotificationPreference(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      chrome.storage.local.get([NOTIFICATIONS_ENABLED_KEY], (result) => {
        // Default to true if not set
        resolve(result[NOTIFICATIONS_ENABLED_KEY] !== false);
      });
    } else {
      const stored = localStorage.getItem(NOTIFICATIONS_ENABLED_KEY);
      resolve(stored !== 'false');
    }
  });
}

/**
 * Save notification preference to storage
 */
async function saveNotificationPreference(enabled: boolean): Promise<void> {
  return new Promise((resolve) => {
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      chrome.storage.local.set({ [NOTIFICATIONS_ENABLED_KEY]: enabled }, () => {
        resolve();
      });
    } else {
      localStorage.setItem(NOTIFICATIONS_ENABLED_KEY, String(enabled));
      resolve();
    }
  });
}

/**
 * Cleanup - call when extension unloads
 */
export function cleanup(): void {
  stopPolling();
  dismissAll();
  
  const container = document.getElementById(TOAST_CONTAINER_ID);
  if (container) container.remove();
  
  isInitialized = false;
}
