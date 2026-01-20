/**
 * Greeting Row Component for User Awareness Sprint
 * 
 * Shows personalized greeting at the top of Mini widget.
 * Clickable to open user dropdown (switch user, sign out).
 */

export interface GreetingRowProps {
  /** Greeting text (e.g., "Good morning, Sarah") */
  greeting: string;
  /** User display name */
  displayName?: string;
  /** User email */
  email?: string;
  /** Whether user can dismiss the greeting */
  dismissible?: boolean;
  /** Callback when greeting is clicked (opens dropdown) */
  onClick: () => void;
  /** Callback when dismissed */
  onDismiss?: () => void;
}

/**
 * Create the greeting row component
 */
export function GreetingRow(props: GreetingRowProps): HTMLElement {
  const { greeting, displayName, email, dismissible = true, onClick, onDismiss } = props;
  
  const row = document.createElement('div');
  row.className = 'mobius-mini-greeting-row';
  
  // Main greeting (clickable)
  const main = document.createElement('button');
  main.type = 'button';
  main.className = 'mobius-mini-greeting-main';
  main.innerHTML = `
    <span class="mobius-mini-greeting-text">${escapeHtml(greeting)}</span>
    <svg class="mobius-mini-greeting-chevron" viewBox="0 0 24 24" width="14" height="14">
      <path fill="currentColor" d="M7 10l5 5 5-5z"/>
    </svg>
  `;
  main.addEventListener('click', onClick);
  row.appendChild(main);
  
  // Dismiss button (if dismissible)
  if (dismissible && onDismiss) {
    const dismissBtn = document.createElement('button');
    dismissBtn.type = 'button';
    dismissBtn.className = 'mobius-mini-greeting-dismiss';
    dismissBtn.innerHTML = `
      <svg viewBox="0 0 24 24" width="12" height="12">
        <path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
      </svg>
    `;
    dismissBtn.title = 'Hide greeting';
    dismissBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      onDismiss();
    });
    row.appendChild(dismissBtn);
  }
  
  return row;
}

/**
 * Create the user dropdown that appears when clicking greeting
 */
export function UserDropdown(props: {
  displayName?: string;
  email?: string;
  onSignOut: () => void;
  onSwitchUser: () => void;
  onPreferences: () => void;
  onClose: () => void;
}): HTMLElement {
  const { displayName, email, onSignOut, onSwitchUser, onPreferences, onClose } = props;
  
  const dropdown = document.createElement('div');
  dropdown.className = 'mobius-mini-user-dropdown';
  
  dropdown.innerHTML = `
    <div class="mobius-mini-dropdown-header">
      <div class="mobius-mini-dropdown-avatar">
        ${(displayName || email || '?')[0].toUpperCase()}
      </div>
      <div class="mobius-mini-dropdown-info">
        ${displayName ? `<div class="mobius-mini-dropdown-name">${escapeHtml(displayName)}</div>` : ''}
        ${email ? `<div class="mobius-mini-dropdown-email">${escapeHtml(email)}</div>` : ''}
      </div>
    </div>
    <div class="mobius-mini-dropdown-divider"></div>
    <button class="mobius-mini-dropdown-item" data-action="preferences">
      <svg viewBox="0 0 24 24" width="14" height="14">
        <path fill="currentColor" d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
      </svg>
      <span>My Preferences</span>
    </button>
    <button class="mobius-mini-dropdown-item" data-action="switch">
      <svg viewBox="0 0 24 24" width="14" height="14">
        <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
      </svg>
      <span>Not you? Sign in differently</span>
    </button>
    <div class="mobius-mini-dropdown-divider"></div>
    <button class="mobius-mini-dropdown-item mobius-mini-dropdown-signout" data-action="signout">
      <svg viewBox="0 0 24 24" width="14" height="14">
        <path fill="currentColor" d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/>
      </svg>
      <span>Sign out</span>
    </button>
  `;
  
  // Wire up actions
  dropdown.querySelectorAll('.mobius-mini-dropdown-item').forEach(item => {
    item.addEventListener('click', () => {
      const action = (item as HTMLElement).dataset.action;
      switch (action) {
        case 'preferences':
          onPreferences();
          break;
        case 'switch':
          onSwitchUser();
          break;
        case 'signout':
          onSignOut();
          break;
      }
      onClose();
    });
  });
  
  // Close on outside click
  const handleOutsideClick = (e: MouseEvent) => {
    if (!dropdown.contains(e.target as Node)) {
      onClose();
      document.removeEventListener('click', handleOutsideClick);
    }
  };
  setTimeout(() => document.addEventListener('click', handleOutsideClick), 0);
  
  return dropdown;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * CSS styles for greeting row
 */
export const GREETING_ROW_STYLES = `
.mobius-mini-greeting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  background: #f0f9ff;
  border-bottom: 1px solid #e0f2fe;
}

.mobius-mini-greeting-main {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.15s;
}

.mobius-mini-greeting-main:hover {
  background: rgba(59, 130, 246, 0.1);
}

.mobius-mini-greeting-text {
  font-size: 11px;
  font-weight: 500;
  color: #0369a1;
}

.mobius-mini-greeting-chevron {
  color: #0369a1;
  opacity: 0.7;
}

.mobius-mini-greeting-dismiss {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  color: #94a3b8;
  opacity: 0.6;
  transition: all 0.15s;
}

.mobius-mini-greeting-dismiss:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.05);
}

/* User Dropdown */
.mobius-mini-user-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  overflow: hidden;
}

.mobius-mini-dropdown-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: #f8fafc;
}

.mobius-mini-dropdown-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
}

.mobius-mini-dropdown-info {
  flex: 1;
}

.mobius-mini-dropdown-name {
  font-size: 11px;
  font-weight: 600;
  color: #0b1220;
}

.mobius-mini-dropdown-email {
  font-size: 9px;
  color: #64748b;
}

.mobius-mini-dropdown-divider {
  height: 1px;
  background: #e2e8f0;
}

.mobius-mini-dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 10px;
  color: #374151;
  text-align: left;
  transition: background 0.15s;
}

.mobius-mini-dropdown-item:hover {
  background: #f8fafc;
}

.mobius-mini-dropdown-item svg {
  color: #64748b;
}

.mobius-mini-dropdown-signout {
  color: #dc2626;
}

.mobius-mini-dropdown-signout svg {
  color: #dc2626;
}
`;
