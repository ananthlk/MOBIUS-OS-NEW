/**
 * Tooltips Module for Mobius OS
 * 
 * Centralized tooltip definitions and utilities for Mini and Sidecar UI.
 * This module can be imported wherever tooltips are needed without
 * modifying existing component logic.
 * 
 * Usage:
 *   import { applyTooltip, initTooltipStyles, TOOLTIP_DEFINITIONS } from './tooltips';
 *   applyTooltip(element, 'status-resolved');
 *   // or
 *   element.dataset.mobiusTooltip = 'status-resolved';
 */

// =============================================================================
// Tooltip Definitions
// =============================================================================

export interface TooltipDefinition {
  /** Short title for the tooltip */
  title: string;
  /** Longer description (optional) */
  description?: string;
  /** Associated icon (for reference) */
  icon?: string;
  /** Color indicator class */
  colorClass?: string;
}

/**
 * All tooltip definitions organized by category
 */
export const TOOLTIP_DEFINITIONS: Record<string, TooltipDefinition> = {
  // ---------------------------------------------------------------------------
  // Factor/Step Status Icons
  // ---------------------------------------------------------------------------
  'status-resolved': {
    title: 'Resolved',
    description: 'This item has been completed successfully.',
    icon: '✓',
    colorClass: 'tooltip-green',
  },
  'status-blocked': {
    title: 'Needs Attention',
    description: 'This item requires action before proceeding.',
    icon: '⚠️',
    colorClass: 'tooltip-yellow',
  },
  'status-waiting': {
    title: 'In Progress',
    description: 'Waiting for a response or external action.',
    icon: '◯',
    colorClass: 'tooltip-blue',
  },
  'status-pending': {
    title: 'Pending',
    description: 'Not yet started.',
    icon: '○',
    colorClass: 'tooltip-grey',
  },
  
  // ---------------------------------------------------------------------------
  // User Override Status
  // ---------------------------------------------------------------------------
  'user-resolved': {
    title: 'Marked as Resolved',
    description: 'You marked this as done. The system may still monitor it.',
    icon: '✓',
    colorClass: 'tooltip-green',
  },
  'user-flagged': {
    title: 'Flagged for Attention',
    description: 'You flagged this as needing work.',
    icon: '⚠',
    colorClass: 'tooltip-orange',
  },
  
  // ---------------------------------------------------------------------------
  // Workflow Mode Icons
  // ---------------------------------------------------------------------------
  'mode-mobius': {
    title: 'Mobius Handles',
    description: 'Mobius will automatically complete this task. You\'ll be notified when done.',
    icon: '🤖',
    colorClass: 'tooltip-purple',
  },
  'mode-together': {
    title: 'Work Together',
    description: 'Collaborate with Mobius on this task.',
    icon: '🤝',
    colorClass: 'tooltip-blue',
  },
  'mode-manual': {
    title: 'You Handle',
    description: 'You\'ll complete this task yourself.',
    icon: '👤',
    colorClass: 'tooltip-grey',
  },
  
  // ---------------------------------------------------------------------------
  // Step Actions
  // ---------------------------------------------------------------------------
  'action-done': {
    title: 'Mark as Done',
    description: 'Complete this step and record the outcome.',
    icon: '✓',
  },
  'action-skip': {
    title: 'Skip Step',
    description: 'Skip this step if not applicable.',
    icon: '⊘',
  },
  'action-delegate': {
    title: 'Delegate to Mobius',
    description: 'Let Mobius handle this step automatically.',
    icon: '→',
  },
  
  // ---------------------------------------------------------------------------
  // Remedy Outcomes
  // ---------------------------------------------------------------------------
  'remedy-worked': {
    title: 'Worked',
    description: 'This remedy resolved the issue.',
    icon: '✓',
    colorClass: 'tooltip-green',
  },
  'remedy-partial': {
    title: 'Partially Worked',
    description: 'This remedy helped but didn\'t fully resolve the issue.',
    icon: '◐',
    colorClass: 'tooltip-yellow',
  },
  'remedy-failed': {
    title: 'Did Not Work',
    description: 'This remedy did not resolve the issue.',
    icon: '✗',
    colorClass: 'tooltip-red',
  },
  
  // ---------------------------------------------------------------------------
  // Care Readiness / Progress
  // ---------------------------------------------------------------------------
  'readiness-high': {
    title: 'Ready for Care',
    description: 'Patient is ready for affordable care. All critical factors resolved.',
    colorClass: 'tooltip-green',
  },
  'readiness-medium': {
    title: 'Almost Ready',
    description: 'Most factors resolved. A few items need attention.',
    colorClass: 'tooltip-yellow',
  },
  'readiness-low': {
    title: 'Needs Work',
    description: 'Several factors need resolution before care can proceed.',
    colorClass: 'tooltip-orange',
  },
  'readiness-starting': {
    title: 'Getting Started',
    description: 'Beginning the care preparation journey.',
    colorClass: 'tooltip-grey',
  },
  'direction-improving': {
    title: 'Improving',
    description: 'Care readiness is trending upward.',
    icon: '↑',
    colorClass: 'tooltip-green',
  },
  'direction-declining': {
    title: 'Needs Attention',
    description: 'Care readiness has decreased. Review recent changes.',
    icon: '↓',
    colorClass: 'tooltip-red',
  },
  'direction-stable': {
    title: 'Stable',
    description: 'Care readiness is holding steady.',
    icon: '→',
    colorClass: 'tooltip-blue',
  },
  
  // ---------------------------------------------------------------------------
  // Alert Indicators
  // ---------------------------------------------------------------------------
  'alert-bell': {
    title: 'Alerts',
    description: 'Click to view notifications and updates.',
    icon: '🔔',
  },
  'alert-high-priority': {
    title: 'High Priority Alert',
    description: 'Urgent items require your attention.',
    colorClass: 'tooltip-red',
  },
  'alert-win': {
    title: 'Success!',
    description: 'A task was completed successfully.',
    colorClass: 'tooltip-green',
  },
  'alert-update': {
    title: 'Update',
    description: 'New information is available.',
    colorClass: 'tooltip-blue',
  },
  'alert-reminder': {
    title: 'Reminder',
    description: 'A follow-up is needed.',
    colorClass: 'tooltip-yellow',
  },
  
  // ---------------------------------------------------------------------------
  // Proceed Indicator Colors
  // ---------------------------------------------------------------------------
  'proceed-green': {
    title: 'Good to Proceed',
    description: 'No blockers detected. Care can proceed.',
    colorClass: 'tooltip-green',
  },
  'proceed-yellow': {
    title: 'Review Needed',
    description: 'Some items may need attention before proceeding.',
    colorClass: 'tooltip-yellow',
  },
  'proceed-red': {
    title: 'Blocked',
    description: 'Critical issues must be resolved before proceeding.',
    colorClass: 'tooltip-red',
  },
  'proceed-blue': {
    title: 'In Progress',
    description: 'Work is ongoing.',
    colorClass: 'tooltip-blue',
  },
  'proceed-grey': {
    title: 'Unknown',
    description: 'Status is being determined.',
    colorClass: 'tooltip-grey',
  },
  
  // ---------------------------------------------------------------------------
  // Factor Focus
  // ---------------------------------------------------------------------------
  'factor-focus': {
    title: 'Your Focus',
    description: 'This factor is recommended for your role and should be addressed first.',
    icon: '◀',
    colorClass: 'tooltip-purple',
  },
  
  // ---------------------------------------------------------------------------
  // Evidence / Information
  // ---------------------------------------------------------------------------
  'evidence-link': {
    title: 'View Evidence',
    description: 'See the facts and data behind these recommendations.',
    icon: 'ⁱ',
  },
  
  // ---------------------------------------------------------------------------
  // System Confidence Labels
  // ---------------------------------------------------------------------------
  'confidence-looks-good': {
    title: 'Looks Good',
    description: 'System is confident this factor is resolved.',
    colorClass: 'tooltip-green',
  },
  'confidence-needs-help': {
    title: 'Needs Your Help',
    description: 'System detected an issue that requires human action.',
    colorClass: 'tooltip-orange',
  },
  'confidence-almost-there': {
    title: 'Almost There',
    description: 'Waiting for external confirmation or response.',
    colorClass: 'tooltip-yellow',
  },
  
  // ---------------------------------------------------------------------------
  // Mini-specific
  // ---------------------------------------------------------------------------
  'mini-greeting-dismiss': {
    title: 'Hide Greeting',
    description: 'Dismiss this greeting. You can re-enable it in preferences.',
  },
  'mini-chevron': {
    title: 'User Menu',
    description: 'Click for user options, preferences, and sign out.',
  },
  'mini-settings': {
    title: 'Settings',
    description: 'Open Mobius preferences and configuration.',
  },
  
  // ---------------------------------------------------------------------------
  // Assignee Icons
  // ---------------------------------------------------------------------------
  'assignee-mobius': {
    title: 'Assigned to Mobius',
    description: 'Mobius will handle this step.',
    icon: '🤖',
    colorClass: 'tooltip-purple',
  },
  'assignee-user': {
    title: 'Assigned to You',
    description: 'This step requires your action.',
    icon: '👤',
    colorClass: 'tooltip-blue',
  },
};


