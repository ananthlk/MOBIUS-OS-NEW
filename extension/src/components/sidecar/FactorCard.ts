/**
 * FactorCard Component
 * 
 * Displays a single factor (L2) in the simplified Sidecar UI.
 * Shows: factor status, mode selector (if blocked), steps, and evidence link.
 * 
 * Collapsed: Single line with status
 * Expanded: Mode selector + steps + evidence
 */

import { Factor, FactorStep, WorkflowMode, UserRemedy } from '../../types';

export interface FactorCardProps {
  factor: Factor;
  isExpanded: boolean;
  onModeSelect: (factorType: string, mode: WorkflowMode) => void;
  onStepAction: (stepId: string, action: 'done' | 'skip' | 'delegate', answerCode?: string) => void;
  onEvidenceClick: (factorType: string) => void;
  onToggleExpand: (factorType: string) => void;
  onResolve?: (factorType: string, status: 'resolved' | 'unresolved') => void;
  onAddRemedy?: (factorType: string, remedyText: string, outcome: 'worked' | 'partial' | 'failed', notes?: string) => void;
}

/**
 * Get status icon for factor
 */
function getStatusIcon(status: string, userOverride?: 'resolved' | 'unresolved' | null): string {
  if (userOverride === 'resolved') {
    return '✓'; // User resolved icon
  }
  if (userOverride === 'unresolved') {
    return '⚠'; // User flagged icon
  }
  switch (status) {
    case 'resolved': return '✓';
    case 'blocked': return '⚠️';
    case 'waiting': return '◯';
    default: return '○';
  }
}

/**
 * Get status class for styling
 */
function getStatusClass(status: string, userOverride?: 'resolved' | 'unresolved' | null): string {
  if (userOverride === 'resolved') {
    return 'factor-resolved factor-user-override';
  }
  if (userOverride === 'unresolved') {
    return 'factor-blocked factor-user-flagged';
  }
  switch (status) {
    case 'resolved': return 'factor-resolved';
    case 'blocked': return 'factor-blocked';
    case 'waiting': return 'factor-waiting';
    default: return '';
  }
}

/**
 * Get human-friendly status label based on system confidence
 * This always reflects system's view, not user action
 */
function getSystemConfidenceLabel(status: string): string {
  switch (status) {
    case 'resolved': return 'Looks good';
    case 'blocked': return 'Needs your help';
    case 'waiting': return 'Almost there';
    default: return 'Checking...';
  }
}

/**
 * Get CSS class for status label prominence
 */
function getStatusLabelClass(status: string): string {
  switch (status) {
    case 'blocked': return 'status-needs-help';  // More prominent
    case 'waiting': return 'status-almost';      // Medium
    case 'resolved': return 'status-good';       // Subtle
    default: return '';
  }
}

/**
 * Create Mini-style status dropdown for per-factor override
 */
function createStatusDropdown(
  userOverride: 'resolved' | 'unresolved' | null | undefined,
  onSelect: (status: 'resolved' | 'unresolved') => void
): HTMLElement {
  const container = document.createElement('div');
  container.className = 'factor-status-dropdown';
  
  // Determine button text based on current override
  let btnText = 'Set status ▾';
  let btnClass = 'factor-status-dropdown-btn';
  if (userOverride === 'resolved') {
    btnText = 'Resolved ▾';
    btnClass += ' is-resolved';
  } else if (userOverride === 'unresolved') {
    btnText = 'Flagged ▾';
    btnClass += ' is-flagged';
  }
  
  // Dropdown button
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = btnClass;
  btn.textContent = btnText;
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const menu = container.querySelector('.factor-status-menu') as HTMLElement;
    if (menu) {
      const isVisible = menu.style.display === 'block';
      menu.style.display = isVisible ? 'none' : 'block';
    }
  });
  container.appendChild(btn);
  
  // Dropdown menu
  const menu = document.createElement('div');
  menu.className = 'factor-status-menu';
  menu.style.display = 'none';
  
  // Options
  const options = [
    { status: 'resolved' as const, label: 'Resolved', icon: '✓', desc: 'Mark as done' },
    { status: 'unresolved' as const, label: 'Needs work', icon: '⚠', desc: 'Flag for attention' },
  ];
  
  options.forEach(opt => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `factor-status-option ${opt.status === userOverride ? 'selected' : ''}`;
    item.innerHTML = `<span class="opt-icon">${opt.icon}</span><span class="opt-label">${opt.label}</span>`;
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.style.display = 'none';
      onSelect(opt.status);
    });
    menu.appendChild(item);
  });
  
  container.appendChild(menu);
  
  // Close on outside click
  document.addEventListener('click', () => {
    menu.style.display = 'none';
  });
  
  return container;
}

