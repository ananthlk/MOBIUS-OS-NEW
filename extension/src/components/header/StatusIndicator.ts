/**
 * StatusIndicator Component
 * Visual status indicator (dot)
 */

import { StatusIndicatorStatus } from '../../types';

export interface StatusIndicatorProps {
  status: StatusIndicatorStatus;
}

export function StatusIndicator({ status }: StatusIndicatorProps): HTMLElement {
  const indicator = document.createElement('span');
  indicator.className = `status-indicator status-${status}`;
  return indicator;
}
