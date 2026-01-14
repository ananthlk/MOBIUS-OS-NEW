/**
 * SettingsButton Component
 * Opens settings panel
 */

export interface SettingsButtonProps {
  onClick: () => void;
}

export function SettingsButton({ onClick }: SettingsButtonProps): HTMLElement {
  const button = document.createElement('button');
  button.className = 'settings-btn';
  button.textContent = '⚙️';
  button.title = 'Settings';
  button.addEventListener('click', onClick);
  return button;
}
