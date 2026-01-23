/**
 * BottleneckCard Component
 * 
 * Redesigned for Workflow Mode UI:
 * - Top-level workflow mode selector (Mobius handle, Do together, I'll handle)
 * - Batch recommendation pre-selects the mode
 * - Content changes based on selected mode
 * - "Set status" button (same as Mini for consistency)
 */

import type { Bottleneck, AnswerOption, PrivacyContext, WorkflowMode } from '../../types/record';
import { formatLabel } from '../../services/personalization';
import { resolveValue, getSourceBadge, hasConflict } from '../../services/dataHierarchy';

export interface BottleneckCardProps {
  bottlenecks: Bottleneck[];
  privacyContext: PrivacyContext;
  recommendedMode?: WorkflowMode;
  agenticConfidence?: number;
  recommendationReason?: string;
  agenticActions?: string[];
  onWorkflowSelect: (mode: WorkflowMode, note?: string) => void;
  onStatusOverride: (status: 'resolved' | 'unresolved') => void;  // Changed from onResolveOverride - uses same status system as Mini
  onAnswer: (bottleneckId: string, answerId: string) => void;
  onAddNote: (bottleneckId: string, noteText: string) => void;
  currentStatus?: 'resolved' | 'unresolved' | null;  // Current user override status (for display)
}

/**
 * Create the BottleneckCard element with workflow mode selector
 */