// =============================================================================
// Tooltip Application Functions
// =============================================================================

/**
 * Apply a tooltip to an HTML element
 * Uses data attributes for CSS-based tooltips
 */
export function applyTooltip(element: HTMLElement, tooltipKey: string): void {
  const def = TOOLTIP_DEFINITIONS[tooltipKey];
  if (!def) {
    console.warn(`[Tooltips] Unknown tooltip key: ${tooltipKey}`);
    return;
  }
  
  element.dataset.mobiusTooltip = def.title;
  if (def.description) {
    element.dataset.mobiusTooltipDesc = def.description;
  }
  if (def.colorClass) {
    element.dataset.mobiusTooltipColor = def.colorClass;
  }
  
  // Add the tooltip class for styling
  element.classList.add('has-mobius-tooltip');
}

/**
 * Apply tooltip directly with custom text (for dynamic content)
 */
export function applyCustomTooltip(
  element: HTMLElement, 
  title: string, 
  description?: string,
  colorClass?: string
): void {
  element.dataset.mobiusTooltip = title;
  if (description) {
    element.dataset.mobiusTooltipDesc = description;
  }
  if (colorClass) {
    element.dataset.mobiusTooltipColor = colorClass;
  }
  element.classList.add('has-mobius-tooltip');
}

/**
 * Remove tooltip from an element
 */
