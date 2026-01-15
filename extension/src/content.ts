/**
 * Content script for Mobius OS extension
 * Injects the Mobius OS sidebar into web pages
 */

import './styles/sidebar.css';
import { getOrCreateSessionId } from './utils/session';
import { fetchMiniStatus, searchMiniPatients, sendChatMessage, submitMiniNote } from './services/api';
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
import { Message, Status, Task, StatusIndicatorStatus, LLMChoice, AgentMode } from './types';

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

type MiniColor = 'green' | 'yellow' | 'grey' | 'blue';
type MiniLine = { color: MiniColor; text: string };

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
} as const;

type MiniPos = { x: number; y: number };
type PatientOverride = { name: string; id: string; dob?: string };

let miniLastPos: MiniPos | null = null;
let miniProceed: MiniLine = { color: 'grey', text: 'Proceed: Not assessed' };
let miniTasking: MiniLine = { color: 'grey', text: 'Tasking: Not applicable' };
let patientOverride: PatientOverride | null = null;

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
  return patientOverride || { name: 'Unknown', id: '', dob: '' };
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

  // Header (drag handle + logo + menu)
  const header = document.createElement('div');
  header.className = 'mobius-mini-header';

  const dragHandle = document.createElement('div');
  dragHandle.className = 'mobius-mini-drag-handle';
  dragHandle.title = 'Drag';
  dragHandle.innerHTML = '<div class="mobius-mini-drag-dots"></div>';

  const brand = document.createElement('div');
  brand.className = 'mobius-mini-brand';
  brand.appendChild(MobiusLogo({ status: mobiusStatus }));

  const brandText = document.createElement('div');
  brandText.className = 'mobius-mini-brand-text';
  brandText.textContent = 'Mobius';
  brand.appendChild(brandText);

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
  menu.innerHTML = `
    <button class="mobius-mini-menu-item danger" type="button" data-action="disable-site">Disable on this site</button>
  `;
  menu.style.display = 'none';

  menuBtn.addEventListener('click', () => {
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
  });
  document.addEventListener('click', (e) => {
    if (!root.contains(e.target as Node)) {
      menu.style.display = 'none';
    }
  });

  header.appendChild(dragHandle);
  header.appendChild(brand);
  header.appendChild(expandBtn);
  header.appendChild(menuBtn);
  header.appendChild(menu);
  root.appendChild(header);

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

  // Proceed
  const proceedRow = document.createElement('div');
  proceedRow.className = 'mobius-mini-row';
  proceedRow.innerHTML = `
    <div class="mobius-mini-row-label">Proceed</div>
    <button class="mobius-mini-status" type="button" aria-label="Proceed status">
      <span class="mobius-mini-dot"></span>
      <span class="mobius-mini-status-text"></span>
    </button>
  `;
  root.appendChild(proceedRow);

  // Tasking
  const taskingRow = document.createElement('div');
  taskingRow.className = 'mobius-mini-row';
  taskingRow.innerHTML = `
    <div class="mobius-mini-row-label">Tasking</div>
    <button class="mobius-mini-status" type="button" aria-label="Tasking mode">
      <span class="mobius-mini-dot"></span>
      <span class="mobius-mini-status-text"></span>
    </button>
  `;
  root.appendChild(taskingRow);

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
  };
  renderPatient();

  const savePatient = async (p: PatientOverride) => {
    patientOverride = p;
    await storageSet({ [STORAGE_KEYS.patientOverride]: p });
    renderPatient();
  };

  patientRow.querySelector<HTMLButtonElement>('.mobius-mini-icon-btn')?.addEventListener('click', () => {
    openPatientModal((p) => void savePatient(p));
  });

  // Wire up statuses
  const applyStatus = (rowEl: HTMLElement, line: MiniLine) => {
    const dot = rowEl.querySelector<HTMLElement>('.mobius-mini-dot');
    const text = rowEl.querySelector<HTMLElement>('.mobius-mini-status-text');
    if (dot) {
      dot.className = `mobius-mini-dot ${colorToCssClass(line.color)}`;
    }
    if (text) text.textContent = line.text;
  };
  applyStatus(proceedRow, miniProceed);
  applyStatus(taskingRow, miniTasking);

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
  const allowed = await isDomainAllowed(getHostname());
  if (!allowed) {
    // If mini isn't visible, there's nowhere to show the toast; just no-op.
    const mini = document.getElementById(MINI_IDS.root) as HTMLElement | null;
    if (mini) showToast('Enable Mobius on this site first');
    return;
  }
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

  // Create mini if needed
  let mini = document.getElementById(MINI_IDS.root) as HTMLElement | null;
  if (!mini) {
    mini = createMini();
    document.body.appendChild(mini);
    const initial = miniLastPos || { x: 14, y: 14 };
    await setMiniPos(mini, initial);
  } else {
    // Ensure it's visible after collapsing from the full sidebar.
    mini.style.display = '';
  }

  // Fetch status from backend (stubbed currently)
  try {
    const status = await fetchMiniStatus(sessionId);
    miniProceed = status.proceed;
    miniTasking = status.tasking;
  } catch {
    // keep defaults
  }

  // Update UI
  const rows = mini.querySelectorAll<HTMLElement>('.mobius-mini-row');
  // Proceed row is index 1 after patient (0 patient, 1 proceed, 2 tasking, 3 note)
  const proceedRow = rows[1];
  const taskingRow = rows[2];
  if (proceedRow) {
    const dot = proceedRow.querySelector<HTMLElement>('.mobius-mini-dot');
    const text = proceedRow.querySelector<HTMLElement>('.mobius-mini-status-text');
    if (dot) dot.className = `mobius-mini-dot ${colorToCssClass(miniProceed.color)}`;
    if (text) text.textContent = miniProceed.text;
  }
  if (taskingRow) {
    const dot = taskingRow.querySelector<HTMLElement>('.mobius-mini-dot');
    const text = taskingRow.querySelector<HTMLElement>('.mobius-mini-status-text');
    if (dot) dot.className = `mobius-mini-dot ${colorToCssClass(miniTasking.color)}`;
    if (text) text.textContent = miniTasking.text;
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
