/**
 * ModeBadge Component
 * Displays current browser/workflow mode
 */

export interface ModeBadgeProps {
  mode: string;
}

export function ModeBadge({ mode }: ModeBadgeProps): HTMLElement {
  const badge = document.createElement('span');
  badge.className = 'mode-badge';
  badge.textContent = mode;
  return badge;
}