export function removeTooltip(element: HTMLElement): void {
  delete element.dataset.mobiusTooltip;
  delete element.dataset.mobiusTooltipDesc;
  delete element.dataset.mobiusTooltipColor;
  element.classList.remove('has-mobius-tooltip');
}

/**
 * Get tooltip text for a key (useful for native title attributes)
 */
export function getTooltipText(tooltipKey: string): string {
  const def = TOOLTIP_DEFINITIONS[tooltipKey];
  if (!def) return '';
  return def.description ? `${def.title}: ${def.description}` : def.title;
}


// =============================================================================
// Batch Tooltip Application (for existing UIs)
// =============================================================================

/**
 * Auto-apply tooltips to elements with data-tooltip-key attribute
 * Call this after rendering components
 */
export function applyTooltipsInContainer(container: HTMLElement): void {
  const elements = container.querySelectorAll('[data-tooltip-key]');
  elements.forEach((el) => {
    const key = (el as HTMLElement).dataset.tooltipKey;
    if (key) {
      applyTooltip(el as HTMLElement, key);
    }
  });
}

/**
 * Apply tooltips to common UI patterns within a container
 * This function looks for known CSS classes and applies appropriate tooltips
 */
export function applyAutoTooltips(container: HTMLElement): void {
  // Factor status icons
  container.querySelectorAll('.factor-status-icon').forEach((el) => {
    const text = el.textContent?.trim();
    if (text === '✓') applyTooltip(el as HTMLElement, 'status-resolved');
    else if (text === '⚠️' || text === '⚠') applyTooltip(el as HTMLElement, 'status-blocked');
    else if (text === '◯') applyTooltip(el as HTMLElement, 'status-waiting');
    else if (text === '○') applyTooltip(el as HTMLElement, 'status-pending');
  });
  
  // Mode indicators
  container.querySelectorAll('.factor-mode-indicator, .step-icon').forEach((el) => {
    const text = el.textContent?.trim();
    if (text === '🤖') applyTooltip(el as HTMLElement, 'mode-mobius');
    else if (text === '🤝') applyTooltip(el as HTMLElement, 'mode-together');
    else if (text === '👤') applyTooltip(el as HTMLElement, 'mode-manual');
  });
  
  // Focus badges
  container.querySelectorAll('.factor-focus-badge').forEach((el) => {
    applyTooltip(el as HTMLElement, 'factor-focus');
  });
  
  // Evidence links
  container.querySelectorAll('.factor-evidence-link').forEach((el) => {
    applyTooltip(el as HTMLElement, 'evidence-link');
  });
  
  // Resolved/Flagged badges
  container.querySelectorAll('.factor-resolved-badge').forEach((el) => {
    applyTooltip(el as HTMLElement, 'user-resolved');
  });
  container.querySelectorAll('.factor-flagged-badge').forEach((el) => {
    applyTooltip(el as HTMLElement, 'user-flagged');
  });
  
  // Step action buttons
  container.querySelectorAll('.done-btn').forEach((el) => {
    applyTooltip(el as HTMLElement, 'action-done');
  });
  container.querySelectorAll('.skip-btn').forEach((el) => {
    applyTooltip(el as HTMLElement, 'action-skip');
  });
  container.querySelectorAll('.delegate-btn').forEach((el) => {
    applyTooltip(el as HTMLElement, 'action-delegate');
  });
  
  // Remedy outcomes
  container.querySelectorAll('.remedy-worked').forEach((el) => {
    applyTooltip(el as HTMLElement, 'remedy-worked');
  });
  container.querySelectorAll('.remedy-partial').forEach((el) => {
    applyTooltip(el as HTMLElement, 'remedy-partial');
  });
  container.querySelectorAll('.remedy-failed').forEach((el) => {
    applyTooltip(el as HTMLElement, 'remedy-failed');
  });
  
  // Alert indicators
  container.querySelectorAll('.sidecar-alert-indicator').forEach((el) => {
    applyTooltip(el as HTMLElement, 'alert-bell');
  });
  container.querySelectorAll('.sidecar-alert-badge--high').forEach((el) => {
    applyTooltip(el as HTMLElement, 'alert-high-priority');
  });
  
  // Status indicators (proceed colors)
  container.querySelectorAll('.status-indicator').forEach((el) => {
    const classList = el.className;
    if (classList.includes('status-green') || classList.includes('status-proceed')) {
      applyTooltip(el as HTMLElement, 'proceed-green');
    } else if (classList.includes('status-yellow') || classList.includes('status-pending')) {
      applyTooltip(el as HTMLElement, 'proceed-yellow');
    } else if (classList.includes('status-red') || classList.includes('status-error')) {
      applyTooltip(el as HTMLElement, 'proceed-red');
    } else if (classList.includes('status-blue')) {
      applyTooltip(el as HTMLElement, 'proceed-blue');
    } else if (classList.includes('status-grey')) {
      applyTooltip(el as HTMLElement, 'proceed-grey');
    }
  });
  
  // Care readiness bar
  container.querySelectorAll('.sidecar-status-bar-marker').forEach((el) => {
    const parent = el.closest('.sidecar-status-bar');
    const percent = parent?.querySelector('.sidecar-status-bar-percent')?.textContent;
    if (percent) {
      const val = parseInt(percent);
      if (val >= 90) applyTooltip(el as HTMLElement, 'readiness-high');
      else if (val >= 70) applyTooltip(el as HTMLElement, 'readiness-medium');
      else if (val >= 30) applyTooltip(el as HTMLElement, 'readiness-low');
      else applyTooltip(el as HTMLElement, 'readiness-starting');
    }
  });
  
  // Mini greeting elements
  container.querySelectorAll('.mobius-mini-greeting-dismiss').forEach((el) => {
    applyTooltip(el as HTMLElement, 'mini-greeting-dismiss');
  });
  container.querySelectorAll('.mobius-mini-greeting-chevron').forEach((el) => {
    applyTooltip(el as HTMLElement, 'mini-chevron');
  });
}


