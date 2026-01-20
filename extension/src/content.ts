/**
 * Content script for Mobius OS extension
 * Injects the Mobius OS sidebar into web pages
 */

import './styles/sidebar.css';
import { getOrCreateSessionId } from './utils/session';
import { fetchMiniStatus, searchMiniPatients, sendChatMessage, submitMiniNote, submitAttentionStatus, reportIssue, AttentionStatus, resolvePatientContext, fetchDetectionConfig } from './services/api';
import { getUiDefaultsForMode } from './utils/uiDefaults';
import { getLayoutForMode } from './utils/modeLayout';
import { renderSection } from './utils/uiLayout';
import { 
  ClientLogo, 
  MobiusLogo, 
  ContextDisplay,
  AlertButton,
  SettingsButton,
  ContextSummary,
  QuickActionButton,
  TasksPanel,
  ChatArea,
  ChatInput,
  RecordIDInput,
  WorkflowButtons,
  UserDetails,
  PreferencesPanel
} from './components';
import { Message, Status, Task, StatusIndicatorStatus, LLMChoice, AgentMode, DetectedPatient, ResolvedPatientContext, UserProfile, PersonalizationData, MiniStatusResponse as MiniStatusResponseType } from './types';
import { PatientContextDetector } from './services/patientContextDetector';
import { getAuthService } from './services/auth';
import { PreferencesModal, PREFERENCES_MODAL_STYLES, UserPreferences } from './components/settings/PreferencesModal';

const componentRegistry = {
  contextSummary: ContextSummary,
  quickActionButton: QuickActionButton,
  recordIdInput: RecordIDInput,
  workflowButtons: WorkflowButtons,
  tasksPanel: TasksPanel,
  chatInput: ChatInput,
} as const;

// App state
let sessionId: string;
let messages: Message[] = [];
let mobiusStatus: Status = 'idle';
let currentMode = 'Chat';
let currentStatus: StatusIndicatorStatus = 'proceed';
let recordType: 'Patient ID' | 'Claim ID' | 'Visit ID' | 'Authorization ID' | 'Other' = 'Patient ID';
let recordId = '';
let llmChoice: LLMChoice = 'Gemini';
let agentMode: AgentMode = 'Agentic';
let tasks: Task[] = [];
let sidebarContainer: HTMLElement | null = null;

type MiniColor = 'green' | 'yellow' | 'grey' | 'blue' | 'red';
type ExecutionMode = 'agentic' | 'copilot' | 'user_driven';
type MiniLine = { 
  color: MiniColor; 
  text: string;
  mode?: ExecutionMode;
  mode_text?: string;
};

// Mode icon mapping for tasking display
const getModeIcon = (mode?: ExecutionMode): string => {
  switch (mode) {
    case 'agentic': return '🤖';
    case 'copilot': return '👤✓';
    case 'user_driven': return '👤';
    default: return '';
  }
};

const MINI_IDS = {
  root: 'mobius-os-mini',
  modal: 'mobius-os-mini-modal',
  toast: 'mobius-os-mini-toast',
  sidebar: 'mobius-os-sidebar',
  pageAdjust: 'mobius-os-page-adjust',
} as const;

const STORAGE_KEYS = {
  allowedDomains: 'mobius.allowedDomains',
  miniPos: 'mobius.miniPos',
  patientOverride: 'mobius.patientOverride',
  miniTheme: 'mobius.miniTheme',
} as const;

type MiniTheme = 'light' | 'dark' | 'blue' | 'glass';

// Apply theme class to Mini widget
function applyMiniTheme(root: HTMLElement, theme: string) {
  root.classList.remove('theme-light', 'theme-dark', 'theme-blue', 'theme-glass');
  root.classList.add(`theme-${theme}`);
}

// Save theme to Chrome storage
async function saveMiniTheme(theme: string): Promise<void> {
  try {
    await chrome.storage.local.set({ [STORAGE_KEYS.miniTheme]: theme });
  } catch (e) {
    console.warn('[Mobius] Failed to save theme:', e);
  }
}

// Load theme from Chrome storage
async function loadMiniTheme(): Promise<MiniTheme> {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEYS.miniTheme);
    return (result[STORAGE_KEYS.miniTheme] as MiniTheme) || 'light';
  } catch {
    return 'light';
  }
}

type MiniPos = { x: number; y: number };
type PatientOverride = { name: string; id: string; dob?: string };

let miniLastPos: MiniPos | null = null;
let miniProceed: MiniLine = { color: 'grey', text: 'Proceed: Not assessed' };
let miniTasking: MiniLine = { color: 'grey', text: 'Tasking: Not applicable' };
let patientOverride: PatientOverride | null = null;

// Patient Context Detection
let patientContextDetector: PatientContextDetector | null = null;
let autoDetectedPatient: ResolvedPatientContext | null = null;
let isAutoDetectionEnabled = true; // Re-enabled for patient context detection

// Needs Attention state (new UI)
let needsAttention: {
  color: MiniColor;
  problemStatement: string | null;
  userStatus: AttentionStatus;
} = { color: 'grey', problemStatement: null, userStatus: null };
let taskCount = 0;

// User Awareness state
let isAuthenticated = false;
let currentUserProfile: UserProfile | null = null;
let currentPersonalization: PersonalizationData | null = null;
let greetingDismissed = false;

function setVisible(el: HTMLElement, visible: boolean) {
  el.style.display = visible ? '' : 'none';
}

function getHostname(): string {
  try {
    return window.location.hostname.toLowerCase();
  } catch {
    return '';
  }
}

async function storageGet<T>(keys: string[]): Promise<Record<string, T | undefined>> {
  return new Promise((resolve) => {
    chrome.storage.local.get(keys, (items) => resolve(items as Record<string, T | undefined>));
  });
}

async function storageSet(items: Record<string, unknown>): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.set(items, () => resolve());
  });
}

async function getAllowedDomains(): Promise<string[]> {
  const res = await storageGet<string[]>([STORAGE_KEYS.allowedDomains]);
  const list = res[STORAGE_KEYS.allowedDomains];
  return Array.isArray(list) ? list : [];
}

async function setDomainAllowed(hostname: string, allowed: boolean): Promise<void> {
  const host = (hostname || '').toLowerCase();
  if (!host) return;
  const current = await getAllowedDomains();
  const next = new Set(current.map((d) => String(d).toLowerCase()).filter(Boolean));
  if (allowed) next.add(host);
  else next.delete(host);
  await storageSet({ [STORAGE_KEYS.allowedDomains]: Array.from(next).sort() });
}

async function isDomainAllowed(hostname: string): Promise<boolean> {
  const host = (hostname || '').toLowerCase();
  if (!host) return false;
  const allowed = await getAllowedDomains();
  return allowed.map((d) => d.toLowerCase()).includes(host);
}

function removeMini(): void {
  const existing = document.getElementById(MINI_IDS.root);
  if (existing) existing.remove();
  const modal = document.getElementById(MINI_IDS.modal);
  if (modal) modal.remove();
  
  // Stop patient context detection when Mini is removed
  stopPatientContextDetection();
}

function removeSidebar(): void {
  const existingSidebar = document.getElementById(MINI_IDS.sidebar);
  if (existingSidebar) existingSidebar.remove();
  const style = document.getElementById(MINI_IDS.pageAdjust);
  if (style) style.remove();
  sidebarContainer = null;
}

function showToast(message: string): void {
  const existing = document.getElementById(MINI_IDS.toast);
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.id = MINI_IDS.toast;
  toast.className = 'mobius-mini-toast';
  toast.textContent = message;
  document.body.appendChild(toast);
  window.setTimeout(() => toast.remove(), 1600);
}

function colorToCssClass(color: MiniColor): string {
  switch (color) {
    case 'green':
      return 'dot-green';
    case 'yellow':
      return 'dot-yellow';
    case 'blue':
      return 'dot-blue';
    case 'red':
      return 'dot-red';
    case 'grey':
    default:
      return 'dot-grey';
  }
}

