/**
 * ContextDisplay Component
 * Shows current extension context with status and mode
 */

import { StatusIndicator, StatusIndicatorProps } from './StatusIndicator';
import { ModeBadge, ModeBadgeProps } from './ModeBadge';

export interface ContextDisplayProps {
  status: StatusIndicatorProps['status'];
  mode: ModeBadgeProps['mode'];
}

export function ContextDisplay({ status, mode }: ContextDisplayProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'context-display';
  
  container.appendChild(StatusIndicator({ status }));
  container.appendChild(ModeBadge({ mode }));
  
  return container;
}
