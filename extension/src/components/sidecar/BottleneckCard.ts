/**
 * BottleneckCard Component
 * 
 * The core UI for displaying questions/bottlenecks.
 * Uses question format for consistency with Mini.
 * Compact assignment dropdown near question.
 * Checkboxes always visible for bulk selection.
 */

import type { Bottleneck, AnswerOption, PrivacyContext } from '../../types/record';
import { formatLabel } from '../../services/personalization';
import { resolveValue, getSourceBadge, hasConflict } from '../../services/dataHierarchy';

export interface BottleneckCardProps {
  bottlenecks: Bottleneck[];
  privacyContext: PrivacyContext;
  onAnswer: (bottleneckId: string, answerId: string) => void;
  onAssign: (bottleneckId: string, mode: 'agentic' | 'copilot') => void;
  onOwn: (bottleneckId: string) => void;
  onAddNote: (bottleneckId: string, noteText: string) => void;
  onBulkAssign: (bottleneckIds: string[]) => void;
}

/**
 * Create the BottleneckCard element
 */
export function BottleneckCard(props: BottleneckCardProps): HTMLElement {
  const { bottlenecks, privacyContext, onAnswer, onAssign, onOwn, onAddNote, onBulkAssign } = props;
  
  const container = document.createElement('div');
  container.className = 'sidecar-bottleneck-card';
  
  // No bottlenecks = all clear
  if (bottlenecks.length === 0) {
    container.innerHTML = `
      <div class="sidecar-bottleneck-clear">
        <span class="sidecar-bottleneck-clear-icon">✓</span>
        <span class="sidecar-bottleneck-clear-text">All clear! No issues detected.</span>
      </div>
    `;
    return container;
  }
  
  // Header - always show task count context
  const header = document.createElement('div');
  header.className = 'sidecar-bottleneck-header';
  if (bottlenecks.length > 1) {
    header.innerHTML = `
      <span class="sidecar-bottleneck-count">${bottlenecks.length} tasks</span>
      <span class="sidecar-bottleneck-hint">Assign each to Mobius or resolve yourself</span>
    `;
  } else {
    header.innerHTML = `
      <span class="sidecar-bottleneck-count">1 task</span>
      <span class="sidecar-bottleneck-hint">Assign to Mobius or resolve yourself</span>
    `;
  }
  container.appendChild(header);
  
  // Render each bottleneck - no checkboxes, assign one at a time
  for (const bottleneck of bottlenecks) {
    const item = createBottleneckItem(
      bottleneck, 
      privacyContext,
      onAnswer,
      onAssign,
      onOwn,
      onAddNote
    );
    container.appendChild(item);
  }
  
  return container;
}

/**
 * Create a single bottleneck item
 */
function createBottleneckItem(
  bottleneck: Bottleneck,
  privacyContext: PrivacyContext,
  onAnswer: (bottleneckId: string, answerId: string) => void,
  onAssign: (bottleneckId: string, mode: 'agentic' | 'copilot') => void,
  onOwn: (bottleneckId: string) => void,
  onAddNote: (bottleneckId: string, noteText: string) => void
): HTMLElement {
  const item = document.createElement('div');
  item.className = 'sidecar-bottleneck-item';
  item.dataset.id = bottleneck.id;
  
  // Question row with question and assignment dropdown
  const questionRow = document.createElement('div');
  questionRow.className = 'sidecar-bottleneck-question-row';
  
  // Question text
  const questionText = document.createElement('div');
  questionText.className = 'sidecar-bottleneck-question';
  questionText.textContent = formatLabel(bottleneck.question_text, privacyContext);
  questionRow.appendChild(questionText);
  
  // Source badge (if not from user)
  const resolved = resolveValue(bottleneck.sources);
  if (resolved && resolved.source !== 'user') {
    const badge = document.createElement('span');
    badge.className = 'sidecar-source-badge';
    badge.textContent = getSourceBadge(resolved.source);
    badge.title = `Data ${resolved.source === 'batch' ? 'from batch analysis' : 'detected on page'}`;
    questionRow.appendChild(badge);
  }
  
  // Conflict indicator
  if (hasConflict(bottleneck.sources)) {
    const conflict = document.createElement('span');
    conflict.className = 'sidecar-conflict-badge';
    conflict.textContent = '⚠️';
    conflict.title = 'Different sources show different values';
    questionRow.appendChild(conflict);
  }
  
  // Assignment dropdown (compact, near question)
  const assignDropdown = createAssignDropdown(bottleneck, onAssign, onOwn);
  questionRow.appendChild(assignDropdown);
  
  item.appendChild(questionRow);
  
  // Answer options row
  const answersRow = document.createElement('div');
  answersRow.className = 'sidecar-bottleneck-answers';
  
  for (const option of bottleneck.answer_options) {
    const btn = createAnswerButton(option, () => {
      onAnswer(bottleneck.id, option.id);
    });
    answersRow.appendChild(btn);
  }
  
  item.appendChild(answersRow);
  
  // Mobius tip - informational only, not clickable
  if (bottleneck.mobius_can_handle) {
    const mobiusTip = document.createElement('div');
    mobiusTip.className = 'sidecar-bottleneck-mobius-tip';
    mobiusTip.innerHTML = `<span class="sidecar-mobius-tip-icon">✦</span> Mobius can handle this for you`;
    item.appendChild(mobiusTip);
  }
  
  // Inline note input (compact)
  const noteRow = document.createElement('div');
  noteRow.className = 'sidecar-bottleneck-note-row';
  
  const noteWrap = document.createElement('div');
  noteWrap.className = 'sidecar-bottleneck-note-wrap';
  
  const noteInput = document.createElement('input');
  noteInput.type = 'text';
  noteInput.className = 'sidecar-bottleneck-note-input';
  noteInput.placeholder = 'Add note...';
  
  const sendBtn = document.createElement('button');
  sendBtn.className = 'sidecar-bottleneck-note-send';
  sendBtn.type = 'button';
  sendBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>';
  sendBtn.title = 'Send note';
  
  const doSendNote = () => {
    const note = noteInput.value.trim();
    if (note) {
      onAddNote(bottleneck.id, note);
      noteInput.value = '';
    }
  };
  
  sendBtn.addEventListener('click', doSendNote);
  noteInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      doSendNote();
    }
  });
  
  noteWrap.appendChild(noteInput);
  noteWrap.appendChild(sendBtn);
  noteRow.appendChild(noteWrap);
  item.appendChild(noteRow);
  
  return item;
}