async function loadMiniPersistedState(): Promise<void> {
  const res = await storageGet<unknown>([
    STORAGE_KEYS.miniPos,
    STORAGE_KEYS.patientOverride,
  ]);

  const pos = res[STORAGE_KEYS.miniPos] as MiniPos | undefined;
  if (pos && typeof pos.x === 'number' && typeof pos.y === 'number') {
    miniLastPos = { x: pos.x, y: pos.y };
  }

  const p = res[STORAGE_KEYS.patientOverride] as PatientOverride | undefined;
  if (p && typeof p.name === 'string' && typeof p.id === 'string') {
    patientOverride = { name: p.name, id: p.id, dob: typeof p.dob === 'string' ? p.dob : undefined };
  }
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function clampMiniPos(pos: MiniPos, rootEl: HTMLElement): MiniPos {
  const rect = rootEl.getBoundingClientRect();
  const margin = 8;
  const maxX = window.innerWidth - rect.width - margin;
  const maxY = window.innerHeight - rect.height - margin;
  return {
    x: clamp(pos.x, margin, Math.max(margin, maxX)),
    y: clamp(pos.y, margin, Math.max(margin, maxY)),
  };
}

async function setMiniPos(rootEl: HTMLElement, pos: MiniPos): Promise<void> {
  const clamped = clampMiniPos(pos, rootEl);
  rootEl.style.left = `${clamped.x}px`;
  rootEl.style.top = `${clamped.y}px`;
  miniLastPos = clamped;
  await storageSet({ [STORAGE_KEYS.miniPos]: clamped });
}

function getPatientDisplay(): PatientOverride {
  // Priority: manual override > auto-detected > default
  if (patientOverride) {
    return patientOverride;
  }
  if (autoDetectedPatient?.found) {
    return {
      name: autoDetectedPatient.display_name || 'Unknown',
      id: autoDetectedPatient.patient_key || '',
      dob: '',
    };
  }
  return { name: 'Unknown', id: '', dob: '' };
}

/**
 * Get the current patient key for API calls.
 * Prefers manual override, falls back to auto-detected.
 */
function getCurrentPatientKey(): string | undefined {
  if (patientOverride?.id) {
    return patientOverride.id;
  }
  if (autoDetectedPatient?.found && autoDetectedPatient.patient_key) {
    return autoDetectedPatient.patient_key;
  }
  return undefined;
}

/**
 * Handle auto-detected patient context from the detector.
 */
async function handleAutoDetectedPatient(detected: DetectedPatient | null): Promise<void> {
  if (!detected) {
    // Patient context cleared
    if (autoDetectedPatient) {
      autoDetectedPatient = null;
      console.log('[Mobius] Auto-detected patient cleared');
      // Re-render Mini with no patient
      await renderMiniIfAllowed();
    }
    return;
  }
  
  // Resolve the detected patient via backend crosswalk
  console.log('[Mobius] Resolving detected patient:', detected);
  const resolved = await resolvePatientContext(detected);
  
  if (resolved.found) {
    autoDetectedPatient = resolved;
    console.log('[Mobius] Patient resolved:', resolved);
    
    // Update Mini widget if visible and no manual override
    if (!patientOverride) {
      await updateMiniWithResolvedPatient(resolved);
    }
  } else {
    console.log('[Mobius] Patient not found in system:', detected);
    // Keep the detection info even if not found (might be useful)
    autoDetectedPatient = resolved;
  }
}

/**
 * Update Mini widget with resolved patient data.
 */
async function updateMiniWithResolvedPatient(resolved: ResolvedPatientContext): Promise<void> {
  const mini = document.getElementById(MINI_IDS.root) as HTMLElement | null;
  if (!mini) return;
  
  // Update patient display
  const nameEl = mini.querySelector<HTMLElement>('.mobius-mini-patient-name');
  const idEl = mini.querySelector<HTMLElement>('.mobius-mini-patient-id');
  
  if (nameEl) nameEl.textContent = resolved.display_name || 'Unknown';
  if (idEl && resolved.id_masked) idEl.textContent = `ID ${resolved.id_masked}`;
  
  // Update minimized info patient name
  const minimizedPatient = mini.querySelector<HTMLElement>('.mobius-mini-minimized-patient');
  if (minimizedPatient) minimizedPatient.textContent = resolved.display_name || 'Unknown';
  
  // Fetch updated status for the detected patient
  if (resolved.patient_key) {
    try {
      const status = await fetchMiniStatus(sessionId, resolved.patient_key);
      
      // Update proceed/tasking state
      miniProceed = status.proceed;
      if (status.tasking) {
        miniTasking = status.tasking;
      }
      
      // Update needs_attention
      if (status.needs_attention) {
        needsAttention = {
          color: status.needs_attention.color,
          problemStatement: status.needs_attention.problem_statement,
          userStatus: status.needs_attention.user_status,
        };
      }
      taskCount = status.task_count || 0;
      
      // Re-render Mini attention UI
      const attentionRow = mini.querySelector<HTMLElement>('.mobius-mini-attention-row');
      let effectiveColor = needsAttention.color;
      if (needsAttention.userStatus === 'resolved') effectiveColor = 'green';
      else if (needsAttention.userStatus === 'confirmed_unresolved') effectiveColor = 'yellow';
      else if (needsAttention.userStatus === 'unable_to_confirm') effectiveColor = 'grey';
      
      if (attentionRow) {
        const dot = attentionRow.querySelector<HTMLElement>('.mobius-mini-dot');
        const text = attentionRow.querySelector<HTMLElement>('.mobius-mini-problem-text');
        if (dot) {
          dot.className = `mobius-mini-dot ${colorToCssClass(effectiveColor)}`;
        }
        if (text) {
          if (needsAttention.userStatus === 'resolved') {
            text.textContent = 'Resolved';
          } else if (needsAttention.problemStatement) {
            text.textContent = needsAttention.problemStatement;
          } else {
            text.textContent = 'No issues detected';
          }
        }
      }
      
      // Update minimized info dot
      const minimizedDot = mini.querySelector<HTMLElement>('.mobius-mini-minimized-info .mobius-mini-dot');
      if (minimizedDot) {
        minimizedDot.className = `mobius-mini-dot ${colorToCssClass(effectiveColor)}`;
      }
      
      // Update task badge
      const taskBadgeRow = mini.querySelector<HTMLElement>('.mobius-mini-task-badge-row');
      if (taskBadgeRow) {
        const countEl = taskBadgeRow.querySelector<HTMLElement>('.mobius-mini-task-count');
        if (countEl) countEl.textContent = String(taskCount);
        taskBadgeRow.style.display = taskCount > 0 ? '' : 'none';
      }
      
      // Show toast for auto-detection
      showToast(`Patient detected: ${resolved.display_name || 'Unknown'}`);
    } catch (err) {
      console.error('[Mobius] Error fetching status for auto-detected patient:', err);
    }
  }
}

/**
 * Initialize the patient context detector.
 */
function initPatientContextDetector(): void {
  if (patientContextDetector) {
    console.log('[Mobius] Patient context detector already initialized');
    return;
  }
  
  patientContextDetector = new PatientContextDetector({
    debounceMs: 500,
    strategies: ['dataAttributes', 'url', 'domText'],
    observeMutations: true,
    autoStart: false,
  });
  
  // Subscribe to detection events
  patientContextDetector.on('patientDetected', (detected) => {
    if (isAutoDetectionEnabled && detected) {
      void handleAutoDetectedPatient(detected);
    }
  });
  
  patientContextDetector.on('patientChanged', (detected) => {
    if (isAutoDetectionEnabled && detected) {
      void handleAutoDetectedPatient(detected);
    }
  });
  
  patientContextDetector.on('patientCleared', () => {
    if (isAutoDetectionEnabled) {
      void handleAutoDetectedPatient(null);
    }
  });
  
  patientContextDetector.on('detectionError', () => {
    console.warn('[Mobius] Patient detection error');
  });
  
  // Fetch tenant-specific detection config if available
  void fetchDetectionConfig(window.location.hostname).then((config) => {
    if (config && patientContextDetector) {
      console.log('[Mobius] Applying tenant detection config:', config);
      patientContextDetector.updatePatterns(config);
    }
  });
  
  console.log('[Mobius] Patient context detector initialized');
}

/**
 * Start patient context detection (called after Mini is rendered).
 */
function startPatientContextDetection(): void {
  if (!patientContextDetector) {
    initPatientContextDetector();
  }
  
  if (patientContextDetector && !patientContextDetector.isActive()) {
    patientContextDetector.start();
    console.log('[Mobius] Patient context detection started');
  }
}

/**
 * Stop patient context detection.
 */
function stopPatientContextDetection(): void {
  if (patientContextDetector) {
    patientContextDetector.stop();
    console.log('[Mobius] Patient context detection stopped');
  }
}

function openPatientModal(onSave: (p: PatientOverride) => void): void {
  const existing = document.getElementById(MINI_IDS.modal);
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = MINI_IDS.modal;
  modal.className = 'mobius-mini-modal-overlay';
  modal.innerHTML = `
    <div class="mobius-mini-modal" role="dialog" aria-modal="true" aria-label="Edit patient">
      <div class="mobius-mini-modal-header">
        <div class="mobius-mini-modal-title">Patient</div>
        <button class="mobius-mini-modal-close" type="button" aria-label="Close">×</button>
      </div>
      <div class="mobius-mini-modal-body">
        <div class="mobius-mini-field">
          <div class="mobius-mini-field-label">Name</div>
          <div class="mobius-mini-search-input">
            <span class="mobius-mini-search-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79L20 21.5 21.5 20 15.5 14zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
            </span>
            <input class="mobius-mini-input mobius-mini-input-with-icon" id="mobius-mini-patient-name" autocomplete="off" />
          </div>
          <div class="mobius-mini-suggestions" data-for="name" aria-label="Name suggestions"></div>
        </div>

        <div class="mobius-mini-field">
          <div class="mobius-mini-field-label">Patient ID</div>
          <div class="mobius-mini-search-input">
            <span class="mobius-mini-search-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79L20 21.5 21.5 20 15.5 14zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
            </span>
            <input class="mobius-mini-input mobius-mini-input-with-icon" id="mobius-mini-patient-id" autocomplete="off" />
          </div>
          <div class="mobius-mini-suggestions" data-for="id" aria-label="ID suggestions"></div>
        </div>

        <div class="mobius-mini-field">
          <div class="mobius-mini-field-label">Date of birth</div>
          <input class="mobius-mini-input" id="mobius-mini-patient-dob" placeholder="YYYY-MM-DD" inputmode="numeric" autocomplete="bday" />
        </div>

        <div class="mobius-mini-field-hint">Start typing to search; select a suggestion to fill both fields.</div>
      </div>
      <div class="mobius-mini-modal-actions">
        <button class="mobius-mini-btn-secondary" type="button" data-action="cancel">Cancel</button>
        <button class="mobius-mini-btn-primary" type="button" data-action="save">Save</button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  const close = () => modal.remove();
  const closeBtn = modal.querySelector<HTMLButtonElement>('.mobius-mini-modal-close');
  closeBtn?.addEventListener('click', close);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) close();
  });

  const { name, id, dob } = getPatientDisplay();
  const nameInput = modal.querySelector<HTMLInputElement>('#mobius-mini-patient-name');
  const idInput = modal.querySelector<HTMLInputElement>('#mobius-mini-patient-id');
  const dobInput = modal.querySelector<HTMLInputElement>('#mobius-mini-patient-dob');
  if (nameInput) nameInput.value = name;
  if (idInput) idInput.value = id;
  if (dobInput) dobInput.value = dob || '';

  const nameSug = modal.querySelector<HTMLElement>('.mobius-mini-suggestions[data-for="name"]');
  const idSug = modal.querySelector<HTMLElement>('.mobius-mini-suggestions[data-for="id"]');

  let activeField: 'name' | 'id' = 'name';
  let currentResults: Array<{ name: string; id: string }> = [];
  let activeIndex = -1;
  let debounceTimer: number | undefined;

  const clearSuggestions = () => {
    currentResults = [];
    activeIndex = -1;
    if (nameSug) nameSug.innerHTML = '';
    if (idSug) idSug.innerHTML = '';
    if (nameSug) nameSug.style.display = 'none';
    if (idSug) idSug.style.display = 'none';
  };

  const renderSuggestions = (target: 'name' | 'id') => {
    const el = target === 'name' ? nameSug : idSug;
    if (!el) return;
    if (currentResults.length === 0) {
      el.innerHTML = '';
      el.style.display = 'none';
      return;
    }
    el.style.display = 'block';
    el.innerHTML = currentResults
      .map((r, idx) => {
        const cls = idx === activeIndex ? 'mobius-mini-suggestion active' : 'mobius-mini-suggestion';
        const safeName = r.name.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const safeId = r.id.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return `<button type="button" class="${cls}" data-idx="${idx}"><span class="name">${safeName}</span><span class="id">ID ${safeId}</span></button>`;
      })
      .join('');

    // Click handler
    el.querySelectorAll<HTMLButtonElement>('.mobius-mini-suggestion').forEach((btn) => {
      btn.addEventListener('click', () => {
        const idx = Number(btn.getAttribute('data-idx') || '-1');
        const chosen = currentResults[idx];
        if (!chosen) return;
        if (nameInput) nameInput.value = chosen.name;
        if (idInput) idInput.value = chosen.id;
        clearSuggestions();
      });
    });
  };

  const setResults = (target: 'name' | 'id', results: Array<{ name: string; id: string }>) => {
    currentResults = results;
    activeIndex = -1;
    // Only show dropdown for the active field
    if (target === 'name') {
      if (idSug) idSug.style.display = 'none';
    } else {
      if (nameSug) nameSug.style.display = 'none';
    }
    renderSuggestions(target);
  };

  const doSearch = (target: 'name' | 'id', q: string) => {
    const query = q.trim();
    if (query.length < 2) {
      clearSuggestions();
      return;
    }
    if (debounceTimer) window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(async () => {
      try {
        const resp = await searchMiniPatients(query, 8);
        setResults(target, Array.isArray(resp.results) ? resp.results : []);
      } catch {
        // silently ignore; keep UI calm
        clearSuggestions();
      }
    }, 180);
  };

  const onKeyDown = (e: KeyboardEvent) => {
    const isOpen = currentResults.length > 0;
    if (!isOpen) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = Math.min(currentResults.length - 1, activeIndex + 1);
      renderSuggestions(activeField);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = Math.max(0, activeIndex - 1);
      renderSuggestions(activeField);
    } else if (e.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < currentResults.length) {
        e.preventDefault();
        const chosen = currentResults[activeIndex];
        if (nameInput) nameInput.value = chosen.name;
        if (idInput) idInput.value = chosen.id;
        clearSuggestions();
      }
    } else if (e.key === 'Escape') {
      clearSuggestions();
    }
  };

  nameInput?.addEventListener('focus', () => {
    activeField = 'name';
  });
  idInput?.addEventListener('focus', () => {
    activeField = 'id';
  });
  nameInput?.addEventListener('input', () => doSearch('name', nameInput.value));
  idInput?.addEventListener('input', () => doSearch('id', idInput.value));
  nameInput?.addEventListener('keydown', onKeyDown);
  idInput?.addEventListener('keydown', onKeyDown);

  // Hide suggestions when clicking outside the modal card
  modal.querySelector('.mobius-mini-modal')?.addEventListener('click', (e) => {
    // allow clicks inside
    e.stopPropagation();
  });
  modal.addEventListener('click', () => clearSuggestions());

  modal.querySelector<HTMLButtonElement>('[data-action="cancel"]')?.addEventListener('click', close);
  modal.querySelector<HTMLButtonElement>('[data-action="save"]')?.addEventListener('click', () => {
    const dobValue = (dobInput?.value || '').trim();
    const next: PatientOverride = {
      name: (nameInput?.value || '').trim() || 'Unknown',
      id: (idInput?.value || '').trim(),
      dob: dobValue,
    };
    onSave(next);
    close();
  });

  nameInput?.focus();
}

function createMini(): HTMLElement {
  const root = document.createElement('div');
  root.id = MINI_IDS.root;
  root.className = 'mobius-mini';

  // Header (drag handle + client logo + divider + Mobius logo + menu)
  const header = document.createElement('div');
  header.className = 'mobius-mini-header';

  const dragHandle = document.createElement('div');
  dragHandle.className = 'mobius-mini-drag-handle';
  dragHandle.title = 'Drag';
  dragHandle.innerHTML = '<div class="mobius-mini-drag-dots"></div>';

  // Client logo (Aspire Health FL for CMHC)
  const clientLogoEl = ClientLogo({ clientName: 'CMHC', compact: true });
  
  // Divider between client and Mobius branding
  const brandDivider = document.createElement('div');
  brandDivider.className = 'mobius-mini-brand-divider';

  const brand = document.createElement('div');
  brand.className = 'mobius-mini-brand';
  brand.appendChild(clientLogoEl);
  brand.appendChild(brandDivider);
  brand.appendChild(MobiusLogo({ status: mobiusStatus }));

  const brandText = document.createElement('div');
  brandText.className = 'mobius-mini-brand-text';
  brandText.textContent = 'Mobius';
  brand.appendChild(brandText);

  const minimizeBtn = document.createElement('button');
  minimizeBtn.className = 'mobius-mini-minimize-btn';
  minimizeBtn.type = 'button';
  minimizeBtn.textContent = '−';
  minimizeBtn.setAttribute('aria-label', 'Minimize');

  // Minimized state info (dot + patient name) - visible only when minimized
  const minimizedInfo = document.createElement('div');
  minimizedInfo.className = 'mobius-mini-minimized-info';
  minimizedInfo.innerHTML = `
    <span class="mobius-mini-dot"></span>
    <span class="mobius-mini-minimized-patient"></span>
  `;

  const expandBtn = document.createElement('button');
  expandBtn.className = 'mobius-mini-expand-btn';
  expandBtn.type = 'button';
  expandBtn.textContent = '›';
  expandBtn.setAttribute('aria-label', 'Expand');

  const menuBtn = document.createElement('button');
  menuBtn.className = 'mobius-mini-menu-btn';
  menuBtn.type = 'button';
  menuBtn.textContent = '⋮';
  menuBtn.setAttribute('aria-label', 'Menu');

  const menu = document.createElement('div');
  menu.className = 'mobius-mini-menu';
  menu.style.cssText = `
    display: none;
    position: fixed;
    background: #fff;
    border: 1px solid rgba(11, 18, 32, 0.12);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(2,6,23,0.15);
    z-index: 2147483647;
    min-width: 120px;
    padding: 4px 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 11px;
    pointer-events: auto;
  `;

  // Store theme state
  let themeSubmenuOpen = false;

  // Helper to apply theme
  const selectTheme = async (themeId: string) => {
    console.log('[Mobius] Applying theme:', themeId);
    applyMiniTheme(root, themeId);
    await saveMiniTheme(themeId);
    menu.style.display = 'none';
    themeSubmenuOpen = false;
  };

  // Build menu HTML with consistent compact styling
  const menuItemStyle = 'padding:6px 12px;cursor:pointer;display:flex;align-items:center;gap:6px;color:#374151;';
  const menuItemHover = 'background:rgba(59,130,246,0.08);';
  
  menu.innerHTML = `
    <div class="mobius-mini-menu-item mobius-mini-theme-trigger" style="${menuItemStyle}">
      Theme <span style="margin-left:auto;font-size:9px;opacity:0.5;">›</span>
    </div>
    <div class="mobius-mini-theme-submenu" style="display:none;border-top:1px solid rgba(11,18,32,0.06);padding:2px 0;margin:0 4px;">
      <div class="mobius-mini-menu-item" data-theme="light" style="${menuItemStyle}font-size:10px;">Light</div>
      <div class="mobius-mini-menu-item" data-theme="dark" style="${menuItemStyle}font-size:10px;">Dark</div>
      <div class="mobius-mini-menu-item" data-theme="blue" style="${menuItemStyle}font-size:10px;">Blue</div>
      <div class="mobius-mini-menu-item" data-theme="glass" style="${menuItemStyle}font-size:10px;">Glass</div>
    </div>
    <div style="height:1px;background:rgba(11,18,32,0.06);margin:2px 8px;"></div>
    <div class="mobius-mini-menu-item danger" style="${menuItemStyle}color:#dc2626;font-size:10px;">Disable on this site</div>
  `;

  const themeSubmenu = menu.querySelector('.mobius-mini-theme-submenu') as HTMLElement;

  // Add click handlers directly to each element
  const themeTriggerEl = menu.querySelector('.mobius-mini-theme-trigger') as HTMLElement;
  console.log('[Mobius] Theme trigger found:', !!themeTriggerEl);
  
  // Theme options count
  const themeOptions = menu.querySelectorAll('[data-theme]');
  console.log('[Mobius] Theme options found:', themeOptions.length);

  // Use mousedown instead of click - fires before any other handlers
  if (themeTriggerEl) {
    themeTriggerEl.onmousedown = (e) => {
      e.stopPropagation();
      e.preventDefault();
      themeSubmenuOpen = !themeSubmenuOpen;
      themeSubmenu.style.display = themeSubmenuOpen ? 'block' : 'none';
      console.log('[Mobius] Theme submenu toggled:', themeSubmenuOpen);
    };
  }

  // Add mousedown handlers to each theme option
  themeOptions.forEach((el) => {
    (el as HTMLElement).onmousedown = async (e) => {
      e.stopPropagation();
      e.preventDefault();
      const theme = (el as HTMLElement).dataset.theme || 'light';
      console.log('[Mobius] Theme option clicked:', theme);
      await selectTheme(theme);
    };
  });

  // Add hover effects to all menu items
  const allMenuItems = menu.querySelectorAll('.mobius-mini-menu-item');
  allMenuItems.forEach((item) => {
    const el = item as HTMLElement;
    el.onmouseenter = () => { el.style.background = 'rgba(59,130,246,0.08)'; };
    el.onmouseleave = () => { el.style.background = 'transparent'; };
  });

  // Disable button
  const disableEl = menu.querySelector('.danger') as HTMLElement;
  if (disableEl) {
    disableEl.onmousedown = async (e) => {
      e.stopPropagation();
      e.preventDefault();
      console.log('[Mobius] Disable clicked');
      menu.style.display = 'none';
      
      // Remove current hostname from allowed domains
      const hostname = getHostname();
      try {
        await setDomainAllowed(hostname, false);
        console.log('[Mobius] Disabled on:', hostname);
        // Remove the Mini widget and menu from page
        removeMini();
        if (document.body.contains(menu)) {
          menu.remove();
        }
      } catch (err) {
        console.error('[Mobius] Failed to disable:', err);
      }
    };
  }

  // Catch-all for debugging
  menu.onmousedown = (e) => {
    console.log('[Mobius] Menu mousedown, target:', (e.target as HTMLElement).className);
  };

  // Menu button click handler - position menu relative to button
  let menuJustOpened = false;
  
  menuBtn.onmousedown = (e) => {
    e.stopPropagation();
    e.preventDefault();
    menuJustOpened = true;
    setTimeout(() => { menuJustOpened = false; }, 150);
    
    const isHidden = menu.style.display === 'none' || menu.style.display === '';
    
    if (isHidden) {
      // Position menu below the button
      const btnRect = menuBtn.getBoundingClientRect();
      menu.style.top = `${btnRect.bottom + 4}px`;
      menu.style.right = `${window.innerWidth - btnRect.right}px`;
      menu.style.left = 'auto';
      menu.style.display = 'block';
      themeSubmenu.style.display = 'none';
      themeSubmenuOpen = false;
      
      // Append to body if not already there
      if (!document.body.contains(menu)) {
        document.body.appendChild(menu);
      }
    } else {
      menu.style.display = 'none';
    }
    console.log('[Mobius] Menu toggled:', menu.style.display);
  };

  // Close menu when clicking outside
  document.addEventListener('mousedown', (e) => {
    // Skip if menu was just opened
    if (menuJustOpened) {
      return;
    }
    // Close if click is outside both the menu and the Mini widget
    if (!menu.contains(e.target as Node) && !root.contains(e.target as Node)) {
      if (menu.style.display !== 'none') {
        console.log('[Mobius] Closing menu - clicked outside');
        menu.style.display = 'none';
        themeSubmenu.style.display = 'none';
        themeSubmenuOpen = false;
      }
    }
  });

  // Note: dragHandle removed for cleaner look - Mini can still be dragged by header
  header.appendChild(minimizedInfo);
  header.appendChild(brand);
  header.appendChild(minimizeBtn);
  header.appendChild(expandBtn);
  header.appendChild(menuBtn);
  // Note: menu is appended to document.body when opened (to escape overflow:hidden)
  root.appendChild(header);

  // Greeting row (User Awareness Sprint)
  const greetingRow = document.createElement('div');
  greetingRow.className = 'mobius-mini-greeting-row';
  greetingRow.style.display = 'none'; // Hidden by default, shown when authenticated
  greetingRow.innerHTML = `
    <button class="mobius-mini-greeting-main" type="button">
      <span class="mobius-mini-greeting-text">Hello</span>
      <svg class="mobius-mini-greeting-chevron" viewBox="0 0 24 24" width="14" height="14">
        <path fill="currentColor" d="M7 10l5 5 5-5z"/>
      </svg>
    </button>
    <button class="mobius-mini-greeting-dismiss" type="button" title="Hide greeting">
      <svg viewBox="0 0 24 24" width="12" height="12">
        <path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
      </svg>
    </button>
  `;
  root.appendChild(greetingRow);

  // User dropdown (shown when clicking greeting)
  let userDropdown: HTMLElement | null = null;
  
  const showUserDropdown = () => {
    if (userDropdown) {
      userDropdown.remove();
      userDropdown = null;
      return;
    }
    
    // Get position of greeting row for fixed dropdown
    const greetingRect = greetingRow.getBoundingClientRect();
    
    userDropdown = document.createElement('div');
    userDropdown.className = 'mobius-mini-user-dropdown';
    userDropdown.style.cssText = `
      position: fixed;
      top: ${greetingRect.bottom + 4}px;
      left: ${greetingRect.left}px;
      width: ${greetingRect.width}px;
      background: white;
      border-radius: 8px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
      z-index: 2147483647;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;
    
    const displayName = currentUserProfile?.display_name || currentUserProfile?.email || 'User';
    const email = currentUserProfile?.email || '';
    const initial = (displayName || '?')[0].toUpperCase();
    
    userDropdown.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;padding:12px;background:#f8fafc;">
        <div style="width:36px;height:36px;border-radius:50%;background:#3b82f6;color:white;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:14px;">${initial}</div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:11px;font-weight:600;color:#0b1220;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${displayName}</div>
          ${email ? `<div style="font-size:9px;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${email}</div>` : ''}
        </div>
      </div>
      <div style="height:1px;background:#e2e8f0;"></div>
      <button class="mobius-mini-dropdown-item" data-action="preferences" style="display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;background:none;border:none;cursor:pointer;font-size:10px;color:#374151;text-align:left;">
        <svg viewBox="0 0 24 24" width="14" height="14" style="color:#64748b;flex-shrink:0;">
          <path fill="currentColor" d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
        </svg>
        <span>My Preferences</span>
      </button>
      <button class="mobius-mini-dropdown-item" data-action="switch" style="display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;background:none;border:none;cursor:pointer;font-size:10px;color:#374151;text-align:left;">
        <svg viewBox="0 0 24 24" width="14" height="14" style="color:#64748b;flex-shrink:0;">
          <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
        </svg>
        <span>Not you? Sign in differently</span>
      </button>
      <div style="height:1px;background:#e2e8f0;"></div>
      <button class="mobius-mini-dropdown-item" data-action="signout" style="display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;background:none;border:none;cursor:pointer;font-size:10px;color:#dc2626;text-align:left;">
        <svg viewBox="0 0 24 24" width="14" height="14" style="color:#dc2626;flex-shrink:0;">
          <path fill="currentColor" d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/>
        </svg>
        <span>Sign out</span>
      </button>
    `;
    
    // Append to document body (fixed position escapes Mini widget overflow)
    document.body.appendChild(userDropdown);
    
    // Wire up dropdown actions
    userDropdown.querySelectorAll('.mobius-mini-dropdown-item').forEach(item => {
      (item as HTMLElement).addEventListener('mouseenter', () => {
        (item as HTMLElement).style.background = '#f8fafc';
      });
      (item as HTMLElement).addEventListener('mouseleave', () => {
        (item as HTMLElement).style.background = 'transparent';
      });
      item.addEventListener('click', async () => {
        const action = (item as HTMLElement).dataset.action;
        if (action === 'signout') {
          const authService = getAuthService();
          await authService.logout();
          isAuthenticated = false;
          currentUserProfile = null;
          currentPersonalization = null;
          await renderMiniIfAllowed();
          showToast('Signed out');
        } else if (action === 'preferences') {
          // Show preferences modal
          openPreferencesModal();
        } else if (action === 'switch') {
          const authService = getAuthService();
          await authService.logout();
          isAuthenticated = false;
          currentUserProfile = null;
          await renderMiniIfAllowed();
        }
        if (userDropdown) {
          userDropdown.remove();
          userDropdown = null;
        }
      });
    });
    
    // Close on outside click
    const closeDropdown = (e: MouseEvent) => {
      if (userDropdown && !userDropdown.contains(e.target as Node) && !greetingRow.contains(e.target as Node)) {
        userDropdown.remove();
        userDropdown = null;
        document.removeEventListener('click', closeDropdown);
      }
    };
    setTimeout(() => document.addEventListener('click', closeDropdown), 0);
  };
  
  // Wire up greeting click
  greetingRow.querySelector('.mobius-mini-greeting-main')?.addEventListener('click', (e) => {
    e.stopPropagation();
    showUserDropdown();
  });
  
  // Wire up dismiss button
  greetingRow.querySelector('.mobius-mini-greeting-dismiss')?.addEventListener('click', (e) => {
    e.stopPropagation();
    greetingDismissed = true;
    greetingRow.style.display = 'none';
  });

  // Open preferences modal
  const openPreferencesModal = async () => {
    // Inject modal styles if not already present
    if (!document.getElementById('mobius-prefs-styles')) {
      const style = document.createElement('style');
      style.id = 'mobius-prefs-styles';
      style.textContent = PREFERENCES_MODAL_STYLES;
      document.head.appendChild(style);
    }
    
    // Build preferences from current user profile and personalization
    // Extract activity codes from user profile or personalization
    const activityCodes = currentUserProfile?.activities || 
      currentPersonalization?.activities?.map(a => a.code) || [];
    
    const currentPrefs: UserPreferences = {
      preferred_name: currentUserProfile?.preferred_name || currentUserProfile?.first_name || '',
      timezone: currentUserProfile?.timezone || 'America/New_York',
      activities: activityCodes,
      tone: (currentUserProfile?.tone as 'professional' | 'friendly' | 'concise') || 'professional',
      greeting_enabled: currentUserProfile?.greeting_enabled !== false,
      autonomy_routine_tasks: (currentUserProfile?.autonomy_routine_tasks as 'automatic' | 'confirm_first' | 'manual') || 'confirm_first',
      autonomy_sensitive_tasks: (currentUserProfile?.autonomy_sensitive_tasks as 'automatic' | 'confirm_first' | 'manual') || 'manual',
    };
    
    // Create and show modal
    const modal = await PreferencesModal({
      preferences: currentPrefs,
      onSave: async (newPrefs) => {
        showToast('Preferences saved!');
        
        // Clear cached user profile to force refresh
        currentUserProfile = null;
        currentPersonalization = null;
        
        // Refresh user profile from backend
        const authService = getAuthService();
        currentUserProfile = await authService.getCurrentUser();
        
        // Refresh Mini to reflect new preferences
        await renderMiniIfAllowed();
        modal.remove();
      },
      onClose: () => {
        modal.remove();
      },
    });
    
    document.body.appendChild(modal);
  };

  // Minimize/restore state
  let isMinimized = false;
  const contentElements: HTMLElement[] = []; // Will store refs to hide/show
  
  minimizeBtn.onclick = (e) => {
    e.stopPropagation();
    isMinimized = !isMinimized;
    
    if (isMinimized) {
      // Minimize: hide all content except header, shrink widget
      root.classList.add('mobius-mini-minimized');
      minimizeBtn.textContent = '+';
      minimizeBtn.setAttribute('aria-label', 'Restore');
    } else {
      // Restore: show all content
      root.classList.remove('mobius-mini-minimized');
      minimizeBtn.textContent = '−';
      minimizeBtn.setAttribute('aria-label', 'Minimize');
    }
  };

  // Patient
  const patientRow = document.createElement('div');
  patientRow.className = 'mobius-mini-row';
  patientRow.innerHTML = `
    <div class="mobius-mini-row-label">Patient</div>
    <div class="mobius-mini-row-body">
      <div class="mobius-mini-patient-name"></div>
      <div class="mobius-mini-patient-id"></div>
      <div class="mobius-mini-patient-dob"></div>
    </div>
    <button class="mobius-mini-icon-btn" type="button" aria-label="Edit patient" title="Edit patient">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm2.92 2.83H5v-.92l9.06-9.06.92.92L5.92 20.08zM20.71 7.04a1.003 1.003 0 0 0 0-1.42l-2.34-2.34a1.003 1.003 0 0 0-1.42 0l-1.83 1.83 3.75 3.75 1.84-1.82z"/>
      </svg>
    </button>
  `;
  root.appendChild(patientRow);

  // Needs Attention (replaces Proceed)
  const attentionRow = document.createElement('div');
  attentionRow.className = 'mobius-mini-row mobius-mini-attention-row';
  attentionRow.innerHTML = `
    <div class="mobius-mini-row-label">Needs<br>Attention</div>
    <div class="mobius-mini-attention-content">
      <span class="mobius-mini-dot"></span>
      <span class="mobius-mini-problem-text"></span>
      <button class="mobius-mini-status-badge" type="button" aria-label="Status">
        <span class="mobius-mini-badge-text">Set status</span>
        <span class="mobius-mini-dropdown-icon">▼</span>
      </button>
    </div>
  `;
  root.appendChild(attentionRow);

  // Task badge row (simplified - just shows count and opens sidecar)
  const taskBadgeRow = document.createElement('div');
  taskBadgeRow.className = 'mobius-mini-row mobius-mini-task-badge-row';
  taskBadgeRow.style.display = 'none'; // Hidden when no tasks
  taskBadgeRow.innerHTML = `
    <div class="mobius-mini-row-label">Tasks</div>
    <button class="mobius-mini-task-badge" type="button" aria-label="Open tasks in Sidecar">
      <span class="mobius-mini-task-count">0</span>
      <span>pending → Open Sidecar</span>
    </button>
  `;
  root.appendChild(taskBadgeRow);

  // Legacy rows for backwards compatibility (hidden)
  const proceedRow = document.createElement('div');
  proceedRow.className = 'mobius-mini-row';
  proceedRow.style.display = 'none';
  const taskingRow = document.createElement('div');
  taskingRow.className = 'mobius-mini-row';
  taskingRow.style.display = 'none';

  // Note + send icon
  const noteRow = document.createElement('div');
  noteRow.className = 'mobius-mini-row';
  noteRow.innerHTML = `
    <div class="mobius-mini-row-label">Note</div>
    <div class="mobius-mini-note-wrap">
      <input class="mobius-mini-note-input" type="text" placeholder="Quick note…" />
      <button class="mobius-mini-send-btn" type="button" aria-label="Send note">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>
      </button>
    </div>
  `;
  root.appendChild(noteRow);

  // Wire up patient row content and actions
  const renderPatient = () => {
    const p = getPatientDisplay();
    const nameEl = root.querySelector<HTMLElement>('.mobius-mini-patient-name');
    const idEl = root.querySelector<HTMLElement>('.mobius-mini-patient-id');
    const dobEl = root.querySelector<HTMLElement>('.mobius-mini-patient-dob');
    if (nameEl) nameEl.textContent = p.name || 'Unknown';
    if (idEl) idEl.textContent = p.id ? `ID ${p.id}` : '';
    if (dobEl) dobEl.textContent = p.dob ? `DOB ${p.dob}` : '';
    // Also update minimized info patient name
    const minimizedName = minimizedInfo.querySelector<HTMLElement>('.mobius-mini-minimized-patient');
    if (minimizedName) minimizedName.textContent = p.name || 'Unknown';
  };
  renderPatient();

  // Wire up statuses
  const applyStatus = (rowEl: HTMLElement, line: MiniLine, showMode = false) => {
    const dot = rowEl.querySelector<HTMLElement>('.mobius-mini-dot');
    const text = rowEl.querySelector<HTMLElement>('.mobius-mini-status-text');
    if (dot) {
      dot.className = `mobius-mini-dot ${colorToCssClass(line.color)}`;
    }
    if (text) {
      if (showMode && line.mode) {
        const icon = getModeIcon(line.mode);
        const modeText = line.mode_text || '';
        text.textContent = `${icon} ${modeText}`;
      } else {
        text.textContent = line.text;
      }
    }
  };

  // Apply attention status (new UI)
  const applyAttention = () => {
    const dot = attentionRow.querySelector<HTMLElement>('.mobius-mini-dot');
    const problemText = attentionRow.querySelector<HTMLElement>('.mobius-mini-problem-text');
    const badgeText = attentionRow.querySelector<HTMLElement>('.mobius-mini-badge-text');
    const badge = attentionRow.querySelector<HTMLElement>('.mobius-mini-status-badge');
    
    // Calculate effective color based on status
    let effectiveColor = needsAttention.color;
    if (needsAttention.userStatus === 'resolved') effectiveColor = 'green';
    else if (needsAttention.userStatus === 'confirmed_unresolved') effectiveColor = 'yellow';
    else if (needsAttention.userStatus === 'unable_to_confirm') effectiveColor = 'grey';
    
    // Dot color reflects status
    if (dot) {
      dot.className = `mobius-mini-dot ${colorToCssClass(effectiveColor)}`;
    }
    
    // Also update minimized info dot
    const minimizedDot = minimizedInfo.querySelector<HTMLElement>('.mobius-mini-dot');
    if (minimizedDot) {
      minimizedDot.className = `mobius-mini-dot ${colorToCssClass(effectiveColor)}`;
    }
    
    // Problem statement always visible
    if (problemText) {
      problemText.textContent = needsAttention.problemStatement || 'No issues detected';
    }
    
    // Status badge shows current status
    if (badgeText && badge) {
      if (needsAttention.userStatus === 'resolved') {
        badgeText.textContent = 'Resolved';
        badge.className = 'mobius-mini-status-badge status-resolved';
      } else if (needsAttention.userStatus === 'confirmed_unresolved') {
        badgeText.textContent = 'Unresolved';
        badge.className = 'mobius-mini-status-badge status-unresolved';
      } else if (needsAttention.userStatus === 'unable_to_confirm') {
        badgeText.textContent = 'Unconfirmed';
        badge.className = 'mobius-mini-status-badge status-unconfirmed';
      } else {
        badgeText.textContent = 'Set status';
        badge.className = 'mobius-mini-status-badge';
      }
    }
  };

  // Apply task count
  const applyTaskCount = () => {
    const countEl = taskBadgeRow.querySelector<HTMLElement>('.mobius-mini-task-count');
    if (countEl) countEl.textContent = String(taskCount);
    taskBadgeRow.style.display = taskCount > 0 ? '' : 'none';
  };

  // Update minimized state info (dot + patient name)
  const updateMinimizedInfo = () => {
    const dot = minimizedInfo.querySelector<HTMLElement>('.mobius-mini-dot');
    const name = minimizedInfo.querySelector<HTMLElement>('.mobius-mini-minimized-patient');
    
    // Patient name
    const p = getPatientDisplay();
    if (name) name.textContent = p.name || 'Unknown';
    
    // Attention dot color
    if (dot) {
      let color = needsAttention.color;
      if (needsAttention.userStatus === 'resolved') color = 'green';
      else if (needsAttention.userStatus === 'confirmed_unresolved') color = 'yellow';
      else if (needsAttention.userStatus === 'unable_to_confirm') color = 'grey';
      dot.className = `mobius-mini-dot ${colorToCssClass(color)}`;
    }
  };

  applyAttention();
  applyTaskCount();
  updateMinimizedInfo();
  
  // Legacy (hidden)
  applyStatus(proceedRow, miniProceed);
  applyStatus(taskingRow, miniTasking, true);

  // Attention workflow dropdown options
  const ATTENTION_OPTIONS: Array<{ status: AttentionStatus | 'new_issue'; label: string; icon: string; description: string }> = [
    { status: 'resolved', label: 'Resolved', icon: '✓', description: 'Problem fixed, no further action' },
    { status: 'confirmed_unresolved', label: 'Confirmed, unresolved', icon: '⚠', description: 'Issue verified, tasks remain' },
    { status: 'unable_to_confirm', label: 'Unable to confirm', icon: '?', description: 'Needs investigation' },
  ];

  // Create issue report modal
  const createIssueModal = (onSubmit: (issueText: string) => void): HTMLElement => {
    const overlay = document.createElement('div');
    overlay.className = 'mobius-mini-modal-overlay';
    overlay.style.cssText = `
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.3);
      z-index: 2147483647;
      display: flex;
      align-items: center;
      justify-content: center;
    `;

    const modal = document.createElement('div');
    modal.className = 'mobius-mini-issue-modal';
    modal.style.cssText = `
      background: white;
      border-radius: 8px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.2);
      width: 280px;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;

    modal.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid #e2e8f0;">
        <span style="font-size:11px;font-weight:600;color:#0b1220;">Report Issue</span>
        <button type="button" class="modal-close" style="background:none;border:none;cursor:pointer;font-size:16px;color:#64748b;padding:0;line-height:1;">&times;</button>
      </div>
      <div style="padding:12px;">
        <input type="text" class="issue-input" placeholder="Describe the issue..." style="
          width:100%;
          box-sizing:border-box;
          padding:8px 10px;
          border:1px solid #e2e8f0;
          border-radius:6px;
          font-size:10px;
          outline:none;
        " />
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end;padding:0 12px 12px;">
        <button type="button" class="modal-cancel" style="
          padding:6px 12px;
          border:1px solid #e2e8f0;
          border-radius:6px;
          background:white;
          font-size:10px;
          cursor:pointer;
        ">Cancel</button>
        <button type="button" class="modal-submit" style="
          padding:6px 12px;
          border:none;
          border-radius:6px;
          background:#2563eb;
          color:white;
          font-size:10px;
          font-weight:500;
          cursor:pointer;
        ">Submit</button>
      </div>
    `;

    overlay.appendChild(modal);

    const input = modal.querySelector<HTMLInputElement>('.issue-input')!;
    const closeBtn = modal.querySelector('.modal-close')!;
    const cancelBtn = modal.querySelector('.modal-cancel')!;
    const submitBtn = modal.querySelector('.modal-submit')!;

    const close = () => overlay.remove();

    closeBtn.addEventListener('click', close);
    cancelBtn.addEventListener('click', close);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close();
    });

    submitBtn.addEventListener('click', () => {
      const text = input.value.trim();
      if (text) {
        onSubmit(text);
        close();
      }
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const text = input.value.trim();
        if (text) {
          onSubmit(text);
          close();
        }
      }
      if (e.key === 'Escape') close();
    });

    // Focus input after append
    setTimeout(() => input.focus(), 50);

    return overlay;
  };

  const createAttentionDropdown = (
    currentStatus: AttentionStatus,
    onSelect: (status: AttentionStatus) => void,
    onReportIssue: () => void,
    anchorRect: DOMRect
  ): HTMLElement => {
    const dropdown = document.createElement('div');
    dropdown.className = 'mobius-mini-status-dropdown mobius-mini-attention-dropdown';
    // Position above the button using fixed positioning (escapes overflow:hidden)
    const dropdownHeight = 150; // approximate height for 3 options + separator + new issue
    dropdown.style.cssText = `
      position: fixed;
      top: ${anchorRect.top - dropdownHeight - 4}px;
      left: ${anchorRect.left}px;
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.18);
      z-index: 2147483647;
      min-width: 200px;
      padding: 4px 0;
    `;

    // Add status options
    ATTENTION_OPTIONS.forEach((opt) => {
      const isSelected = opt.status === currentStatus;
      const item = document.createElement('button');
      item.type = 'button';
      item.style.cssText = `
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 1px;
        width: 100%;
        padding: 6px 8px;
        border: none;
        background: ${isSelected ? '#f1f5f9' : 'transparent'};
        cursor: pointer;
        text-align: left;
      `;
      item.innerHTML = `
        <div style="display:flex;align-items:center;gap:6px;font-size:10px;font-weight:500;">
          <span>${opt.icon}</span>
          <span>${opt.label}</span>
        </div>
        <div style="font-size:8px;color:#64748b;padding-left:16px;">${opt.description}</div>
      `;
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        onSelect(opt.status as AttentionStatus);
        dropdown.remove();
      });
      item.addEventListener('mouseenter', () => {
        item.style.background = '#f1f5f9';
      });
      item.addEventListener('mouseleave', () => {
        item.style.background = isSelected ? '#f1f5f9' : 'transparent';
      });
      dropdown.appendChild(item);
    });

    // Add separator
    const separator = document.createElement('div');
    separator.style.cssText = `
      height: 1px;
      background: #e2e8f0;
      margin: 4px 8px;
    `;
    dropdown.appendChild(separator);

    // Add "Report new issue" option
    const reportItem = document.createElement('button');
    reportItem.type = 'button';
    reportItem.style.cssText = `
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 1px;
      width: 100%;
      padding: 6px 8px;
      border: none;
      background: transparent;
      cursor: pointer;
      text-align: left;
    `;
    reportItem.innerHTML = `
      <div style="display:flex;align-items:center;gap:6px;font-size:10px;font-weight:500;color:#2563eb;">
        <span>+</span>
        <span>Report new issue</span>
      </div>
      <div style="font-size:8px;color:#64748b;padding-left:16px;">Add a new problem</div>
    `;
    reportItem.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.remove();
      onReportIssue();
    });
    reportItem.addEventListener('mouseenter', () => {
      reportItem.style.background = '#eff6ff';
    });
    reportItem.addEventListener('mouseleave', () => {
      reportItem.style.background = 'transparent';
    });
    dropdown.appendChild(reportItem);

    return dropdown;
  };

  // Click handler for Attention status badge
  const statusBadge = attentionRow.querySelector<HTMLButtonElement>('.mobius-mini-status-badge');
  statusBadge?.addEventListener('click', async (e) => {
    e.stopPropagation();
    // Remove any existing dropdown
    document.querySelectorAll('.mobius-mini-status-dropdown').forEach(d => d.remove());
    
    // Get button position to anchor dropdown
    const btnRect = statusBadge.getBoundingClientRect();
    
    const dropdown = createAttentionDropdown(
      needsAttention.userStatus,
      // onSelect callback for status changes
      async (status) => {
        // Update local state
        needsAttention.userStatus = status;
        applyAttention();
        
        // Submit to backend
        const patientId = getPatientDisplay().id;
        if (patientId) {
          try {
            const response = await submitAttentionStatus(sessionId, patientId, status);
            showToast(status === 'resolved' ? 'Marked as resolved' : 'Status updated');
            
            // Open sidecar if indicated
            if (response.open_sidecar) {
              // Expand to full sidebar
              await expandToSidebar();
            }
          } catch (err) {
            console.error('[Mobius] Failed to update attention status:', err);
            showToast('Failed to update status');
          }
        }
      },
      // onReportIssue callback
      () => {
        const modal = createIssueModal(async (issueText) => {
          const patientId = getPatientDisplay().id;
          if (patientId) {
            try {
              await reportIssue(sessionId, patientId, issueText);
              showToast('Issue reported');
            } catch (err) {
              console.error('[Mobius] Failed to report issue:', err);
              showToast('Failed to report issue');
            }
          }
        });
        document.body.appendChild(modal);
      },
      btnRect
    );
    
    // Append to body to escape overflow:hidden on Mini widget
    document.body.appendChild(dropdown);
  });

  // Click handler for task badge (opens sidecar)
  const taskBadge = taskBadgeRow.querySelector<HTMLButtonElement>('.mobius-mini-task-badge');
  taskBadge?.addEventListener('click', async () => {
    // Open sidecar - expand to full sidebar
    await expandToSidebar();
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', () => {
    document.querySelectorAll('.mobius-mini-status-dropdown').forEach(d => d.remove());
  });

  // Legacy: Track overrides (kept for backwards compatibility)
  let proceedOverride: MiniColor | null = null;
  let taskingOverride: MiniColor | null = null;

  const savePatient = async (p: PatientOverride) => {
    patientOverride = p;
    await storageSet({ [STORAGE_KEYS.patientOverride]: p });
    renderPatient();
    
    // Fetch new status for the selected patient
    if (p.id) {
      try {
        const status = await fetchMiniStatus(sessionId, p.id);
        
        // Update legacy proceed/tasking (hidden)
        miniProceed = status.proceed;
        if (status.tasking) {
          miniTasking = status.tasking;
        }
        applyStatus(proceedRow, miniProceed);
        applyStatus(taskingRow, miniTasking, true);
        
        // Update needs_attention (new UI)
        if (status.needs_attention) {
          needsAttention = {
            color: status.needs_attention.color,
            problemStatement: status.needs_attention.problem_statement,
            userStatus: status.needs_attention.user_status,
          };
        } else {
          // Fallback to proceed data
          needsAttention = {
            color: status.proceed.color,
            problemStatement: status.proceed.text,
            userStatus: null,
          };
        }
        applyAttention();
        
        // Update task count
        taskCount = status.task_count || 0;
        applyTaskCount();
      } catch (err) {
        console.error('[Mobius] Failed to fetch status for patient:', err);
      }
    }
  };

  patientRow.querySelector<HTMLButtonElement>('.mobius-mini-icon-btn')?.addEventListener('click', () => {
    openPatientModal((p) => void savePatient(p));
  });

  // Note send
  const noteInput = root.querySelector<HTMLInputElement>('.mobius-mini-note-input');
  const sendBtn = root.querySelector<HTMLButtonElement>('.mobius-mini-send-btn');
  const doSend = async () => {
    const note = (noteInput?.value || '').trim();
    if (!note) return;
    try {
      await submitMiniNote(sessionId, note, getPatientDisplay());
      if (noteInput) noteInput.value = '';
      showToast('Note sent');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to send';
      showToast(msg);
    }
  };
  sendBtn?.addEventListener('click', () => void doSend());
  noteInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      void doSend();
    }
  });

  // Expand + disable site
  const doExpand = async () => {
    menu.style.display = 'none';
    await expandToSidebar();
  };
  expandBtn.addEventListener('click', () => void doExpand());

  menu.querySelector<HTMLButtonElement>('[data-action="disable-site"]')?.addEventListener('click', () => {
    menu.style.display = 'none';
    const host = getHostname();
    void (async () => {
      await setDomainAllowed(host, false);
      removeMini();
      removeSidebar();
      showToast('Disabled on this site');
    })();
  });

  // Draggable positioning (only via dragHandle)
  let dragging = false;
  let start = { x: 0, y: 0, left: 0, top: 0 };

  const startDrag = (e: PointerEvent) => {
    dragging = true;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    const rect = root.getBoundingClientRect();
    start = { x: e.clientX, y: e.clientY, left: rect.left, top: rect.top };
    e.preventDefault();
  };
  const moveDrag = (e: PointerEvent) => {
    if (!dragging) return;
    const dx = e.clientX - start.x;
    const dy = e.clientY - start.y;
    root.style.left = `${start.left + dx}px`;
    root.style.top = `${start.top + dy}px`;
  };
  const endDrag = () => {
    if (!dragging) return;
    dragging = false;
    const rect = root.getBoundingClientRect();
    void setMiniPos(root, { x: rect.left, y: rect.top });
  };

  // Make dragging easy: allow dragging from the whole header,
  // but ignore interactions on buttons/inputs.
  const canStartDrag = (target: EventTarget | null) => {
    const el = target as HTMLElement | null;
    if (!el) return false;
    return !el.closest('button') && !el.closest('input') && !el.closest('select') && !el.closest('textarea');
  };

  header.addEventListener('pointerdown', (e) => {
    if (!canStartDrag(e.target)) return;
    startDrag(e);
  });
  header.addEventListener('pointermove', moveDrag);
  header.addEventListener('pointerup', endDrag);

  // Also allow dragging via the grip specifically.
  dragHandle.addEventListener('pointerdown', startDrag);
  dragHandle.addEventListener('pointermove', moveDrag);
  dragHandle.addEventListener('pointerup', endDrag);

  window.addEventListener('resize', () => {
    const rect = root.getBoundingClientRect();
    void setMiniPos(root, { x: rect.left, y: rect.top });
  });

  return root;
}

async function expandToSidebar(): Promise<void> {
  console.log('[Mobius OS] Expanding to sidebar...');
  const mini = document.getElementById(MINI_IDS.root) as HTMLElement | null;
  if (mini) {
    const rect = mini.getBoundingClientRect();
    miniLastPos = { x: rect.left, y: rect.top };
    await storageSet({ [STORAGE_KEYS.miniPos]: miniLastPos });
    mini.style.display = 'none';
  }
  await initSidebar();
}

async function collapseToMini(): Promise<void> {
  removeSidebar();
  await renderMiniIfAllowed();
}

async function renderMiniIfAllowed(): Promise<void> {
  await loadMiniPersistedState();
  const host = getHostname();
  const allowed = await isDomainAllowed(host);
  if (!allowed) {
    removeMini();
    return;
  }

  if (!sessionId) sessionId = await getOrCreateSessionId();

  // Check authentication state
  const authService = getAuthService();
  isAuthenticated = await authService.isAuthenticated();
  
  if (isAuthenticated) {
    currentUserProfile = await authService.getUserProfile();
  }

  // Create mini if needed
  let mini = document.getElementById(MINI_IDS.root) as HTMLElement | null;
  if (!mini) {
    mini = createMini();
    document.body.appendChild(mini);
    const initial = miniLastPos || { x: 14, y: 14 };
    await setMiniPos(mini, initial);
    
    // Apply saved theme
    const savedTheme = await loadMiniTheme();
    applyMiniTheme(mini, savedTheme);
  } else {
    // Ensure it's visible after collapsing from the full sidebar.
    mini.style.display = '';
  }

  // Handle locked state for unauthenticated users
  const greetingRow = mini.querySelector<HTMLElement>('.mobius-mini-greeting-row');
  const patientRow = mini.querySelector<HTMLElement>('.mobius-mini-row');
  const attentionRow = mini.querySelector<HTMLElement>('.mobius-mini-attention-row');
  const taskBadgeRow = mini.querySelector<HTMLElement>('.mobius-mini-task-badge-row');
  const noteRow = mini.querySelectorAll<HTMLElement>('.mobius-mini-row')[3]; // note row
  
  // Get or create locked overlay
  let lockedOverlay = mini.querySelector<HTMLElement>('.mobius-mini-locked-overlay');
  
  // =========================================================================
  // Account Creation & Onboarding Flow (scoped to have access to lockedOverlay)
  // =========================================================================
  
  const API_BASE_AUTH = 'http://localhost:5001';
  
  // Fetch available activities from backend
  const fetchActivities = async (): Promise<Array<{activity_code: string; label: string; description?: string}>> => {
    try {
      const response = await fetch(`${API_BASE_AUTH}/api/v1/auth/activities`);
      const data = await response.json();
      if (data.ok && data.activities) {
        return data.activities;
      }
    } catch (err) {
      console.error('[Mobius] Failed to fetch activities:', err);
    }
    // Fallback activities if backend fails
    return [
      { activity_code: 'verify_eligibility', label: 'Verify Insurance Eligibility' },
      { activity_code: 'check_in_patients', label: 'Check In Patients' },
      { activity_code: 'schedule_appointments', label: 'Schedule Appointments' },
      { activity_code: 'submit_claims', label: 'Submit Claims' },
      { activity_code: 'rework_claims', label: 'Rework Denied Claims' },
      { activity_code: 'prior_auth', label: 'Prior Authorizations' },
      { activity_code: 'patient_collections', label: 'Patient Collections' },
      { activity_code: 'post_payments', label: 'Post Payments' },
    ];
  };
  
  // Show onboarding form (Step 2 of account creation)
  const showOnboardingForm = async (firstName: string, accessToken: string) => {
    if (!lockedOverlay) return;
    
    // Fetch available activities
    const activities = await fetchActivities();
    
    // Update locked overlay to be a flex container for proper scrolling
    lockedOverlay.style.cssText = `
      display: flex;
      flex-direction: column;
      height: 100%;
      max-height: 500px;
      padding: 12px;
      background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.98));
      overflow: hidden;
    `;
    
    lockedOverlay.innerHTML = `
      <div style="text-align: center; margin-bottom: 10px; flex-shrink: 0;">
        <div style="font-size: 16px; margin-bottom: 4px;">👋</div>
        <div style="font-size: 11px; font-weight: 600; color: #0b1220;">Welcome, ${firstName}!</div>
        <div style="font-size: 9px; color: #64748b; margin-top: 2px;">Step 2 of 2 - Your preferences</div>
      </div>
      
      <div class="mobius-mini-onboarding-form" style="flex: 1; overflow-y: auto; padding-right: 4px; min-height: 0;">
        <!-- Preferred Name -->
        <div style="margin-bottom: 10px;">
          <label style="font-size: 9px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;">What should we call you?</label>
          <input type="text" class="mobius-mini-onb-name" placeholder="${firstName}" value="${firstName}" style="
            width: 100%;
            box-sizing: border-box;
            padding: 6px 8px;
            border: 1px solid rgba(11, 18, 32, 0.15);
            border-radius: 6px;
            font-size: 10px;
            outline: none;
          " />
        </div>
        
        <!-- Activities -->
        <div style="margin-bottom: 10px;">
          <label style="font-size: 9px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;">What do you do? (select all that apply)</label>
          <div class="mobius-mini-onb-activities" style="display: flex; flex-wrap: wrap; gap: 4px;">
            ${activities.map((a: {activity_code: string; label: string}) => `
              <label style="display: flex; align-items: center; gap: 4px; padding: 4px 8px; background: #f8fafc; border-radius: 12px; cursor: pointer; font-size: 9px; color: #374151; border: 1px solid transparent; transition: all 0.15s;">
                <input type="checkbox" value="${a.activity_code}" style="width: 12px; height: 12px; margin: 0;" />
                <span>${a.label}</span>
              </label>
            `).join('')}
          </div>
        </div>
        
        <!-- AI Experience -->
        <div style="margin-bottom: 10px;">
          <label style="font-size: 9px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;">How familiar are you with AI tools?</label>
          <div class="mobius-mini-onb-experience" style="display: flex; flex-direction: column; gap: 4px;">
            <label style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px;">
              <input type="radio" name="ai_exp" value="beginner" style="margin: 0;" />
              <span><strong>New to AI</strong> - I haven't used ChatGPT or similar tools</span>
            </label>
            <label style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px;">
              <input type="radio" name="ai_exp" value="regular" checked style="margin: 0;" />
              <span><strong>Regular user</strong> - I've used AI tools for work or personal use</span>
            </label>
            <label style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px;">
              <input type="radio" name="ai_exp" value="power_user" style="margin: 0;" />
              <span><strong>Power user</strong> - I use AI daily and understand its capabilities</span>
            </label>
          </div>
        </div>
        
        <!-- Autonomy - Routine Tasks -->
        <div style="margin-bottom: 10px;">
          <label style="font-size: 9px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;">For routine tasks (like sending reminders), should Mobius:</label>
          <div class="mobius-mini-onb-routine" style="display: flex; flex-direction: column; gap: 4px;">
            <label style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px;">
              <input type="radio" name="routine" value="automatic" style="margin: 0;" />
              <span><strong>Act automatically</strong> - Just do it and let me know</span>
            </label>
            <label style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px;">
              <input type="radio" name="routine" value="confirm_first" checked style="margin: 0;" />
              <span><strong>Ask first</strong> - Show me what you'll do before doing it</span>
            </label>
            <label style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px;">
              <input type="radio" name="routine" value="manual" style="margin: 0;" />
              <span><strong>I'll do it</strong> - Just guide me, I'll take action myself</span>
            </label>
          </div>
        </div>
        
        <!-- Autonomy - Sensitive Tasks -->
        <div style="margin-bottom: 10px;">
          <label style="font-size: 9px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;">For sensitive tasks (like submitting claims), should Mobius:</label>
          <div class="mobius-mini-onb-sensitive" style="display: flex; flex-direction: column; gap: 4px;">
            <label style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px;">
              <input type="radio" name="sensitive" value="confirm_first" style="margin: 0;" />
              <span><strong>Ask first</strong> - Always confirm before taking action</span>
            </label>
            <label style="display: flex; align-items: center; gap: 6px; padding: 6px 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px;">
              <input type="radio" name="sensitive" value="manual" checked style="margin: 0;" />
              <span><strong>I'll do it</strong> - Just prepare it, I'll submit myself</span>
            </label>
          </div>
        </div>
        
        <!-- Communication Style -->
        <div style="margin-bottom: 12px;">
          <label style="font-size: 9px; font-weight: 500; color: #374151; display: block; margin-bottom: 4px;">How should Mobius communicate with you?</label>
          <div class="mobius-mini-onb-tone" style="display: flex; gap: 6px;">
            <label style="flex: 1; display: flex; flex-direction: column; align-items: center; padding: 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px; border: 2px solid transparent;" class="tone-option" data-tone="professional">
              <input type="radio" name="tone" value="professional" checked style="margin: 0 0 4px 0;" />
              <span style="font-weight: 500;">Professional</span>
              <span style="color: #64748b; font-size: 8px;">Clear & formal</span>
            </label>
            <label style="flex: 1; display: flex; flex-direction: column; align-items: center; padding: 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px; border: 2px solid transparent;" class="tone-option" data-tone="friendly">
              <input type="radio" name="tone" value="friendly" style="margin: 0 0 4px 0;" />
              <span style="font-weight: 500;">Friendly</span>
              <span style="color: #64748b; font-size: 8px;">Warm & helpful</span>
            </label>
            <label style="flex: 1; display: flex; flex-direction: column; align-items: center; padding: 8px; background: #f8fafc; border-radius: 6px; cursor: pointer; font-size: 9px; border: 2px solid transparent;" class="tone-option" data-tone="concise">
              <input type="radio" name="tone" value="concise" style="margin: 0 0 4px 0;" />
              <span style="font-weight: 500;">Concise</span>
              <span style="color: #64748b; font-size: 8px;">Brief & direct</span>
            </label>
          </div>
        </div>
      </div>
      
      <div style="flex-shrink: 0; padding-top: 8px;">
        <button class="mobius-mini-onb-submit" style="
          width: 100%;
          padding: 10px 12px;
          background: #2563eb;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 10px;
          font-weight: 500;
          cursor: pointer;
        ">Get Started</button>
        <div class="mobius-mini-onb-error" style="
          font-size: 9px;
          color: #dc2626;
          margin-top: 6px;
          display: none;
        "></div>
        <div style="text-align: center; font-size: 8px; color: #94a3b8; margin-top: 6px;">
          You can change these anytime in preferences
        </div>
      </div>
    `;
    
    // Wire up form interactions
    const nameInput = lockedOverlay.querySelector<HTMLInputElement>('.mobius-mini-onb-name');
    const submitBtn = lockedOverlay.querySelector<HTMLButtonElement>('.mobius-mini-onb-submit');
    const errorDiv = lockedOverlay.querySelector<HTMLElement>('.mobius-mini-onb-error');
    
    // Highlight selected tone
    lockedOverlay.querySelectorAll('.tone-option').forEach((opt: Element) => {
      const radio = opt.querySelector('input[type="radio"]') as HTMLInputElement;
      if (radio?.checked) {
        (opt as HTMLElement).style.borderColor = '#2563eb';
        (opt as HTMLElement).style.background = '#eff6ff';
      }
      opt.addEventListener('click', () => {
        lockedOverlay!.querySelectorAll('.tone-option').forEach((o: Element) => {
          (o as HTMLElement).style.borderColor = 'transparent';
          (o as HTMLElement).style.background = '#f8fafc';
        });
        (opt as HTMLElement).style.borderColor = '#2563eb';
        (opt as HTMLElement).style.background = '#eff6ff';
      });
    });
    
    // Highlight checked activity checkboxes
    lockedOverlay.querySelectorAll('.mobius-mini-onb-activities input[type="checkbox"]').forEach((cb: Element) => {
      cb.addEventListener('change', () => {
        const label = cb.closest('label') as HTMLElement;
        if ((cb as HTMLInputElement).checked) {
          label.style.borderColor = '#2563eb';
          label.style.background = '#eff6ff';
        } else {
          label.style.borderColor = 'transparent';
          label.style.background = '#f8fafc';
        }
      });
    });
    
    const doOnboarding = async () => {
      const preferredName = nameInput?.value.trim() || firstName;
      
      // Gather selected activities
      const selectedActivities: string[] = [];
      lockedOverlay!.querySelectorAll('.mobius-mini-onb-activities input[type="checkbox"]:checked').forEach((cb: Element) => {
        selectedActivities.push((cb as HTMLInputElement).value);
      });
      
      // Get AI experience level
      const aiExp = (lockedOverlay!.querySelector('input[name="ai_exp"]:checked') as HTMLInputElement)?.value || 'regular';
      
      // Get autonomy preferences
      const routineAutonomy = (lockedOverlay!.querySelector('input[name="routine"]:checked') as HTMLInputElement)?.value || 'confirm_first';
      const sensitiveAutonomy = (lockedOverlay!.querySelector('input[name="sensitive"]:checked') as HTMLInputElement)?.value || 'manual';
      
      // Get tone preference
      const tone = (lockedOverlay!.querySelector('input[name="tone"]:checked') as HTMLInputElement)?.value || 'professional';
      
      if (submitBtn) {
        submitBtn.textContent = 'Setting up...';
        submitBtn.disabled = true;
      }
      
      try {
        const response = await fetch(`${API_BASE_AUTH}/api/v1/auth/onboarding`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            preferred_name: preferredName,
            activities: selectedActivities,
            ai_experience_level: aiExp,
            autonomy_routine_tasks: routineAutonomy,
            autonomy_sensitive_tasks: sensitiveAutonomy,
            tone,
            greeting_enabled: true,
          }),
        });
        
        const data = await response.json();
        
        if (data.ok) {
          showToast(`Welcome to Mobius, ${preferredName}!`);
          
          // Refresh user profile and re-render Mini
          const authService = getAuthService();
          currentUserProfile = await authService.getCurrentUser();
          isAuthenticated = true;
          
          await renderMiniIfAllowed();
        } else {
          if (errorDiv) {
            errorDiv.textContent = data.error || 'Failed to save preferences';
            errorDiv.style.display = 'block';
          }
          if (submitBtn) {
            submitBtn.textContent = 'Get Started';
            submitBtn.disabled = false;
          }
        }
      } catch (err) {
        if (errorDiv) {
          errorDiv.textContent = 'Connection error. Please try again.';
          errorDiv.style.display = 'block';
        }
        if (submitBtn) {
          submitBtn.textContent = 'Get Started';
          submitBtn.disabled = false;
        }
      }
    };
    
    submitBtn?.addEventListener('click', () => void doOnboarding());
  };
  
  // Show registration form (Step 1 of account creation)
  const showRegistrationForm = () => {
    if (!lockedOverlay) {
      // Create lockedOverlay if it doesn't exist
      lockedOverlay = document.createElement('div');
      lockedOverlay.className = 'mobius-mini-locked-overlay';
      lockedOverlay.style.cssText = `
        padding: 12px;
        background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.98));
      `;
      mini.appendChild(lockedOverlay);
    }
    
    lockedOverlay.innerHTML = `
      <div style="text-align: center; margin-bottom: 12px;">
        <div style="font-size: 18px; margin-bottom: 4px;">✨</div>
        <div style="font-size: 11px; font-weight: 600; color: #0b1220;">Create Your Account</div>
        <div style="font-size: 9px; color: #64748b; margin-top: 2px;">Step 1 of 2</div>
      </div>
      <div class="mobius-mini-register-form">
        <input type="text" class="mobius-mini-reg-firstname" placeholder="First name *" style="
          width: 100%;
          box-sizing: border-box;
          padding: 8px 10px;
          border: 1px solid rgba(11, 18, 32, 0.15);
          border-radius: 6px;
          font-size: 10px;
          margin-bottom: 6px;
          outline: none;
        " />
        <input type="text" class="mobius-mini-reg-lastname" placeholder="Last name (optional)" style="
          width: 100%;
          box-sizing: border-box;
          padding: 8px 10px;
          border: 1px solid rgba(11, 18, 32, 0.15);
          border-radius: 6px;
          font-size: 10px;
          margin-bottom: 6px;
          outline: none;
        " />
        <input type="email" class="mobius-mini-reg-email" placeholder="Email address *" style="
          width: 100%;
          box-sizing: border-box;
          padding: 8px 10px;
          border: 1px solid rgba(11, 18, 32, 0.15);
          border-radius: 6px;
          font-size: 10px;
          margin-bottom: 6px;
          outline: none;
        " />
        <input type="password" class="mobius-mini-reg-password" placeholder="Password (8+ characters) *" style="
          width: 100%;
          box-sizing: border-box;
          padding: 8px 10px;
          border: 1px solid rgba(11, 18, 32, 0.15);
          border-radius: 6px;
          font-size: 10px;
          margin-bottom: 6px;
          outline: none;
        " />
        <input type="password" class="mobius-mini-reg-confirm" placeholder="Confirm password *" style="
          width: 100%;
          box-sizing: border-box;
          padding: 8px 10px;
          border: 1px solid rgba(11, 18, 32, 0.15);
          border-radius: 6px;
          font-size: 10px;
          margin-bottom: 8px;
          outline: none;
        " />
        <button class="mobius-mini-reg-submit" style="
          width: 100%;
          padding: 8px 12px;
          background: #2563eb;
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 10px;
          font-weight: 500;
          cursor: pointer;
        ">Continue</button>
        <div class="mobius-mini-reg-error" style="
          font-size: 9px;
          color: #dc2626;
          margin-top: 6px;
          display: none;
        "></div>
        <div style="text-align: center; font-size: 9px; color: #64748b; margin-top: 10px;">
          Already have an account? 
          <a href="#" class="mobius-mini-back-to-login" style="color: #2563eb; text-decoration: none; font-weight: 500;">Sign in</a>
        </div>
      </div>
    `;
    
    // Wire up form
    const firstNameInput = lockedOverlay.querySelector<HTMLInputElement>('.mobius-mini-reg-firstname');
    const lastNameInput = lockedOverlay.querySelector<HTMLInputElement>('.mobius-mini-reg-lastname');
    const emailInput = lockedOverlay.querySelector<HTMLInputElement>('.mobius-mini-reg-email');
    const passwordInput = lockedOverlay.querySelector<HTMLInputElement>('.mobius-mini-reg-password');
    const confirmInput = lockedOverlay.querySelector<HTMLInputElement>('.mobius-mini-reg-confirm');
    const submitBtn = lockedOverlay.querySelector<HTMLButtonElement>('.mobius-mini-reg-submit');
    const errorDiv = lockedOverlay.querySelector<HTMLElement>('.mobius-mini-reg-error');
    const backToLoginLink = lockedOverlay.querySelector('.mobius-mini-back-to-login');
    
    const showError = (msg: string) => {
      if (errorDiv) {
        errorDiv.textContent = msg;
        errorDiv.style.display = 'block';
      }
    };
    
    const doRegister = async () => {
      const firstName = firstNameInput?.value.trim() || '';
      const lastName = lastNameInput?.value.trim() || '';
      const email = emailInput?.value.trim() || '';
      const password = passwordInput?.value || '';
      const confirm = confirmInput?.value || '';
      
      // Validation
      if (!firstName) { showError('First name is required'); return; }
      if (!email) { showError('Email is required'); return; }
      if (!password) { showError('Password is required'); return; }
      if (password.length < 8) { showError('Password must be at least 8 characters'); return; }
      if (password !== confirm) { showError('Passwords do not match'); return; }
      
      if (submitBtn) {
        submitBtn.textContent = 'Creating account...';
        submitBtn.disabled = true;
      }
      if (errorDiv) errorDiv.style.display = 'none';
      
      try {
        const response = await fetch(`${API_BASE_AUTH}/api/v1/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            password,
            first_name: firstName,
            display_name: lastName ? `${firstName} ${lastName}` : firstName,
          }),
        });
        
        const data = await response.json();
        
        if (data.ok && data.access_token) {
          // Store auth tokens
          const authService = getAuthService();
          await authService.storeTokens({
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            expires_in: data.expires_in || 3600,
          });
          
          // Show onboarding step
          showOnboardingForm(firstName, data.access_token);
        } else {
          showError(data.error || 'Registration failed');
          if (submitBtn) {
            submitBtn.textContent = 'Continue';
            submitBtn.disabled = false;
          }
        }
      } catch (err) {
        showError('Connection error. Please try again.');
        if (submitBtn) {
          submitBtn.textContent = 'Continue';
          submitBtn.disabled = false;
        }
      }
    };
    
    submitBtn?.addEventListener('click', () => void doRegister());
    confirmInput?.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter') void doRegister();
    });
    
    // Back to login
    backToLoginLink?.addEventListener('click', (e: Event) => {
      e.preventDefault();
      void renderMiniIfAllowed(); // Re-render shows login form
    });
  };

  if (!isAuthenticated) {
    // Show locked state with login form
    if (!lockedOverlay) {
      lockedOverlay = document.createElement('div');
      lockedOverlay.className = 'mobius-mini-locked-overlay';
      lockedOverlay.style.cssText = `
        padding: 12px;
        background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.98));
      `;
      lockedOverlay.innerHTML = `
        <div style="text-align: center; margin-bottom: 10px;">
          <div style="font-size: 20px; margin-bottom: 4px;">🔒</div>
          <div style="font-size: 10px; font-weight: 600; color: #0b1220;">Sign in to Mobius</div>
        </div>
        <div class="mobius-mini-login-form">
          <input type="email" class="mobius-mini-login-email" placeholder="Email" style="
            width: 100%;
            box-sizing: border-box;
            padding: 8px 10px;
            border: 1px solid rgba(11, 18, 32, 0.15);
            border-radius: 6px;
            font-size: 10px;
            margin-bottom: 6px;
            outline: none;
          " value="sarah.chen@demo.clinic" />
          <input type="password" class="mobius-mini-login-password" placeholder="Password" style="
            width: 100%;
            box-sizing: border-box;
            padding: 8px 10px;
            border: 1px solid rgba(11, 18, 32, 0.15);
            border-radius: 6px;
            font-size: 10px;
            margin-bottom: 8px;
            outline: none;
          " value="demo1234" />
          <button class="mobius-mini-signin-btn" style="
            width: 100%;
            padding: 8px 12px;
            background: #2563eb;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 10px;
            font-weight: 500;
            cursor: pointer;
          ">Sign in</button>
          <div class="mobius-mini-login-error" style="
            font-size: 9px;
            color: #dc2626;
            margin-top: 6px;
            display: none;
          "></div>
          
          <!-- Divider -->
          <div style="display: flex; align-items: center; margin: 12px 0 10px;">
            <div style="flex: 1; height: 1px; background: rgba(11, 18, 32, 0.1);"></div>
            <span style="padding: 0 8px; font-size: 8px; color: #94a3b8;">or continue with</span>
            <div style="flex: 1; height: 1px; background: rgba(11, 18, 32, 0.1);"></div>
          </div>
          
          <!-- OAuth options -->
          <div style="display: flex; gap: 8px; margin-bottom: 10px;">
            <button class="mobius-mini-oauth-btn" data-provider="google" style="
              flex: 1;
              display: flex;
              align-items: center;
              justify-content: center;
              gap: 6px;
              padding: 8px;
              background: white;
              border: 1px solid rgba(11, 18, 32, 0.15);
              border-radius: 6px;
              font-size: 9px;
              color: #374151;
              cursor: pointer;
            ">
              <svg width="12" height="12" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Google
            </button>
            <button class="mobius-mini-oauth-btn" data-provider="microsoft" style="
              flex: 1;
              display: flex;
              align-items: center;
              justify-content: center;
              gap: 6px;
              padding: 8px;
              background: white;
              border: 1px solid rgba(11, 18, 32, 0.15);
              border-radius: 6px;
              font-size: 9px;
              color: #374151;
              cursor: pointer;
            ">
              <svg width="12" height="12" viewBox="0 0 23 23">
                <path fill="#f35325" d="M1 1h10v10H1z"/>
                <path fill="#81bc06" d="M12 1h10v10H12z"/>
                <path fill="#05a6f0" d="M1 12h10v10H1z"/>
                <path fill="#ffba08" d="M12 12h10v10H12z"/>
              </svg>
              Microsoft
            </button>
          </div>
          
          <!-- Enterprise SSO -->
          <button class="mobius-mini-sso-btn" style="
            width: 100%;
            padding: 8px 12px;
            background: #f8fafc;
            border: 1px solid rgba(11, 18, 32, 0.15);
            border-radius: 6px;
            font-size: 9px;
            color: #374151;
            cursor: pointer;
            margin-bottom: 10px;
          ">
            <span style="display: flex; align-items: center; justify-content: center; gap: 6px;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                <path d="M2 17l10 5 10-5"/>
                <path d="M2 12l10 5 10-5"/>
              </svg>
              Enterprise SSO
            </span>
          </button>
          
          <!-- Create account link -->
          <div style="text-align: center; font-size: 9px; color: #64748b;">
            Don't have an account? 
            <a href="#" class="mobius-mini-create-account" style="color: #2563eb; text-decoration: none; font-weight: 500;">Create one</a>
          </div>
          
          <div style="font-size: 8px; color: #94a3b8; margin-top: 8px; text-align: center;">
            Demo: sarah.chen@demo.clinic
          </div>
        </div>
      `;
      mini.appendChild(lockedOverlay);
      
      // Wire up login form
      const emailInput = lockedOverlay.querySelector<HTMLInputElement>('.mobius-mini-login-email');
      const passwordInput = lockedOverlay.querySelector<HTMLInputElement>('.mobius-mini-login-password');
      const signInBtn = lockedOverlay.querySelector<HTMLButtonElement>('.mobius-mini-signin-btn');
      const errorDiv = lockedOverlay.querySelector<HTMLElement>('.mobius-mini-login-error');
      
      const doLogin = async () => {
        const email = emailInput?.value.trim() || '';
        const password = passwordInput?.value || '';
        
        if (!email || !password) {
          if (errorDiv) {
            errorDiv.textContent = 'Please enter email and password';
            errorDiv.style.display = 'block';
          }
          return;
        }
        
        if (signInBtn) {
          signInBtn.textContent = 'Signing in...';
          signInBtn.disabled = true;
        }
        
        try {
          const authService = getAuthService();
          const result = await authService.login(email, password);
          
          if (result.success) {
            showToast('Signed in successfully!');
            // Refresh Mini to show authenticated state
            await renderMiniIfAllowed();
          } else {
            if (errorDiv) {
              errorDiv.textContent = result.error || 'Login failed';
              errorDiv.style.display = 'block';
            }
          }
        } catch (err) {
          if (errorDiv) {
            errorDiv.textContent = 'Connection error';
            errorDiv.style.display = 'block';
          }
        } finally {
          if (signInBtn) {
            signInBtn.textContent = 'Sign in';
            signInBtn.disabled = false;
          }
        }
      };
      
      signInBtn?.addEventListener('click', () => void doLogin());
      passwordInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') void doLogin();
      });
      
      // OAuth button handlers
      lockedOverlay.querySelectorAll('.mobius-mini-oauth-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          const provider = (btn as HTMLElement).dataset.provider;
          // TODO: Implement OAuth flow
          showToast(`${provider === 'google' ? 'Google' : 'Microsoft'} sign-in coming soon`);
          console.log(`[Mobius] OAuth login with ${provider}`);
        });
        // Hover effect
        btn.addEventListener('mouseenter', () => {
          (btn as HTMLElement).style.background = '#f1f5f9';
        });
        btn.addEventListener('mouseleave', () => {
          (btn as HTMLElement).style.background = 'white';
        });
      });
      
      // SSO button handler
      const ssoBtn = lockedOverlay.querySelector('.mobius-mini-sso-btn');
      ssoBtn?.addEventListener('click', () => {
        // TODO: Implement Enterprise SSO flow
        showToast('Enterprise SSO coming soon');
        console.log('[Mobius] Enterprise SSO login');
      });
      ssoBtn?.addEventListener('mouseenter', () => {
        (ssoBtn as HTMLElement).style.background = '#f1f5f9';
      });
      ssoBtn?.addEventListener('mouseleave', () => {
        (ssoBtn as HTMLElement).style.background = '#f8fafc';
      });
      
      // Create account link handler
      const createAccountLink = lockedOverlay.querySelector('.mobius-mini-create-account');
      createAccountLink?.addEventListener('click', (e) => {
        e.preventDefault();
        showRegistrationForm();
      });
    }
    lockedOverlay.style.display = '';
    
    // Hide content rows when locked
    if (greetingRow) greetingRow.style.display = 'none';
    if (patientRow) patientRow.style.display = 'none';
    if (attentionRow) attentionRow.style.display = 'none';
    if (taskBadgeRow) taskBadgeRow.style.display = 'none';
    if (noteRow) noteRow.style.display = 'none';
    
    return;
  }
  
  // Hide locked overlay when authenticated
  if (lockedOverlay) lockedOverlay.style.display = 'none';
  
  // Show content rows
  if (patientRow) patientRow.style.display = '';
  if (attentionRow) attentionRow.style.display = '';
  if (noteRow) noteRow.style.display = '';

  // Fetch status from backend
  try {
    const patientKey = patientOverride?.id || undefined;
    const status = await fetchMiniStatus(sessionId, patientKey) as MiniStatusResponseType;
    miniProceed = {
      color: (status.proceed.color || 'grey') as MiniColor,
      text: status.proceed.text || '',
    };
    if (status.tasking) {
      miniTasking = {
        color: (status.tasking.color || 'grey') as MiniColor,
        text: status.tasking.text || '',
        mode: status.tasking.mode as ExecutionMode | undefined,
        mode_text: status.tasking.mode_text,
      };
    }
    
    // Extract user/personalization data from response
    if (status.user) {
      // Merge response user data with existing profile (response has simplified structure)
      currentUserProfile = {
        ...currentUserProfile,
        user_id: status.user.user_id,
        display_name: status.user.display_name,
        greeting_name: status.user.greeting_name,
        is_onboarded: status.user.is_onboarded,
      } as UserProfile;
    }
    if (status.personalization) {
      currentPersonalization = status.personalization;
      
      // Update greeting row
      if (greetingRow && currentPersonalization.greeting && !greetingDismissed) {
        const greetingText = greetingRow.querySelector<HTMLElement>('.mobius-mini-greeting-text');
        if (greetingText) {
          greetingText.textContent = currentPersonalization.greeting;
        }
        greetingRow.style.display = '';
      }
    } else if (currentUserProfile && !greetingDismissed) {
      // Fallback greeting if no personalization from server
      const displayName = currentUserProfile.display_name || currentUserProfile.email?.split('@')[0] || 'there';
      const greetingText = greetingRow?.querySelector<HTMLElement>('.mobius-mini-greeting-text');
      if (greetingText) {
        greetingText.textContent = `Hello, ${displayName}`;
      }
      if (greetingRow) greetingRow.style.display = '';
    }
    
    // Update needs_attention state
    if (status.needs_attention) {
      needsAttention = {
        color: (status.needs_attention.color || 'grey') as MiniColor,
        problemStatement: status.needs_attention.problem_statement || null,
        userStatus: (status.needs_attention.user_status || null) as AttentionStatus,
      };
    } else {
      needsAttention = {
        color: (status.proceed.color || 'grey') as MiniColor,
        problemStatement: status.proceed.text || null,
        userStatus: null,
      };
    }
    taskCount = status.task_count || 0;
    
    // Update patient info from response if available
    if (status.patient?.found && status.patient.display_name) {
      const nameEl = mini.querySelector<HTMLElement>('.mobius-mini-patient-name');
      const idEl = mini.querySelector<HTMLElement>('.mobius-mini-patient-id');
      if (nameEl) nameEl.textContent = status.patient.display_name;
      if (idEl && status.patient.id_masked) idEl.textContent = `ID ${status.patient.id_masked}`;
      // Update minimized info patient name
      const minimizedPatient = mini.querySelector<HTMLElement>('.mobius-mini-minimized-patient');
      if (minimizedPatient) minimizedPatient.textContent = status.patient.display_name;
    }
  } catch {
    // keep defaults
  }

  // Calculate effective attention color
  let effectiveAttentionColor = needsAttention.color;
  if (needsAttention.userStatus === 'resolved') effectiveAttentionColor = 'green';
  else if (needsAttention.userStatus === 'confirmed_unresolved') effectiveAttentionColor = 'yellow';
  else if (needsAttention.userStatus === 'unable_to_confirm') effectiveAttentionColor = 'grey';

  // Update Needs Attention UI (new layout: problem text + status badge)
  if (attentionRow) {
    const dot = attentionRow.querySelector<HTMLElement>('.mobius-mini-dot');
    const problemText = attentionRow.querySelector<HTMLElement>('.mobius-mini-problem-text');
    const badgeText = attentionRow.querySelector<HTMLElement>('.mobius-mini-badge-text');
    const badge = attentionRow.querySelector<HTMLElement>('.mobius-mini-status-badge');
    
    // Dot color reflects status
    if (dot) {
      dot.className = `mobius-mini-dot ${colorToCssClass(effectiveAttentionColor)}`;
    }
    
    // Problem statement always visible
    if (problemText) {
      problemText.textContent = needsAttention.problemStatement || 'No issues detected';
    }
    
    // Status badge shows current status
    if (badgeText && badge) {
      if (needsAttention.userStatus === 'resolved') {
        badgeText.textContent = 'Resolved';
        badge.className = 'mobius-mini-status-badge status-resolved';
      } else if (needsAttention.userStatus === 'confirmed_unresolved') {
        badgeText.textContent = 'Unresolved';
        badge.className = 'mobius-mini-status-badge status-unresolved';
      } else if (needsAttention.userStatus === 'unable_to_confirm') {
        badgeText.textContent = 'Unconfirmed';
        badge.className = 'mobius-mini-status-badge status-unconfirmed';
      } else {
        badgeText.textContent = 'Set status';
        badge.className = 'mobius-mini-status-badge';
      }
    }
  }
  
  // Update minimized info dot
  const minimizedInfoEl = mini.querySelector<HTMLElement>('.mobius-mini-minimized-info');
  if (minimizedInfoEl) {
    const minimizedDot = minimizedInfoEl.querySelector<HTMLElement>('.mobius-mini-dot');
    if (minimizedDot) {
      minimizedDot.className = `mobius-mini-dot ${colorToCssClass(effectiveAttentionColor)}`;
    }
  }

  // Update task badge
  if (taskBadgeRow) {
    const countEl = taskBadgeRow.querySelector<HTMLElement>('.mobius-mini-task-count');
    if (countEl) countEl.textContent = String(taskCount);
    taskBadgeRow.style.display = taskCount > 0 ? '' : 'none';
  }

  // Legacy UI update (hidden rows)
  const rows = mini.querySelectorAll<HTMLElement>('.mobius-mini-row');
  // Legacy proceed/tasking rows are now hidden
  
  // Start patient context detection if enabled
  if (isAutoDetectionEnabled) {
    startPatientContextDetection();
  }
}