/**
 * Create the FactorCard element
 */
export function FactorCard(props: FactorCardProps): HTMLElement {
  const { factor, isExpanded, onModeSelect, onStepAction, onEvidenceClick, onToggleExpand, onResolve, onAddRemedy } = props;
  
  // Use per-factor override status (from backend factor_overrides)
  // "resolved" = user marked as done, "unresolved" = user flagged as needing work
  const userOverride = factor.user_override;  // 'resolved' | 'unresolved' | null
  const isUserResolved = userOverride === 'resolved';
  const isUserFlagged = userOverride === 'unresolved';
  
  const card = document.createElement('div');
  card.className = `factor-card ${getStatusClass(factor.status, userOverride)} ${factor.is_focus ? 'factor-focus' : ''} ${isExpanded ? 'expanded' : 'collapsed'}`;
  card.dataset.factorType = factor.factor_type;
  
  // Header row (always visible)
  const header = document.createElement('div');
  header.className = 'factor-header';
  header.addEventListener('click', () => onToggleExpand(factor.factor_type));
  
  // Status icon
  const statusIcon = document.createElement('span');
  statusIcon.className = 'factor-status-icon';
  statusIcon.textContent = getStatusIcon(factor.status, userOverride);
  header.appendChild(statusIcon);
  
  // Label
  const label = document.createElement('span');
  label.className = 'factor-label';
  label.textContent = factor.label;
  header.appendChild(label);
  
  // Status label - system confidence (always shows system's view)
  const statusLabel = document.createElement('span');
  statusLabel.className = `factor-status-label ${getStatusLabelClass(factor.status)}`;
  statusLabel.textContent = `· ${getSystemConfidenceLabel(factor.status)}`;
  header.appendChild(statusLabel);
  
  // User override badge (separate from system confidence)
  if (isUserResolved) {
    const resolvedBadge = document.createElement('span');
    resolvedBadge.className = 'factor-resolved-badge';
    resolvedBadge.textContent = 'Resolved';
    header.appendChild(resolvedBadge);
  } else if (isUserFlagged) {
    const flaggedBadge = document.createElement('span');
    flaggedBadge.className = 'factor-flagged-badge';
    flaggedBadge.textContent = 'Flagged';
    header.appendChild(flaggedBadge);
  }
  
  // Focus indicator
  if (factor.is_focus) {
    const focusBadge = document.createElement('span');
    focusBadge.className = 'factor-focus-badge';
    focusBadge.textContent = '◀ YOUR FOCUS';
    header.appendChild(focusBadge);
  }
  
  // Status dropdown (Mini-style) - per-factor action
  if (onResolve) {
    const statusDropdown = createStatusDropdown(userOverride, (status) => {
      onResolve(factor.factor_type, status);
    });
    header.appendChild(statusDropdown);
  }
  
  // Mode indicator (if set and not expanded)
  if (factor.mode && !isExpanded) {
    const modeIndicator = document.createElement('span');
    modeIndicator.className = 'factor-mode-indicator';
    modeIndicator.textContent = factor.mode === 'mobius' ? '🤖' : factor.mode === 'together' ? '🤝' : '👤';
    header.appendChild(modeIndicator);
  }
  
  // Expand/collapse icon
  const expandIcon = document.createElement('span');
  expandIcon.className = 'factor-expand-icon';
  expandIcon.textContent = isExpanded ? '▼' : '▶';
  header.appendChild(expandIcon);
  
  card.appendChild(header);
  
  // Expanded content (show for all factors when expanded)
  if (isExpanded) {
    const content = document.createElement('div');
    content.className = 'factor-content';
    
    // Combined recommendation + mode dropdown (compact single line)
    const modeRow = createModeDropdownRow(factor, onModeSelect);
    content.appendChild(modeRow);
    
    // Always show steps when expanded (regardless of mode selection)
    if (factor.steps.length > 0) {
      // Show "Mobius is handling" message if mobius mode is selected
      if (factor.mode === 'mobius') {
        const mobiusStatus = document.createElement('div');
        mobiusStatus.className = 'factor-mobius-status';
        mobiusStatus.innerHTML = `
          <div class="mobius-handling">
            <span class="mobius-icon">🤖</span>
            <span class="mobius-text">Mobius is handling this.</span>
          </div>
          <div class="mobius-notify">You'll be notified when complete.</div>
        `;
        content.appendChild(mobiusStatus);
      }
      // Always show steps (for visibility/transparency)
      const stepsSection = createStepsSection(factor, onStepAction);
      content.appendChild(stepsSection);
    }
    
    // No prompt needed - dropdown makes it clear
    
    // User remedies section
    const remediesSection = createRemediesSection(factor, onAddRemedy);
    content.appendChild(remediesSection);
    
    // Evidence link
    if (factor.evidence_count > 0) {
      const evidenceLink = document.createElement('div');
      evidenceLink.className = 'factor-evidence-link';
      evidenceLink.innerHTML = `<span class="evidence-icon">ⁱ</span> Why these steps? (${factor.evidence_count} facts)`;
      evidenceLink.addEventListener('click', (e) => {
        e.stopPropagation();
        onEvidenceClick(factor.factor_type);
      });
      content.appendChild(evidenceLink);
    }
    
    // Note: Resolve/Reopen is now in the header toggle button
    
    card.appendChild(content);
  }
  
  return card;
}