export function BottleneckCard(props: BottleneckCardProps): HTMLElement {
  const { 
    bottlenecks, 
    privacyContext, 
    recommendedMode,
    agenticConfidence,
    recommendationReason,
    agenticActions,
    onWorkflowSelect, 
    onStatusOverride,
    onAnswer, 
    onAddNote,
    currentStatus
  } = props;
  
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
  
  // State
  let selectedMode: WorkflowMode | null = recommendedMode || null;
  
  // Top row: Set status button (same as Mini for consistency)
  const overrideRow = document.createElement('div');
  overrideRow.className = 'sidecar-workflow-override-row';
  const statusButton = document.createElement('button');
  statusButton.className = 'sidecar-workflow-status-btn';
  statusButton.type = 'button';
  
  // Set button text based on current status
  if (currentStatus === 'resolved') {
    statusButton.textContent = 'Resolved ▾';
    statusButton.classList.add('status-resolved');
  } else if (currentStatus === 'unresolved') {
    statusButton.textContent = 'Unresolved ▾';
    statusButton.classList.add('status-unresolved');
  } else {
    statusButton.textContent = 'Set status ▾';
  }
  
  overrideRow.appendChild(statusButton);
  container.appendChild(overrideRow);
  
  // Status button handler - shows Resolved/Unresolved dropdown (same as Mini)
  statusButton.addEventListener('click', (e) => {
    e.stopPropagation();
    // Remove any existing dropdown
    document.querySelectorAll('.sidecar-status-dropdown').forEach(d => d.remove());
    
    const btnRect = statusButton.getBoundingClientRect();
    const dropdown = createStatusDropdown(btnRect, currentStatus, onStatusOverride);
    document.body.appendChild(dropdown);
  });
  
  // Problem statement (first bottleneck's question)
  const problemRow = document.createElement('div');
  problemRow.className = 'sidecar-workflow-problem';
  problemRow.textContent = formatLabel(bottlenecks[0].question_text, privacyContext);
  container.appendChild(problemRow);
  
  // Recommendation message (if available)
  if (recommendedMode && agenticConfidence !== undefined) {
    const recRow = document.createElement('div');
    recRow.className = 'sidecar-workflow-recommendation';
    
    let recMessage = '';
    if (recommendedMode === 'mobius' && agenticConfidence >= 80) {
      recMessage = `Mobius recommends: Let me handle this (${agenticConfidence}% confident)`;
    } else if (recommendedMode === 'mobius' || recommendedMode === 'together') {
      recMessage = `Mobius recommends: ${recommendedMode === 'mobius' ? 'Let me handle this' : 'Let\'s work together'} (${agenticConfidence}% confident)`;
    } else {
      recMessage = `Mobius recommends: You should review this`;
    }
    
    recRow.innerHTML = `
      <span class="sidecar-workflow-rec-icon">✦</span>
      <span class="sidecar-workflow-rec-text">${recMessage}</span>
    `;
    container.appendChild(recRow);
  }
  
  // Workflow mode selector
  const modeSelector = document.createElement('div');
  modeSelector.className = 'sidecar-workflow-mode-selector';
  
  const modes: { id: WorkflowMode; label: string; hint: string }[] = [
    { id: 'mobius', label: 'Mobius handle', hint: 'Fully automated' },
    { id: 'together', label: 'Do together', hint: 'Collaborative' },
    { id: 'manual', label: 'I\'ll handle', hint: 'Track my work' },
  ];
  
  for (const mode of modes) {
    const modeBtn = document.createElement('button');
    modeBtn.className = 'sidecar-workflow-mode-btn';
    modeBtn.dataset.mode = mode.id;
    if (selectedMode === mode.id) {
      modeBtn.classList.add('sidecar-workflow-mode-btn--selected');
    }
    modeBtn.innerHTML = `
      <span class="sidecar-workflow-mode-radio">${selectedMode === mode.id ? '●' : '○'}</span>
      <span class="sidecar-workflow-mode-label">${mode.label}</span>
    `;
    modeBtn.title = mode.hint;
    
    modeBtn.addEventListener('click', () => {
      selectedMode = mode.id;
      updateModeSelection();
      updateContentArea();
      onWorkflowSelect(mode.id);
    });
    
    modeSelector.appendChild(modeBtn);
  }
  
  container.appendChild(modeSelector);
  
  // Divider
  const divider = document.createElement('div');
  divider.className = 'sidecar-workflow-divider';
  container.appendChild(divider);
  
  // Content area - changes based on mode
  const contentArea = document.createElement('div');
  contentArea.className = 'sidecar-workflow-content';
  container.appendChild(contentArea);
  
  // Note input (always visible)
  const noteRow = document.createElement('div');
  noteRow.className = 'sidecar-workflow-note-row';
  noteRow.innerHTML = `
    <div class="sidecar-workflow-note-wrap">
      <input type="text" class="sidecar-workflow-note-input" placeholder="Add note..." />
      <button type="button" class="sidecar-workflow-note-send" title="Send note">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>
      </button>
    </div>
  `;
  container.appendChild(noteRow);
  
  // Note send handler
  const noteInput = noteRow.querySelector<HTMLInputElement>('.sidecar-workflow-note-input');
  const noteSendBtn = noteRow.querySelector<HTMLButtonElement>('.sidecar-workflow-note-send');
  
  const doSendNote = () => {
    const note = noteInput?.value.trim();
    if (note && bottlenecks[0]) {
      onAddNote(bottlenecks[0].id, note);
      if (noteInput) noteInput.value = '';
    }
  };
  
  noteSendBtn?.addEventListener('click', doSendNote);
  noteInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      doSendNote();
    }
  });
  
  // Update mode selection UI
  function updateModeSelection(): void {
    const btns = modeSelector.querySelectorAll<HTMLButtonElement>('.sidecar-workflow-mode-btn');
    btns.forEach(btn => {
      const isSelected = btn.dataset.mode === selectedMode;
      btn.classList.toggle('sidecar-workflow-mode-btn--selected', isSelected);
      const radio = btn.querySelector('.sidecar-workflow-mode-radio');
      if (radio) radio.textContent = isSelected ? '●' : '○';
    });
  }
  
  // Collect all answer options from all bottlenecks (consistent across modes)
  function getAllAnswerOptions(): Array<{ option: AnswerOption; bottleneck: Bottleneck; fullId: string }> {
    const allOptions: Array<{ option: AnswerOption; bottleneck: Bottleneck; fullId: string }> = [];
    for (const bottleneck of bottlenecks) {
      for (const option of bottleneck.answer_options) {
        allOptions.push({
          option,
          bottleneck,
          fullId: `${bottleneck.id}:${option.id}`
        });
      }
    }
    return allOptions;
  }

  // Update content area based on selected mode
  function updateContentArea(): void {
    contentArea.innerHTML = '';
    
    // Get all options (consistent across all modes)
    const allOptions = getAllAnswerOptions();
    
    if (selectedMode === 'mobius') {
      // Mobius handle: Show what Mobius will do + only options Mobius can handle
      const mobiusContent = document.createElement('div');
      mobiusContent.className = 'sidecar-workflow-mobius-content';
      
      if (agenticActions && agenticActions.length > 0) {
        mobiusContent.innerHTML = `
          <div class="sidecar-workflow-mobius-message">
            Mobius will handle this automatically.
          </div>
          <div class="sidecar-workflow-mobius-actions">
            <span class="sidecar-workflow-mobius-actions-label">Planned actions:</span>
            <ul class="sidecar-workflow-mobius-actions-list">
              ${agenticActions.map(a => `<li>${formatActionLabel(a)}</li>`).join('')}
            </ul>
          </div>
        `;
      } else {
        mobiusContent.innerHTML = `
          <div class="sidecar-workflow-mobius-message">
            Mobius will handle this automatically. You'll be notified when complete.
          </div>
        `;
      }
      
      // Show only options that Mobius can handle (filter by bottleneck.mobius_can_handle)
      const mobiusOptions = allOptions.filter(item => item.bottleneck.mobius_can_handle);
      
      if (mobiusOptions.length > 0) {
        const optionsSection = document.createElement('div');
        optionsSection.className = 'sidecar-workflow-mobius-options';
        optionsSection.innerHTML = `
          <div class="sidecar-workflow-option-group-header">
            <span class="sidecar-workflow-option-group-icon">✓</span>
            <span class="sidecar-workflow-option-group-title">Mobius will resolve:</span>
          </div>
        `;
        
        const optionsList = document.createElement('div');
        optionsList.className = 'sidecar-workflow-options-list';
        
        for (const { option, fullId } of mobiusOptions) {
          const optionEl = createOptionCheckbox(
            { ...option, id: fullId },
            () => {} // Read-only in Mobius mode
          );
          const checkbox = optionEl.querySelector<HTMLInputElement>('input[type="checkbox"]');
          if (checkbox) {
            checkbox.disabled = true;
            checkbox.checked = true; // Show as "will be handled"
          }
          optionsList.appendChild(optionEl);
        }
        
        optionsSection.appendChild(optionsList);
        mobiusContent.appendChild(optionsSection);
      }
      
      contentArea.appendChild(mobiusContent);
      
    } else if (selectedMode === 'together') {
      // Do together: Show ALL options, grouped by Mobius capability (bottleneck-level)
      const togetherContent = document.createElement('div');
      togetherContent.className = 'sidecar-workflow-together-content';
      
      // Group options by bottleneck's Mobius capability
      const mobiusOptions: Array<{ option: AnswerOption; bottleneck: Bottleneck; fullId: string }> = [];
      const manualOptions: Array<{ option: AnswerOption; bottleneck: Bottleneck; fullId: string }> = [];
      
      for (const item of allOptions) {
        if (item.bottleneck.mobius_can_handle) {
          mobiusOptions.push(item);
        } else {
          manualOptions.push(item);
        }
      }
      
      // Mobius can handle section
      if (mobiusOptions.length > 0) {
        const mobiusSection = document.createElement('div');
        mobiusSection.className = 'sidecar-workflow-option-group';
        mobiusSection.innerHTML = `
          <div class="sidecar-workflow-option-group-header">
            <span class="sidecar-workflow-option-group-icon">✦</span>
            <span class="sidecar-workflow-option-group-title">Mobius can handle</span>
          </div>
        `;
        
        const optionsList = document.createElement('div');
        optionsList.className = 'sidecar-workflow-options-list';
        
        for (const { option, fullId } of mobiusOptions) {
          const optionEl = createOptionCheckbox(
            { ...option, id: fullId },
            (checked) => {
              if (checked) {
                const [bottleneckId, optionId] = fullId.split(':');
                onAnswer(bottleneckId, optionId);
              }
            }
          );
          optionsList.appendChild(optionEl);
        }
        
        mobiusSection.appendChild(optionsList);
        togetherContent.appendChild(mobiusSection);
      }
      
      // Manual section
      if (manualOptions.length > 0) {
        const manualSection = document.createElement('div');
        manualSection.className = 'sidecar-workflow-option-group';
        manualSection.innerHTML = `
          <div class="sidecar-workflow-option-group-header">
            <span class="sidecar-workflow-option-group-icon">👤</span>
            <span class="sidecar-workflow-option-group-title">You'll need to handle</span>
          </div>
        `;
        
        const optionsList = document.createElement('div');
        optionsList.className = 'sidecar-workflow-options-list';
        
        for (const { option, fullId } of manualOptions) {
          const optionEl = createOptionCheckbox(
            { ...option, id: fullId },
            (checked) => {
              if (checked) {
                const [bottleneckId, optionId] = fullId.split(':');
                onAnswer(bottleneckId, optionId);
              }
            }
          );
          optionsList.appendChild(optionEl);
        }
        
        manualSection.appendChild(optionsList);
        togetherContent.appendChild(manualSection);
      }
      
      // If no options at all, show message
      if (allOptions.length === 0) {
        togetherContent.innerHTML = `
          <div class="sidecar-workflow-prompt">
            No options available for this issue.
          </div>
        `;
      }
      
      contentArea.appendChild(togetherContent);
      
    } else if (selectedMode === 'manual') {
      // I'll handle: Show top 2 tasks with dropdowns to resolve
      const manualContent = document.createElement('div');
      manualContent.className = 'sidecar-workflow-manual-content';
      
      manualContent.innerHTML = `
        <div class="sidecar-workflow-manual-message">
          Select an option below to resolve each task. Mobius will monitor and remind if needed.
        </div>
      `;
      
      // Show top 2 bottlenecks (already filtered by backend to highest impact)
      // Each bottleneck gets its own card with a dropdown
      const tasksContainer = document.createElement('div');
      tasksContainer.className = 'sidecar-manual-tasks-container';
      
      for (const bottleneck of bottlenecks.slice(0, 2)) {
        const taskCard = createTaskCardWithDropdown(bottleneck, onAnswer);
        tasksContainer.appendChild(taskCard);
      }
      
      manualContent.appendChild(tasksContainer);
      contentArea.appendChild(manualContent);
      
    } else {
      // No mode selected - show prompt
      contentArea.innerHTML = `
        <div class="sidecar-workflow-prompt">
          Select how you'd like to handle this issue above.
        </div>
      `;
    }
  }
  
  // Initial render
  updateContentArea();
  
  return container;
}