/**
 * Create assignment dropdown
 */
function createAssignDropdown(
  bottleneck: Bottleneck,
  onAssign: (bottleneckId: string, mode: 'agentic' | 'copilot') => void,
  onOwn: (bottleneckId: string) => void
): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = 'sidecar-assign-dropdown';
  
  // Dropdown button - more prominent
  const btn = document.createElement('button');
  btn.className = 'sidecar-assign-btn';
  btn.innerHTML = `
    <span class="sidecar-assign-label">Assign</span>
    <span class="sidecar-assign-arrow">▾</span>
  `;
  btn.title = 'Assign task';
  
  // Dropdown menu
  const menu = document.createElement('div');
  menu.className = 'sidecar-assign-menu';
  menu.style.display = 'none';
  
  // Option 1: Let Mobius handle (agentic)
  const mobiusOption = document.createElement('button');
  mobiusOption.className = 'sidecar-assign-option';
  mobiusOption.innerHTML = `
    <span class="sidecar-assign-option-text">Let Mobius handle</span>
    <span class="sidecar-assign-option-hint">Fully automated</span>
  `;
  if (bottleneck.mobius_action) {
    mobiusOption.title = bottleneck.mobius_action;
  }
  mobiusOption.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.style.display = 'none';
    btn.querySelector('.sidecar-assign-label')!.textContent = 'Mobius';
    btn.classList.add('sidecar-assign-btn--assigned');
    onAssign(bottleneck.id, 'agentic');
  });
  menu.appendChild(mobiusOption);
  
  // Option 2: Watch Mobius do it (copilot)
  const copilotOption = document.createElement('button');
  copilotOption.className = 'sidecar-assign-option';
  copilotOption.innerHTML = `
    <span class="sidecar-assign-option-text">Watch Mobius do it</span>
    <span class="sidecar-assign-option-hint">You review each step</span>
  `;
  copilotOption.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.style.display = 'none';
    btn.querySelector('.sidecar-assign-label')!.textContent = 'Copilot';
    btn.classList.add('sidecar-assign-btn--assigned');
    onAssign(bottleneck.id, 'copilot');
  });
  menu.appendChild(copilotOption);
  
  // Divider
  const divider = document.createElement('div');
  divider.className = 'sidecar-assign-divider';
  menu.appendChild(divider);
  
  // Option 3: I'll do it
  const userOption = document.createElement('button');
  userOption.className = 'sidecar-assign-option';
  userOption.innerHTML = `
    <span class="sidecar-assign-option-text">I'll do it myself</span>
    <span class="sidecar-assign-option-hint">Manual resolution</span>
  `;
  userOption.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.style.display = 'none';
    btn.querySelector('.sidecar-assign-label')!.textContent = 'Me';
    btn.classList.add('sidecar-assign-btn--assigned');
    onOwn(bottleneck.id);
  });
  menu.appendChild(userOption);
  
  // Toggle menu
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = menu.style.display !== 'none';
    menu.style.display = isOpen ? 'none' : 'block';
  });
  
  // Close on outside click
  document.addEventListener('click', () => {
    menu.style.display = 'none';
  });
  
  wrapper.appendChild(btn);
  wrapper.appendChild(menu);
  
  return wrapper;
}

/**
 * Create an answer button
 */
function createAnswerButton(option: AnswerOption, onClick: () => void): HTMLElement {
  const btn = document.createElement('button');
  btn.className = 'sidecar-answer-btn';
  btn.textContent = option.label;
  if (option.description) {
    btn.title = option.description;
  }
  btn.addEventListener('click', () => {
    selectAnswerButton(btn);
    onClick();
  });
  return btn;
}

function selectAnswerButton(btn: HTMLButtonElement): void {
  const container = btn.closest('.sidecar-bottleneck-answers');
  if (!container) {
    console.log('[BottleneckCard] Container not found for button');
    return;
  }
  // Remove selected class from all buttons in this container
  const allBtns = container.querySelectorAll('.sidecar-answer-btn');
  allBtns.forEach(el => {
    el.classList.remove('sidecar-answer-btn--selected');
  });
  // Add selected class to clicked button
  btn.classList.add('sidecar-answer-btn--selected');
  console.log('[BottleneckCard] Selected button:', btn.textContent, 'Classes:', btn.className);
}

/**
 * Create the "All Clear" state
 */
export function AllClearCard(): HTMLElement {
  const container = document.createElement('div');
  container.className = 'sidecar-bottleneck-card sidecar-bottleneck-card--clear';
  container.innerHTML = `
    <div class="sidecar-bottleneck-clear">
      <span class="sidecar-bottleneck-clear-icon">✓</span>
      <div class="sidecar-bottleneck-clear-text">
        <strong>All clear!</strong>
        <span>No issues detected for this patient.</span>
      </div>
    </div>
  `;
  return container;
}