// =============================================================================
// CSS Styles for Tooltips
// =============================================================================

/**
 * CSS styles for the tooltip system
 * Call initTooltipStyles() once to inject these styles
 */
export const TOOLTIP_STYLES = `
/* =============================================================================
   Mobius Tooltip Styles
   ============================================================================= */

/* Base tooltip container */
.has-mobius-tooltip {
  position: relative;
  cursor: help;
}

/* Tooltip pseudo-element */
.has-mobius-tooltip::before,
.has-mobius-tooltip::after {
  position: absolute;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity 0.2s ease, visibility 0.2s ease, transform 0.2s ease;
  z-index: 10000;
}

/* Tooltip arrow */
.has-mobius-tooltip::before {
  content: '';
  border: 6px solid transparent;
  border-top-color: #1e293b;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(4px);
}

/* Tooltip content box */
.has-mobius-tooltip::after {
  content: attr(data-mobius-tooltip);
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  
  /* Styling */
  background: #1e293b;
  color: #f8fafc;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  max-width: 280px;
  text-align: center;
  
  /* Shadow */
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* Show tooltip on hover */
.has-mobius-tooltip:hover::before,
.has-mobius-tooltip:hover::after {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(0);
}

/* Tooltip with description (two-line) */
.has-mobius-tooltip[data-mobius-tooltip-desc]::after {
  content: attr(data-mobius-tooltip) "\\A" attr(data-mobius-tooltip-desc);
  white-space: pre-wrap;
  text-align: left;
  min-width: 180px;
}

/* Color variants - border accent on left */
.has-mobius-tooltip[data-mobius-tooltip-color="tooltip-green"]::after {
  border-left: 3px solid #22c55e;
}

.has-mobius-tooltip[data-mobius-tooltip-color="tooltip-yellow"]::after {
  border-left: 3px solid #eab308;
}

.has-mobius-tooltip[data-mobius-tooltip-color="tooltip-orange"]::after {
  border-left: 3px solid #f97316;
}

.has-mobius-tooltip[data-mobius-tooltip-color="tooltip-red"]::after {
  border-left: 3px solid #ef4444;
}

.has-mobius-tooltip[data-mobius-tooltip-color="tooltip-blue"]::after {
  border-left: 3px solid #3b82f6;
}

.has-mobius-tooltip[data-mobius-tooltip-color="tooltip-purple"]::after {
  border-left: 3px solid #a855f7;
}

.has-mobius-tooltip[data-mobius-tooltip-color="tooltip-grey"]::after {
  border-left: 3px solid #94a3b8;
}

/* Position variants for edge cases */
.has-mobius-tooltip.tooltip-right::before {
  left: auto;
  right: 50%;
  transform: translateX(50%) translateY(4px);
}

.has-mobius-tooltip.tooltip-right::after {
  left: auto;
  right: 0;
  transform: translateX(0) translateY(4px);
}

.has-mobius-tooltip.tooltip-right:hover::before,
.has-mobius-tooltip.tooltip-right:hover::after {
  transform: translateX(0) translateY(0);
}

.has-mobius-tooltip.tooltip-left::before {
  left: 50%;
  right: auto;
  transform: translateX(-50%) translateY(4px);
}

.has-mobius-tooltip.tooltip-left::after {
  left: 0;
  right: auto;
  transform: translateX(0) translateY(4px);
}

.has-mobius-tooltip.tooltip-left:hover::before,
.has-mobius-tooltip.tooltip-left:hover::after {
  transform: translateX(0) translateY(0);
}

/* Bottom position */
.has-mobius-tooltip.tooltip-bottom::before {
  top: 100%;
  bottom: auto;
  border-top-color: transparent;
  border-bottom-color: #1e293b;
  transform: translateX(-50%) translateY(-4px);
}

.has-mobius-tooltip.tooltip-bottom::after {
  top: calc(100% + 8px);
  bottom: auto;
  transform: translateX(-50%) translateY(-4px);
}

.has-mobius-tooltip.tooltip-bottom:hover::before,
.has-mobius-tooltip.tooltip-bottom:hover::after {
  transform: translateX(-50%) translateY(0);
}

/* Disable tooltip on buttons during click (prevents flicker) */
.has-mobius-tooltip:active::before,
.has-mobius-tooltip:active::after {
  opacity: 0;
}

/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .has-mobius-tooltip::before,
  .has-mobius-tooltip::after {
    transition: none;
  }
}

/* Dark mode support (if needed) */
@media (prefers-color-scheme: dark) {
  .has-mobius-tooltip::after {
    background: #334155;
    color: #f1f5f9;
  }
  
  .has-mobius-tooltip::before {
    border-top-color: #334155;
  }
  
  .has-mobius-tooltip.tooltip-bottom::before {
    border-bottom-color: #334155;
  }
}
`;