// Initialize sidebar
async function initSidebar() {
  console.log('[Mobius OS] Initializing sidebar...');
  
  // Check if sidebar already exists
  if (document.getElementById('mobius-os-sidebar')) {
    console.log('[Mobius OS] Sidebar already exists, skipping initialization');
    return Promise.resolve();
  }

  // Create sidebar container
  sidebarContainer = document.createElement('div');
  sidebarContainer.id = 'mobius-os-sidebar';
  sidebarContainer.setAttribute('style', `
    position: fixed !important;
    top: 0 !important;
    right: 0 !important;
    width: 450px !important;
    height: 100vh !important;
    min-height: 100vh !important;
    max-height: 100vh !important;
    background: white !important;
    z-index: 2147483647 !important;
    box-shadow: -2px 0 8px rgba(0,0,0,0.1) !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
    margin: 0 !important;
    padding: 0 !important;
  `);

  // Adjust page content to make room for sidebar
  const style = document.createElement('style');
  style.id = 'mobius-os-page-adjust';
  style.textContent = `
    body {
      margin-right: 450px !important;
      transition: margin-right 0.3s ease !important;
    }
    html {
      overflow-x: hidden !important;
    }
  `;
  document.head.appendChild(style);

  // Get or create session ID
  sessionId = await getOrCreateSessionId();

  // Create top row / header
  const topRow = document.createElement('div');
  topRow.className = 'top-row';
  
  const headerLeft = document.createElement('div');
  headerLeft.className = 'header-left';
  
  headerLeft.appendChild(ClientLogo({ clientName: 'CMHC' }));
  
  const logoSection = document.createElement('div');
  logoSection.className = 'logo-section';
  // Track the currently-mounted Mobius logo element; replaceChild must target a node that is
  // actually attached, otherwise it throws and aborts the send handler.
  let currentMobiusLogoEl = MobiusLogo({ status: mobiusStatus });
  logoSection.appendChild(currentMobiusLogoEl);
  const logoLabel = document.createElement('span');
  logoLabel.className = 'logo-label';
  logoLabel.textContent = 'Mobius OS';
  logoSection.appendChild(logoLabel);
  headerLeft.appendChild(logoSection);
  
  topRow.appendChild(headerLeft);
  let contextDisplayEl = ContextDisplay({ status: currentStatus, mode: currentMode });
  topRow.appendChild(contextDisplayEl);

  const headerActions = document.createElement('div');
  headerActions.className = 'header-actions';
  headerActions.appendChild(AlertButton({ 
    hasAlerts: false, 
    onClick: () => alert('Live Alerts:\n- No active alerts') 
  }));
  headerActions.appendChild(SettingsButton({ onClick: () => alert('Settings') }));
  // Collapse control (minimally invasive)
  const collapseBtn = document.createElement('button');
  collapseBtn.className = 'collapse-btn';
  collapseBtn.type = 'button';
  collapseBtn.title = 'Collapse';
  collapseBtn.textContent = '‹';
  collapseBtn.addEventListener('click', () => {
    void collapseToMini();
  });
  headerActions.appendChild(collapseBtn);
  topRow.appendChild(headerActions);
  
  sidebarContainer.appendChild(topRow);

  // Second row - context summary
  const secondRow = document.createElement('div');
  secondRow.className = 'second-row';
  const contextMount = document.createElement('div');
  contextMount.className = 'context-mount';
  secondRow.appendChild(contextMount);
  sidebarContainer.appendChild(secondRow);

  // Tasks panel
  const tasksPanel = TasksPanel({
    tasks: tasks,
    status: 'active',
    isCollapsed: false,
    onTaskToggle: (taskId, checked) => {
      const task = tasks.find(t => t.id === taskId);
      if (task) task.checked = checked;
    }
  });
  sidebarContainer.appendChild(tasksPanel);

  // Chat area container
  const chatAreaContainer = document.createElement('div');
  chatAreaContainer.className = 'chat-area';
  chatAreaContainer.id = 'chatArea';
  sidebarContainer.appendChild(chatAreaContainer);

  // Function to render messages
  function renderMessages() {
    chatAreaContainer.innerHTML = '';
    const chatArea = ChatArea({ 
      messages, 
      onFeedbackSubmit: (messageId, rating, feedback) => {
        console.log('Feedback submitted:', { messageId, rating, feedback });
      }
    });
    chatAreaContainer.appendChild(chatArea);
  }

  // Chat input
  const chatInput = ChatInput({
    onSend: async (messageText: string) => {
      // Add user message
      const userMessage: Message = {
        id: `msg_${Date.now()}`,
        content: messageText,
        timestamp: new Date().toISOString(),
        sessionId,
        type: 'user'
      };
      messages.push(userMessage);
      renderMessages();
      
      // Update Mobius logo to processing
      mobiusStatus = 'processing';
      const processingEl = MobiusLogo({ status: mobiusStatus });
      logoSection.replaceChild(processingEl, currentMobiusLogoEl);
      currentMobiusLogoEl = processingEl;
      
      try {
        // Send to backend
        const response = await sendChatMessage(messageText, sessionId);

        // Client is the source of truth for mode UI defaults. Backend is per-message overrides only.
        const uiDefaults = getUiDefaultsForMode(currentMode);
        const serverMessages = Array.isArray(response.messages) ? response.messages : [];

        if (serverMessages.length > 0) {
          for (const m of serverMessages) {
            const ui = { ...uiDefaults, ...(m.ui_overrides || {}) };

            const systemMsg: Message = {
              id: `msg_${Date.now()}_${m.kind}`,
              content: m.content,
              timestamp: new Date().toISOString(),
              sessionId,
              type: 'system',
              // Backend-driven visibility
              feedbackComponent: ui.feedbackComponent === true,
            };

            // Optional local thinking / guidance scaffolding (only if visible)
            if (ui.thinkingBox) {
              systemMsg.thinkingBox = {
                content: ['Processing message...', 'Generating response...'],
                isCollapsed: false,
              };
            }
            if (ui.guidanceActions) {
              systemMsg.guidanceActions = [
                { label: 'View Details', onClick: () => console.log('View details') },
                { label: 'Follow Up', onClick: () => console.log('Follow up') },
              ];
            }

            messages.push(systemMsg);
          }
        } else {
          // Fallback (older backend)
          messages.push({
            id: `msg_${Date.now()}_replayed`,
            content: response.replayed,
            timestamp: new Date().toISOString(),
            sessionId,
            type: 'system',
            thinkingBox: {
              content: ['Processing message...', 'Generating response...'],
              isCollapsed: false,
            },
            feedbackComponent: false,
          });

          messages.push({
            id: `msg_${Date.now()}_ack`,
            content: response.acknowledgement,
            timestamp: new Date().toISOString(),
            sessionId,
            type: 'system',
            feedbackComponent: false,
          });
        }
        
        renderMessages();
      } catch (error) {
        console.error('Error sending message:', error);
        const errorMessage: Message = {
          id: `msg_${Date.now()}_error`,
          content: `Error: ${error instanceof Error ? error.message : 'Failed to send message'}`,
          timestamp: new Date().toISOString(),
          sessionId,
          type: 'system'
        };
        messages.push(errorMessage);
        renderMessages();
      } finally {
        // Update Mobius logo back to idle
        mobiusStatus = 'idle';
        const idleEl = MobiusLogo({ status: mobiusStatus });
        logoSection.replaceChild(idleEl, currentMobiusLogoEl);
        currentMobiusLogoEl = idleEl;
      }
    }
  });
  sidebarContainer.appendChild(chatInput);

  // Footer
  const footer = document.createElement('div');
  footer.className = 'footer';
  
  const userDetailsEl = UserDetails({ userName: 'Dr. Smith', userRole: 'Provider' });
  const preferencesEl = PreferencesPanel({
    llmChoice,
    agentMode,
    onLLMChange: (llm) => {
      llmChoice = llm;
      console.log('LLM changed:', llm);
    },
    onAgentModeChange: (mode) => {
      agentMode = mode;
      console.log('Agent mode changed:', mode);
    },
    isExpanded: false
  });

  // One-line footer row: User | Role | LLM | Agent (with expandable preferences below)
  const footerRow = document.createElement('div');
  footerRow.className = 'user-details';
  footerRow.appendChild(userDetailsEl);
  footerRow.appendChild(preferencesEl);
  footer.appendChild(footerRow);
  sidebarContainer.appendChild(footer);

  function renderMode(mode: string) {
    const ui = getUiDefaultsForMode(mode);
    const layout = getLayoutForMode(mode, {
      recordType,
      recordId,
      onRecordChange: (type, value) => {
        recordType = type;
        recordId = value;
        console.log('Record ID changed:', type, value);
      },
      workflowButtons: [
        { label: 'Generate Report', onClick: () => console.log('Generate report') },
        { label: 'Schedule Follow-up', onClick: () => console.log('Schedule follow-up') },
      ],
    });

    renderSection(contextMount, layout.context, ui, componentRegistry);

    setVisible(topRow, ui.header);
    setVisible(tasksPanel, ui.tasksPanel);
    setVisible(chatAreaContainer, ui.chatArea);
    setVisible(chatInput, ui.chatInput);
    setVisible(userDetailsEl, ui.userDetails);
    setVisible(preferencesEl, ui.preferencesPanel);
    setVisible(footer, ui.userDetails || ui.preferencesPanel);
    setVisible(secondRow, contextMount.childElementCount > 0);
  }

  function setMode(nextMode: string) {
    currentMode = nextMode;
    const nextContext = ContextDisplay({ status: currentStatus, mode: currentMode });
    topRow.replaceChild(nextContext, contextDisplayEl);
    contextDisplayEl = nextContext;

    renderMode(currentMode);
  }

  // Example hook for future mode changes:
  // quickActionEl.addEventListener('click', () => setMode('Chat'));

  // Apply initial mode defaults.
  renderMode(currentMode);

  // Append to body (or html if body doesn't exist yet)
  const target = document.body || document.documentElement;
  if (!target) {
    console.error('[Mobius OS] No body or documentElement found!');
    return;
  }
  
  target.appendChild(sidebarContainer);
  console.log('[Mobius OS] Sidebar appended to DOM');

  // Initial render
  renderMessages();
  
  // Force a reflow to ensure styles are applied
  sidebarContainer.offsetHeight;
  
  console.log('[Mobius OS] Sidebar initialization complete. Position:', {
    top: sidebarContainer.offsetTop,
    right: window.innerWidth - sidebarContainer.offsetLeft - sidebarContainer.offsetWidth,
    width: sidebarContainer.offsetWidth,
    height: sidebarContainer.offsetHeight,
    computedStyle: window.getComputedStyle(sidebarContainer).position
  });
  
  return Promise.resolve();
}