/**
 * Get human-readable mode label
 */
function getModeLabel(mode: WorkflowMode | null): string {
  switch (mode) {
    case 'mobius': return 'Let Mobius handle';
    case 'together': return 'Work together';
    case 'manual': return 'I\'ll do it';
    default: return 'Select mode';
  }
}

/**
 * Create compact mode dropdown row with recommendation
 */
function createModeDropdownRow(factor: Factor, onModeSelect: (factorType: string, mode: WorkflowMode) => void): HTMLElement {
  const row = document.createElement('div');
  row.className = 'factor-mode-row';
  
  // Recommendation hint (if available) - bolder, explains success rate
  if (factor.recommendation) {
    const hint = document.createElement('span');
    hint.className = 'factor-mode-hint';
    const successRate = Math.round(factor.recommendation.confidence * 100);
    hint.innerHTML = `💡 <strong>${getShortModeLabel(factor.recommendation.mode)}</strong> · ${successRate}% success rate`;
    row.appendChild(hint);
  }
  
  // Dropdown container
  const dropdownContainer = document.createElement('div');
  dropdownContainer.className = 'factor-mode-dropdown';
  
  // Current selection button
  const dropdownBtn = document.createElement('button');
  dropdownBtn.className = `factor-mode-dropdown-btn ${factor.mode ? 'has-selection' : ''}`;
  dropdownBtn.innerHTML = factor.mode 
    ? `${getModeIcon(factor.mode)} ${getShortModeLabel(factor.mode)} <span class="dropdown-arrow">▾</span>`
    : `Select <span class="dropdown-arrow">▾</span>`;
  
  // Dropdown menu
  const dropdownMenu = document.createElement('div');
  dropdownMenu.className = 'factor-mode-dropdown-menu';
  dropdownMenu.style.display = 'none';
  
  const modes: { mode: WorkflowMode; icon: string; label: string }[] = [
    { mode: 'mobius', icon: '🤖', label: 'Mobius handles' },
    { mode: 'manual', icon: '👤', label: 'I\'ll handle' },
  ];
  
  for (const m of modes) {
    const option = document.createElement('div');
    option.className = `factor-mode-option ${factor.mode === m.mode ? 'selected' : ''} ${factor.recommendation?.mode === m.mode ? 'recommended' : ''}`;
    option.innerHTML = `${m.icon} ${m.label}`;
    option.addEventListener('click', (e) => {
      e.stopPropagation();
      onModeSelect(factor.factor_type, m.mode);
      dropdownMenu.style.display = 'none';
    });
    dropdownMenu.appendChild(option);
  }
  
  // Toggle dropdown
  dropdownBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = dropdownMenu.style.display !== 'none';
    dropdownMenu.style.display = isOpen ? 'none' : 'block';
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', () => {
    dropdownMenu.style.display = 'none';
  });
  
  dropdownContainer.appendChild(dropdownBtn);
  dropdownContainer.appendChild(dropdownMenu);
  row.appendChild(dropdownContainer);
  
  return row;
}