/**
 * Inject tooltip styles into the document
 * Call this once when initializing the UI
 */
export function initTooltipStyles(): void {
  // Check if already injected
  if (document.getElementById('mobius-tooltip-styles')) {
    return;
  }
  
  const style = document.createElement('style');
  style.id = 'mobius-tooltip-styles';
  style.textContent = TOOLTIP_STYLES;
  document.head.appendChild(style);
}

/**
 * Inject tooltip styles into a shadow DOM root
 * Use this if components are in shadow DOM
 */
export function initTooltipStylesInShadow(shadowRoot: ShadowRoot): void {
  const style = document.createElement('style');
  style.textContent = TOOLTIP_STYLES;
  shadowRoot.appendChild(style);
}


// =============================================================================
// Utility: Create Tooltip Map for Quick Access
// =============================================================================

/**
 * Helper to get tooltip by status/mode for dynamic content
 */
export function getStatusTooltipKey(status: string, userOverride?: string | null): string {
  if (userOverride === 'resolved') return 'user-resolved';
  if (userOverride === 'unresolved') return 'user-flagged';
  
  switch (status) {
    case 'resolved': return 'status-resolved';
    case 'blocked': return 'status-blocked';
    case 'waiting': return 'status-waiting';
    default: return 'status-pending';
  }
}

