/**
 * QuickActionButton Component
 * Context-aware quick action button
 */

export interface QuickActionButtonProps {
  label: string;
  onClick: () => void;
  actionType?: string;
}

export function QuickActionButton({ label, onClick }: QuickActionButtonProps): HTMLElement {
  const button = document.createElement('button');
  button.className = 'quick-action-btn';
  button.textContent = label;
  button.addEventListener('click', onClick);
  return button;
}