/**
 * Create an option checkbox
 */
function createOptionCheckbox(
  option: AnswerOption, 
  onChange: (checked: boolean) => void
): HTMLElement {
  const wrapper = document.createElement('label');
  wrapper.className = 'sidecar-workflow-option';
  
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.className = 'sidecar-workflow-option-checkbox';
  
  const label = document.createElement('span');
  label.className = 'sidecar-workflow-option-label';
  label.textContent = option.label;
  
  checkbox.addEventListener('change', () => {
    onChange(checkbox.checked);
  });
  
  wrapper.appendChild(checkbox);
  wrapper.appendChild(label);
  
  if (option.description) {
    wrapper.title = option.description;
  }
  
  return wrapper;
}

/**
 * Create a task card with dropdown for "I'll handle" mode
 */
function createTaskCardWithDropdown(
  bottleneck: Bottleneck,
  onAnswer: (bottleneckId: string, answerId: string) => void
): HTMLElement {
  const card = document.createElement('div');
  card.className = 'sidecar-manual-task-card';
  
  // Task question
  const questionEl = document.createElement('div');
  questionEl.className = 'sidecar-manual-task-question';
  questionEl.textContent = bottleneck.question_text;
  card.appendChild(questionEl);
  
  // Dropdown for options
  const dropdownWrap = document.createElement('div');
  dropdownWrap.className = 'sidecar-manual-task-dropdown-wrap';
  
  const select = document.createElement('select');
  select.className = 'sidecar-manual-task-dropdown';
  select.innerHTML = '<option value="">Select an option...</option>';
  
  // Add options
  for (const option of bottleneck.answer_options) {
    const optionEl = document.createElement('option');
    optionEl.value = option.id;
    optionEl.textContent = option.label;
    if (bottleneck.selected_answer === option.id) {
      optionEl.selected = true;
    }
    select.appendChild(optionEl);
  }
  
  // Handle selection - answers the question (does NOT resolve the task)
  // The bottleneck may still exist, it just means the task is answered/confirmed
  select.addEventListener('change', (e) => {
    const selectedValue = (e.target as HTMLSelectElement).value;
    if (selectedValue) {
      onAnswer(bottleneck.id, selectedValue);
      // Mark as answered (not resolved) - task card stays visible, dropdown stays enabled
      select.classList.add('sidecar-manual-task-dropdown--answered');
      card.classList.add('sidecar-manual-task-card--answered');
    }
  });
  
  dropdownWrap.appendChild(select);
  card.appendChild(dropdownWrap);
  
  // Show selected answer if already answered (but task is still active, not resolved)
  if (bottleneck.selected_answer) {
    select.value = bottleneck.selected_answer;
    select.classList.add('sidecar-manual-task-dropdown--answered');
    card.classList.add('sidecar-manual-task-card--answered');
  }
  
  // Only disable if status is actually "resolved" (not just "answered")
  if (bottleneck.status === 'resolved') {
    select.disabled = true;
    select.classList.add('sidecar-manual-task-dropdown--resolved');
    card.classList.add('sidecar-manual-task-card--resolved');
  }
  
  return card;
}