// Content script boot: always loaded via content_scripts, but mini rendering is gated by allowlist.
console.log('[Mobius OS] Content script loaded. URL:', window.location.href);

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  const type = (msg && msg.type) as string | undefined;
  if (!type) return;

  void (async () => {
    try {
      if (type === 'mobius:setDomainAllowed') {
        await setDomainAllowed(String(msg.hostname || ''), Boolean(msg.allowed));
        const allowed = Boolean(msg.allowed);
        if (!allowed) removeSidebar();
        await renderMiniIfAllowed();
        sendResponse({ ok: true });
        return;
      }
      if (type === 'mobius:expand') {
        await expandToSidebar();
        sendResponse({ ok: true });
        return;
      }
      if (type === 'mobius:collapse') {
        await collapseToMini();
        sendResponse({ ok: true });
        return;
      }
      if (type === 'mobius:refreshMini') {
        await renderMiniIfAllowed();
        sendResponse({ ok: true });
        return;
      }
      sendResponse({ ok: false, error: 'unknown_message' });
    } catch (e) {
      const err = e instanceof Error ? e.message : String(e);
      sendResponse({ ok: false, error: err });
    }
  })();

  // Keep channel open for async sendResponse
  return true;
});

(async () => {
  sessionId = await getOrCreateSessionId();
  await renderMiniIfAllowed();
})();
