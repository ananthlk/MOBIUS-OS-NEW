/**
 * GuidanceActions Component
 * Context-aware action buttons (Next Steps)
 */

import { GuidanceAction } from '../../types';

export interface GuidanceActionsProps {
  actions: GuidanceAction[];
  isVisible?: boolean;
}

export function GuidanceActions({ actions, isVisible = true }: GuidanceActionsProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'guidance-actions';
  if (!isVisible) {
    container.style.display = 'none';
  }
  
  actions.forEach(action => {
    const button = document.createElement('button');
    button.className = 'guidance-action-btn';
    button.textContent = action.label;
    button.addEventListener('click', action.onClick);
    container.appendChild(button);
  });
  
  return container;
}
