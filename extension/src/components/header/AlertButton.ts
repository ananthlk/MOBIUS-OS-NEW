/**
 * AlertButton Component
 * Shows live alerts/notifications
 */

export interface AlertButtonProps {
  hasAlerts: boolean;
  onClick: () => void;
}

export function AlertButton({ hasAlerts, onClick }: AlertButtonProps): HTMLElement {
  const button = document.createElement('button');
  button.className = `alert-btn ${hasAlerts ? 'has-alerts' : ''}`;
  button.title = 'Live Alerts';
  // Use a minimal icon (not a bell) to match the current scheme.
  button.textContent = '◉';
  button.addEventListener('click', onClick);
  return button;
}