/**
 * Format action label for display
 */
function formatActionLabel(action: string): string {
  const labels: Record<string, string> = {
    'search_history': 'Search patient history for prior coverage',
    'check_medicaid': 'Check Medicaid/Medicare eligibility',
    'send_portal': 'Send portal message to patient',
    'send_sms': 'Send SMS request',
    'run_eligibility_check': 'Run 270/271 eligibility check',
    'check_portal_uploads': 'Check portal for recent uploads',
    'send_card_request': 'Send insurance card request',
    'run_verification': 'Run eligibility verification',
    'check_benefits': 'Check benefit details',
    'send_sms_reminder': 'Send SMS reminder',
    'book_medicaid_transport': 'Book Medicaid transportation',
    'check_transport_status': 'Check transport booking status',
    'send_scheduling_link': 'Send scheduling link',
    'submit_auth': 'Submit authorization request',
    'review_docs': 'Review clinical documentation',
    'check_portal_status': 'Check payer portal status',
    'compile_docs': 'Compile documentation package',
    'submit_renewal': 'Submit renewal request',
    'verify_coverage': 'Verify coverage status',
    'send_confirmation': 'Send confirmation request',
  };
  
  return labels[action] || action.replace(/_/g, ' ');
}

/**
 * Create status dropdown (same as Mini - Resolved/Unresolved options)
 */