/**
 * Get mode icon
 */
function getModeIcon(mode: WorkflowMode | null): string {
  switch (mode) {
    case 'mobius': return '🤖';
    case 'manual': return '👤';
    default: return '';
  }
}

/**
 * Get short mode label for dropdown
 */
function getShortModeLabel(mode: WorkflowMode | null): string {
  switch (mode) {
    case 'mobius': return 'Mobius';
    case 'manual': return 'User';
    default: return 'Select';
  }
}

/**
 * Create override/resolve row (same pattern as Mini)
 */
function createOverrideRow(factor: Factor, onResolve: (factorType: string, status: 'resolved' | 'unresolved') => void): HTMLElement {
  const row = document.createElement('div');
  row.className = 'factor-override-row';
  
  // If already user-overridden, show "Undo" option
  if (factor.user_override) {
    const undoBtn = document.createElement('button');
    undoBtn.className = 'factor-override-btn factor-override-undo';
    undoBtn.innerHTML = '↩ Undo override';
    undoBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      onResolve(factor.factor_type, 'unresolved');
    });
    row.appendChild(undoBtn);
  } else {
    // Show resolve option
    const resolveBtn = document.createElement('button');
    resolveBtn.className = 'factor-override-btn factor-override-resolve';
    resolveBtn.innerHTML = '✓ Mark resolved';
    resolveBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      onResolve(factor.factor_type, 'resolved');
    });
    row.appendChild(resolveBtn);
  }
  
  return row;
}

/**
 * Create steps section based on mode
 */
function createStepsSection(factor: Factor, onStepAction: (stepId: string, action: 'done' | 'skip' | 'delegate', answerCode?: string) => void): HTMLElement {
  const section = document.createElement('div');
  section.className = 'factor-steps';
  
  factor.steps.forEach((step, index) => {
    const stepEl = createStepElement(step, factor.mode, onStepAction, index + 1);
    section.appendChild(stepEl);
  });
  
  return section;
}

/**
 * Create a single step element (compact single-line layout)
 */