export function getModeTooltipKey(mode: string | null): string {
  switch (mode) {
    case 'mobius': return 'mode-mobius';
    case 'together': return 'mode-together';
    case 'manual': return 'mode-manual';
    default: return 'mode-manual';
  }
}

export function getRemedyTooltipKey(outcome: string): string {
  switch (outcome) {
    case 'worked': return 'remedy-worked';
    case 'partial': return 'remedy-partial';
    case 'failed': return 'remedy-failed';
    default: return 'remedy-partial';
  }
}

export function getProceedTooltipKey(color: string): string {
  switch (color.toLowerCase()) {
    case 'green': return 'proceed-green';
    case 'yellow': return 'proceed-yellow';
    case 'red': return 'proceed-red';
    case 'blue': return 'proceed-blue';
    default: return 'proceed-grey';
  }
}

export function getReadinessTooltipKey(position: number): string {
  if (position >= 90) return 'readiness-high';
  if (position >= 70) return 'readiness-medium';
  if (position >= 30) return 'readiness-low';
  return 'readiness-starting';
}

export function getDirectionTooltipKey(direction: string): string {
  switch (direction) {
    case 'improving': return 'direction-improving';
    case 'declining': return 'direction-declining';
    default: return 'direction-stable';
  }
}


// =============================================================================
// Automatic Tooltip Observer
// =============================================================================

/**
 * Store for active observers (to prevent duplicates)
 */
const activeObservers = new WeakMap<HTMLElement, MutationObserver>();

/**
 * Start observing a container for DOM changes and auto-apply tooltips
 * This is useful for components that re-render dynamically (like FactorList)
 */
export function observeTooltips(container: HTMLElement): void {
  // Don't create duplicate observers
  if (activeObservers.has(container)) {
    return;
  }
  
  // Apply tooltips initially
  applyAutoTooltips(container);
  
  // Create observer
  const observer = new MutationObserver((mutations) => {
    // Debounce: only process if there were actual changes
    let hasRelevantChanges = false;
    for (const mutation of mutations) {
      if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
        hasRelevantChanges = true;
        break;
      }
    }
    
    if (hasRelevantChanges) {
      // Re-apply tooltips when DOM changes
      applyAutoTooltips(container);
    }
  });
  
  // Start observing
  observer.observe(container, {
    childList: true,
    subtree: true,
  });
  
  // Store reference
  activeObservers.set(container, observer);
}

/**
 * Stop observing a container
 */
export function stopObservingTooltips(container: HTMLElement): void {
  const observer = activeObservers.get(container);
  if (observer) {
    observer.disconnect();
    activeObservers.delete(container);
  }
}

/**
 * Initialize tooltips with automatic observation for a container
 * This is the recommended all-in-one setup function
 * 
 * Usage:
 *   import { setupTooltips } from './services/tooltips';
 *   setupTooltips(sidebarContainer);
 */
export function setupTooltips(container: HTMLElement): void {
  initTooltipStyles();
  observeTooltips(container);
}