function createStatusDropdown(
  anchorRect: DOMRect,
  currentStatus: 'resolved' | 'unresolved' | null | undefined,
  onSelect: (status: 'resolved' | 'unresolved') => void
): HTMLElement {
  const dropdown = document.createElement('div');
  dropdown.className = 'sidecar-status-dropdown';
  const dropdownWidth = 200;
  const dropdownHeight = 100;
  
  // Position dropdown above or below button
  const spaceAbove = anchorRect.top;
  const spaceBelow = window.innerHeight - anchorRect.bottom;
  const preferAbove = spaceAbove > spaceBelow;
  const top = preferAbove 
    ? anchorRect.top - dropdownHeight - 4
    : anchorRect.bottom + 4;
  
  dropdown.style.cssText = `
    position: fixed;
    top: ${top}px;
    left: ${anchorRect.left}px;
    width: ${dropdownWidth}px;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.18);
    z-index: 2147483647;
    padding: 4px 0;
  `;
  
  // Status options (same as Mini)
  const options = [
    { status: 'resolved' as const, label: 'Resolved', icon: '✓', description: 'Problem fixed, no further action' },
    { status: 'unresolved' as const, label: 'Unresolved', icon: '✗', description: 'Issue remains unresolved' },
  ];
  
  options.forEach((opt) => {
    const isSelected = currentStatus === opt.status;
    const item = document.createElement('button');
    item.type = 'button';
    item.style.cssText = `
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 1px;
      width: 100%;
      padding: 8px 12px;
      border: none;
      background: ${isSelected ? '#f1f5f9' : 'transparent'};
      cursor: pointer;
      text-align: left;
    `;
    item.innerHTML = `
      <div style="display:flex;align-items:center;gap:6px;font-size:11px;font-weight:500;color:#1e293b;">
        <span>${opt.icon}</span>
        <span>${opt.label}</span>
      </div>
      <div style="font-size:9px;color:#64748b;padding-left:18px;">${opt.description}</div>
    `;
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      onSelect(opt.status);
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
  
  // Close dropdown when clicking outside
  const closeOnOutsideClick = (e: MouseEvent) => {
    if (!dropdown.contains(e.target as Node)) {
      dropdown.remove();
      document.removeEventListener('click', closeOnOutsideClick);
    }
  };
  setTimeout(() => document.addEventListener('click', closeOnOutsideClick), 0);
  
  return dropdown;
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