function createStepElement(step: FactorStep, mode: WorkflowMode | null, onStepAction: (stepId: string, action: 'done' | 'skip' | 'delegate', answerCode?: string) => void, stepNumber?: number): HTMLElement {
  const el = document.createElement('div');
  el.className = `factor-step step-${step.status}`;
  
  // Left side: number + icon + label
  const left = document.createElement('div');
  left.className = 'step-left';
  
  // Step number (1, 2, 3...)
  if (stepNumber) {
    const numEl = document.createElement('span');
    numEl.className = 'step-number';
    numEl.textContent = `${stepNumber}.`;
    left.appendChild(numEl);
  }
  
  // Assignee icon
  const icon = document.createElement('span');
  icon.className = 'step-icon';
  icon.textContent = step.assignee_icon;
  left.appendChild(icon);
  
  // Step label
  const label = document.createElement('span');
  label.className = 'step-label';
  label.textContent = step.label;
  left.appendChild(label);
  
  el.appendChild(left);
  
  // Right side: status or action buttons
  const right = document.createElement('div');
  right.className = 'step-right';
  
  // Action buttons (show for user's turn when not in mobius mode)
  if (step.is_user_turn && mode !== 'mobius') {
    // Done button with answer options dropdown
    const doneContainer = document.createElement('div');
    doneContainer.className = 'step-done-container';
    
    const doneBtn = document.createElement('button');
    doneBtn.className = 'step-btn done-btn';
    doneBtn.textContent = 'Done ▾';
    
    // Create answer options dropdown
    const answerMenu = document.createElement('div');
    answerMenu.className = 'step-answer-menu';
    answerMenu.style.display = 'none';
    
    if (step.answer_options && step.answer_options.length > 0) {
      // Show predefined options
      for (const opt of step.answer_options) {
        const optEl = document.createElement('div');
        optEl.className = 'step-answer-option';
        optEl.textContent = opt.label;
        optEl.addEventListener('click', (e) => {
          e.stopPropagation();
          answerMenu.style.display = 'none';
          onStepAction(step.step_id, 'done', opt.code);
        });
        answerMenu.appendChild(optEl);
      }
    } else {
      // No options - just confirm
      const confirmEl = document.createElement('div');
      confirmEl.className = 'step-answer-option';
      confirmEl.textContent = '✓ Mark complete';
      confirmEl.addEventListener('click', (e) => {
        e.stopPropagation();
        answerMenu.style.display = 'none';
        onStepAction(step.step_id, 'done', 'completed');
      });
      answerMenu.appendChild(confirmEl);
    }
    
    doneBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = answerMenu.style.display !== 'none';
      answerMenu.style.display = isOpen ? 'none' : 'block';
    });
    
    // Close on outside click
    document.addEventListener('click', () => {
      answerMenu.style.display = 'none';
    });
    
    doneContainer.appendChild(doneBtn);
    doneContainer.appendChild(answerMenu);
    right.appendChild(doneContainer);
    
    const skipBtn = document.createElement('button');
    skipBtn.className = 'step-btn skip-btn';
    skipBtn.textContent = 'Skip';
    skipBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      onStepAction(step.step_id, 'skip');
    });
    right.appendChild(skipBtn);
    
    // Delegate button when system can handle (in User mode or no mode)
    if ((mode === 'manual' || !mode) && step.can_system_handle) {
      const delegateBtn = document.createElement('button');
      delegateBtn.className = 'step-btn delegate-btn';
      delegateBtn.textContent = '→ Mobius';
      delegateBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        onStepAction(step.step_id, 'delegate');
      });
      right.appendChild(delegateBtn);
    }
  } else {
    // Status indicator (when no action buttons)
    const status = document.createElement('span');
    status.className = `step-status step-status-${step.status}`;
    
    if (step.status === 'done' || step.status === 'answered') {
      // Show the actual answer the user selected
      if (step.selected_answer_label) {
        status.textContent = `✓ ${step.selected_answer_label}`;
        status.title = step.selected_answer_label;  // Full text on hover
      } else {
        status.textContent = '✓ Done';
      }
    } else if (step.status === 'skipped') {
      status.textContent = '⊘ Skipped';
    } else if (mode === 'mobius') {
      status.textContent = '🤖 Mobius';
    } else {
      status.textContent = '○';
    }
    right.appendChild(status);
  }
  
  el.appendChild(right);
  
  return el;
}

/**
 * Create remedies section with "+" button and existing remedies
 */
