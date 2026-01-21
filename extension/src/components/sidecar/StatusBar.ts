/**
 * StatusBar Component
 * 
 * Modern, minimal status indicator showing current care readiness.
 * Simple mono-grey gradient with position marker.
 */

import type { CareReadiness } from '../../types/record';

export interface StatusBarProps {
  careReadiness: CareReadiness;
}

/**
 * Create the StatusBar element
 */
export function StatusBar({ careReadiness }: StatusBarProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'sidecar-status-bar';
  
  const currentPosition = careReadiness.position;
  
  // Title row
  const titleRow = document.createElement('div');
  titleRow.className = 'sidecar-status-bar-title-row';
  
  const title = document.createElement('div');
  title.className = 'sidecar-status-bar-title';
  title.textContent = 'Care Readiness';
  titleRow.appendChild(title);
  
  // Status text - patient-focused
  const context = document.createElement('div');
  context.className = 'sidecar-status-bar-context';
  context.textContent = getStatusText(currentPosition, careReadiness.direction);
  titleRow.appendChild(context);
  
  container.appendChild(titleRow);
  
  // Progress row with track and percentage
  const progressRow = document.createElement('div');
  progressRow.className = 'sidecar-status-bar-progress-row';
  
  // Track wrapper for positioning
  const trackWrapper = document.createElement('div');
  trackWrapper.className = 'sidecar-status-bar-track-wrapper';
  
  // Gradient track
  const track = document.createElement('div');
  track.className = 'sidecar-status-bar-track';
  
  // Progress fill (from left to current position)
  const progressFill = document.createElement('div');
  progressFill.className = 'sidecar-status-bar-progress';
  progressFill.style.width = `${currentPosition}%`;
  track.appendChild(progressFill);
  
  // Current position marker
  const marker = document.createElement('div');
  marker.className = 'sidecar-status-bar-marker';
  marker.style.left = `${currentPosition}%`;
  track.appendChild(marker);
  
  trackWrapper.appendChild(track);
  progressRow.appendChild(trackWrapper);
  
  // Percentage label
  const percentLabel = document.createElement('div');
  percentLabel.className = 'sidecar-status-bar-percent';
  percentLabel.textContent = `${Math.round(currentPosition)}%`;
  progressRow.appendChild(percentLabel);
  
  container.appendChild(progressRow);
  
  // Tooltip with details
  container.title = buildTooltip(careReadiness);
  
  return container;
}

/**
 * Get patient-focused status text based on position
 */
function getStatusText(position: number, direction: string): string {
  if (position >= 90) {
    return 'Ready for affordable care';
  }
  if (position >= 70) {
    return 'Enabling affordable care';
  }
  if (position >= 50) {
    return 'Securing care access';
  }
  if (position >= 30) {
    return 'Preparing care pathway';
  }
  return 'Starting care journey';
}

/**
 * Build tooltip text
 */
function buildTooltip(careReadiness: CareReadiness): string {
  const lines: string[] = [];
  
  lines.push(`Care Readiness: ${Math.round(careReadiness.position)}%`);
  
  // Add factor summary if available
  const factors = careReadiness.factors;
  const completed = Object.values(factors).filter(f => f.status === 'complete').length;
  const total = Object.values(factors).length;
  
  if (total > 0) {
    lines.push(`${completed}/${total} milestones complete`);
  }
  
  if (careReadiness.direction === 'improving') {
    lines.push('↑ Improving');
  } else if (careReadiness.direction === 'declining') {
    lines.push('↓ Needs attention');
  }
  
  return lines.join('\n');
}

/**
 * Update the StatusBar with new data
 */
export function updateStatusBar(element: HTMLElement, careReadiness: CareReadiness): void {
  // Update marker position
  const marker = element.querySelector('.sidecar-status-bar-marker') as HTMLElement;
  if (marker) {
    marker.style.left = `${careReadiness.position}%`;
  }
  
  // Update progress fill
  const progressFill = element.querySelector('.sidecar-status-bar-progress') as HTMLElement;
  if (progressFill) {
    progressFill.style.width = `${careReadiness.position}%`;
  }
  
  // Update context text
  const context = element.querySelector('.sidecar-status-bar-context');
  if (context) {
    context.textContent = getStatusText(careReadiness.position, careReadiness.direction);
  }
  
  // Update percentage
  const percentLabel = element.querySelector('.sidecar-status-bar-percent');
  if (percentLabel) {
    percentLabel.textContent = `${Math.round(careReadiness.position)}%`;
  }
  
  element.title = buildTooltip(careReadiness);
}
