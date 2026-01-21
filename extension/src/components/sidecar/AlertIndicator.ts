/**
 * AlertIndicator Component
 * 
 * Shows count of unread alerts in header.
 * Red dot for high priority items.
 */

import type { Alert } from '../../types/record';

export interface AlertIndicatorProps {
  alerts: Alert[];
  onClick: () => void;
}

/**
 * Create the AlertIndicator element
 */
export function AlertIndicator(props: AlertIndicatorProps): HTMLElement {
  const { alerts, onClick } = props;
  
  const container = document.createElement('button');
  container.className = 'sidecar-alert-indicator';
  container.title = 'View alerts';
  container.addEventListener('click', onClick);
  
  // Bell icon (SVG to match Mini styling)
  const icon = document.createElement('span');
  icon.className = 'sidecar-alert-icon';
  icon.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3c-3.314 0-6 2.686-6 6v3.5l-1.5 2h15L18 12.5V9c0-3.314-2.686-6-6-6z" />
      <path d="M9.5 17a2.5 2.5 0 0 0 5 0" />
    </svg>
  `;
  container.appendChild(icon);
  
  // Count badge
  const unreadCount = alerts.filter(a => !a.read).length;
  if (unreadCount > 0) {
    const badge = document.createElement('span');
    badge.className = 'sidecar-alert-badge';
    badge.textContent = unreadCount > 9 ? '9+' : String(unreadCount);
    container.appendChild(badge);
    
    // High priority dot
    const hasHighPriority = alerts.some(a => !a.read && a.priority === 'high');
    if (hasHighPriority) {
      badge.classList.add('sidecar-alert-badge--high');
    }
  }
  
  return container;
}

/**
 * Update the alert indicator with new counts
 */
export function updateAlertIndicator(element: HTMLElement, alerts: Alert[]): void {
  // Find or create badge
  let badge = element.querySelector('.sidecar-alert-badge') as HTMLElement;
  const unreadCount = alerts.filter(a => !a.read).length;
  
  if (unreadCount === 0) {
    // Remove badge if no unread
    if (badge) badge.remove();
    return;
  }
  
  if (!badge) {
    badge = document.createElement('span');
    badge.className = 'sidecar-alert-badge';
    element.appendChild(badge);
  }
  
  badge.textContent = unreadCount > 9 ? '9+' : String(unreadCount);
  
  // Update high priority status
  const hasHighPriority = alerts.some(a => !a.read && a.priority === 'high');
  badge.classList.toggle('sidecar-alert-badge--high', hasHighPriority);
}

/**
 * Create a simple notification dot (for minimal display)
 */
export function NotificationDot(hasUnread: boolean, hasHighPriority: boolean): HTMLElement {
  const dot = document.createElement('span');
  dot.className = 'sidecar-notification-dot';
  
  if (!hasUnread) {
    dot.style.display = 'none';
  } else if (hasHighPriority) {
    dot.classList.add('sidecar-notification-dot--high');
  }
  
  return dot;
}
