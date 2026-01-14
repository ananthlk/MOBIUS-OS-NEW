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
    button.textContent = action.label;
    button.addEventListener('click', action.onClick);
    container.appendChild(button);
  });
  
  const toggle = document.createElement('span');
  toggle.className = 'guidance-toggle';
  toggle.textContent = 'Hide guidance';
  toggle.addEventListener('click', () => {
    if (container.style.display === 'none') {
      container.style.display = 'flex';
      toggle.textContent = 'Hide guidance';
    } else {
      container.style.display = 'none';
      toggle.textContent = 'Show guidance';
    }
  });
  
  container.appendChild(toggle);
  
  return container;
}