function createRemediesSection(
  factor: Factor,
  onAddRemedy?: (factorType: string, remedyText: string, outcome: 'worked' | 'partial' | 'failed', notes?: string) => void
): HTMLElement {
  const section = document.createElement('div');
  section.className = 'factor-remedies';
  
  // Show existing remedies (if any)
  if (factor.remedies && factor.remedies.length > 0) {
    const remediesList = document.createElement('div');
    remediesList.className = 'remedies-list';
    
    for (const remedy of factor.remedies) {
      const remedyEl = document.createElement('div');
      remedyEl.className = `remedy-item remedy-${remedy.outcome}`;
      
      // Outcome icon
      const outcomeIcon = remedy.outcome === 'worked' ? '✓' : remedy.outcome === 'partial' ? '◐' : '✗';
      
      remedyEl.innerHTML = `
        <span class="remedy-icon">${outcomeIcon}</span>
        <span class="remedy-text">${remedy.remedy_text}</span>
        ${remedy.outcome_notes ? `<span class="remedy-notes">${remedy.outcome_notes}</span>` : ''}
      `;
      remediesList.appendChild(remedyEl);
    }
    section.appendChild(remediesList);
  }
  
  // Add remedy button/form
  if (onAddRemedy) {
    const addRow = document.createElement('div');
    addRow.className = 'remedy-add-row';
    
    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'remedy-add-btn';
    addBtn.textContent = '+ Add what I tried';
    
    // Form (hidden by default)
    const form = document.createElement('div');
    form.className = 'remedy-form';
    form.style.display = 'none';
    
    const textInput = document.createElement('input');
    textInput.type = 'text';
    textInput.className = 'remedy-input';
    textInput.placeholder = 'What did you try?';
    
    const outcomeSelect = document.createElement('div');
    outcomeSelect.className = 'remedy-outcomes';
    
    const outcomes = [
      { value: 'worked' as const, label: 'Worked', icon: '✓' },
      { value: 'partial' as const, label: 'Partial', icon: '◐' },
      { value: 'failed' as const, label: 'Failed', icon: '✗' },
    ];
    
    let selectedOutcome: 'worked' | 'partial' | 'failed' | null = null;
    
    outcomes.forEach(o => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'outcome-btn';
      btn.dataset.outcome = o.value;
      btn.innerHTML = `<span class="outcome-icon">${o.icon}</span>${o.label}`;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        // Deselect others
        outcomeSelect.querySelectorAll('.outcome-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        selectedOutcome = o.value;
      });
      outcomeSelect.appendChild(btn);
    });
    
    const notesInput = document.createElement('input');
    notesInput.type = 'text';
    notesInput.className = 'remedy-notes-input';
    notesInput.placeholder = 'Optional notes...';
    
    const submitBtn = document.createElement('button');
    submitBtn.type = 'button';
    submitBtn.className = 'remedy-submit-btn';
    submitBtn.textContent = 'Save';
    submitBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const remedyText = textInput.value.trim();
      if (remedyText && selectedOutcome) {
        onAddRemedy(factor.factor_type, remedyText, selectedOutcome, notesInput.value.trim() || undefined);
        // Reset form
        textInput.value = '';
        notesInput.value = '';
        selectedOutcome = null;
        outcomeSelect.querySelectorAll('.outcome-btn').forEach(b => b.classList.remove('selected'));
        form.style.display = 'none';
        addBtn.style.display = 'block';
      }
    });
    
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'remedy-cancel-btn';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      form.style.display = 'none';
      addBtn.style.display = 'block';
    });
    
    const btnRow = document.createElement('div');
    btnRow.className = 'remedy-btn-row';
    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(submitBtn);
    
    form.appendChild(textInput);
    form.appendChild(outcomeSelect);
    form.appendChild(notesInput);
    form.appendChild(btnRow);
    
    addBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      addBtn.style.display = 'none';
      form.style.display = 'block';
      textInput.focus();
    });
    
    addRow.appendChild(addBtn);
    addRow.appendChild(form);
    section.appendChild(addRow);
  }
  
  return section;
}
