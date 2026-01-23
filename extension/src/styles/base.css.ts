/**
 * Base CSS Styles using Theme Variables
 * 
 * This generates CSS that uses the --mobius-* custom properties
 * defined by the theme system.
 */

export const BASE_CSS = `
/* =============================================================================
   MOBIUS BASE STYLES
   Uses CSS variables from themes.ts for consistent styling
   ============================================================================= */

/* Typography */
.mobius-text-xs { font-size: var(--mobius-font-xs); }
.mobius-text-sm { font-size: var(--mobius-font-sm); }
.mobius-text-base { font-size: var(--mobius-font-base); }
.mobius-text-md { font-size: var(--mobius-font-md); }
.mobius-text-lg { font-size: var(--mobius-font-lg); }
.mobius-text-xl { font-size: var(--mobius-font-xl); }

.mobius-text-primary { color: var(--mobius-text-primary); }
.mobius-text-secondary { color: var(--mobius-text-secondary); }
.mobius-text-muted { color: var(--mobius-text-muted); }
.mobius-text-accent { color: var(--mobius-accent); }
.mobius-text-success { color: var(--mobius-success); }
.mobius-text-warning { color: var(--mobius-warning); }
.mobius-text-error { color: var(--mobius-error); }

/* Spacing */
.mobius-p-xs { padding: var(--mobius-space-xs); }
.mobius-p-sm { padding: var(--mobius-space-sm); }
.mobius-p-base { padding: var(--mobius-space-base); }
.mobius-p-md { padding: var(--mobius-space-md); }
.mobius-p-lg { padding: var(--mobius-space-lg); }

.mobius-m-xs { margin: var(--mobius-space-xs); }
.mobius-m-sm { margin: var(--mobius-space-sm); }
.mobius-m-base { margin: var(--mobius-space-base); }
.mobius-m-md { margin: var(--mobius-space-md); }
.mobius-m-lg { margin: var(--mobius-space-lg); }

.mobius-gap-xs { gap: var(--mobius-space-xs); }
.mobius-gap-sm { gap: var(--mobius-space-sm); }
.mobius-gap-base { gap: var(--mobius-space-base); }
.mobius-gap-md { gap: var(--mobius-space-md); }
.mobius-gap-lg { gap: var(--mobius-space-lg); }

/* Backgrounds */
.mobius-bg-primary { background-color: var(--mobius-bg-primary); }
.mobius-bg-secondary { background-color: var(--mobius-bg-secondary); }
.mobius-bg-tertiary { background-color: var(--mobius-bg-tertiary); }
.mobius-bg-accent { background-color: var(--mobius-accent); }

/* Borders */
.mobius-border { border: 1px solid var(--mobius-border); }
.mobius-border-light { border: 1px solid var(--mobius-border-light); }
.mobius-rounded-sm { border-radius: var(--mobius-radius-sm); }
.mobius-rounded { border-radius: var(--mobius-radius-base); }
.mobius-rounded-lg { border-radius: var(--mobius-radius-lg); }

/* Shadows */
.mobius-shadow { box-shadow: 0 1px 3px var(--mobius-shadow); }
.mobius-shadow-md { box-shadow: 0 4px 6px var(--mobius-shadow), 0 1px 3px var(--mobius-shadow); }
.mobius-shadow-lg { box-shadow: 0 10px 15px var(--mobius-shadow-strong), 0 4px 6px var(--mobius-shadow); }

/* =============================================================================
   MINI WIDGET STYLES
   ============================================================================= */

.mobius-mini-widget {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--mobius-bg-primary);
  color: var(--mobius-text-primary);
  border-radius: var(--mobius-radius-lg);
  box-shadow: 0 4px 12px var(--mobius-shadow-strong);
  border: 1px solid var(--mobius-border);
  overflow: hidden;
}

.mobius-mini-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--mobius-space-sm) var(--mobius-space-md);
  background: var(--mobius-bg-secondary);
  border-bottom: 1px solid var(--mobius-border-light);
}

.mobius-mini-logo {
  font-size: var(--mobius-font-base);
  font-weight: 600;
  color: var(--mobius-text-primary);
}

.mobius-mini-greeting {
  font-size: var(--mobius-font-sm);
  color: var(--mobius-text-secondary);
  padding: var(--mobius-space-sm) var(--mobius-space-md);
}

.mobius-mini-patient {
  display: flex;
  align-items: center;
  gap: var(--mobius-space-sm);
  padding: var(--mobius-space-sm) var(--mobius-space-md);
  background: var(--mobius-bg-secondary);
}

.mobius-mini-patient-name {
  font-size: var(--mobius-font-sm);
  font-weight: 500;
  color: var(--mobius-text-primary);
}

.mobius-mini-patient-id {
  font-size: var(--mobius-font-xs);
  color: var(--mobius-text-muted);
}

.mobius-mini-status {
  display: flex;
  align-items: center;
  gap: var(--mobius-space-xs);
  padding: var(--mobius-space-sm) var(--mobius-space-md);
  font-size: var(--mobius-font-sm);
}

.mobius-mini-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.mobius-mini-status-dot.green { background: var(--mobius-success); }
.mobius-mini-status-dot.yellow { background: var(--mobius-warning); }
.mobius-mini-status-dot.red { background: var(--mobius-error); }

.mobius-mini-plan {
  padding: var(--mobius-space-sm) var(--mobius-space-md);
  font-size: var(--mobius-font-sm);
}

.mobius-mini-plan-link {
  color: var(--mobius-accent);
  cursor: pointer;
}

.mobius-mini-plan-link:hover {
  text-decoration: underline;
}

.mobius-mini-note {
  display: flex;
  gap: var(--mobius-space-sm);
  padding: var(--mobius-space-sm) var(--mobius-space-md);
  border-top: 1px solid var(--mobius-border-light);
}

.mobius-mini-note-input {
  flex: 1;
  border: 1px solid var(--mobius-border);
  border-radius: var(--mobius-radius-sm);
  padding: var(--mobius-space-xs) var(--mobius-space-sm);
  font-size: var(--mobius-font-sm);
  background: var(--mobius-bg-primary);
  color: var(--mobius-text-primary);
}

.mobius-mini-note-input::placeholder {
  color: var(--mobius-text-muted);
}

.mobius-mini-note-btn {
  background: var(--mobius-accent);
  color: var(--mobius-accent-text);
  border: none;
  border-radius: var(--mobius-radius-sm);
  padding: var(--mobius-space-xs) var(--mobius-space-sm);
  cursor: pointer;
  font-size: var(--mobius-font-sm);
}

.mobius-mini-note-btn:hover {
  background: var(--mobius-accent-hover);
}

/* =============================================================================
   SIDECAR STYLES
   ============================================================================= */

.mobius-sidecar {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--mobius-bg-primary);
  color: var(--mobius-text-primary);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.mobius-sidecar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--mobius-space-md);
  background: var(--mobius-bg-secondary);
  border-bottom: 1px solid var(--mobius-border);
}

.mobius-sidecar-title {
  font-size: var(--mobius-font-md);
  font-weight: 600;
}

.mobius-sidecar-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--mobius-space-md);
}

.mobius-sidecar-section {
  margin-bottom: var(--mobius-space-lg);
}

.mobius-sidecar-section-title {
  font-size: var(--mobius-font-sm);
  font-weight: 600;
  color: var(--mobius-text-secondary);
  margin-bottom: var(--mobius-space-sm);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Factor Cards */
.mobius-factor-card {
  background: var(--mobius-bg-secondary);
  border: 1px solid var(--mobius-border);
  border-radius: var(--mobius-radius-base);
  margin-bottom: var(--mobius-space-sm);
  overflow: hidden;
}

.mobius-factor-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--mobius-space-sm) var(--mobius-space-md);
  cursor: pointer;
}

.mobius-factor-card-header:hover {
  background: var(--mobius-bg-hover);
}

.mobius-factor-card-title {
  font-size: var(--mobius-font-sm);
  font-weight: 500;
}

.mobius-factor-card-status {
  font-size: var(--mobius-font-xs);
  padding: var(--mobius-space-xs) var(--mobius-space-sm);
  border-radius: var(--mobius-radius-sm);
}

.mobius-factor-card-status.success {
  background: color-mix(in srgb, var(--mobius-success) 15%, transparent);
  color: var(--mobius-success);
}

.mobius-factor-card-status.warning {
  background: color-mix(in srgb, var(--mobius-warning) 15%, transparent);
  color: var(--mobius-warning);
}

.mobius-factor-card-status.error {
  background: color-mix(in srgb, var(--mobius-error) 15%, transparent);
  color: var(--mobius-error);
}

.mobius-factor-card-body {
  padding: var(--mobius-space-sm) var(--mobius-space-md);
  border-top: 1px solid var(--mobius-border-light);
}

/* Steps */
.mobius-step {
  display: flex;
  align-items: center;
  gap: var(--mobius-space-sm);
  padding: var(--mobius-space-xs) 0;
  font-size: var(--mobius-font-sm);
}

.mobius-step-indicator {
  width: var(--mobius-icon-sm);
  height: var(--mobius-icon-sm);
  border-radius: 50%;
  border: 2px solid var(--mobius-border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
}

.mobius-step-indicator.done {
  background: var(--mobius-success);
  border-color: var(--mobius-success);
  color: white;
}

.mobius-step-indicator.current {
  border-color: var(--mobius-accent);
  background: var(--mobius-accent);
  color: white;
}

.mobius-step-label {
  flex: 1;
  color: var(--mobius-text-primary);
}

.mobius-step-label.muted {
  color: var(--mobius-text-muted);
}

/* Buttons */
.mobius-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--mobius-space-xs);
  height: var(--mobius-button-height);
  padding: 0 var(--mobius-space-md);
  font-size: var(--mobius-font-sm);
  font-weight: 500;
  border-radius: var(--mobius-radius-base);
  cursor: pointer;
  transition: all 0.15s ease;
  border: none;
}

.mobius-btn-primary {
  background: var(--mobius-accent);
  color: var(--mobius-accent-text);
}

.mobius-btn-primary:hover {
  background: var(--mobius-accent-hover);
}

.mobius-btn-secondary {
  background: var(--mobius-bg-tertiary);
  color: var(--mobius-text-primary);
  border: 1px solid var(--mobius-border);
}

.mobius-btn-secondary:hover {
  background: var(--mobius-bg-hover);
}

.mobius-btn-ghost {
  background: transparent;
  color: var(--mobius-text-secondary);
}

.mobius-btn-ghost:hover {
  background: var(--mobius-bg-hover);
  color: var(--mobius-text-primary);
}

.mobius-btn-sm {
  height: calc(var(--mobius-button-height) - 4px);
  padding: 0 var(--mobius-space-sm);
  font-size: var(--mobius-font-xs);
}

/* Menu */
.mobius-menu {
  background: var(--mobius-bg-primary);
  border: 1px solid var(--mobius-border);
  border-radius: var(--mobius-radius-base);
  box-shadow: 0 4px 12px var(--mobius-shadow-strong);
  min-width: 180px;
  padding: var(--mobius-space-xs) 0;
}

.mobius-menu-item {
  display: flex;
  align-items: center;
  gap: var(--mobius-space-sm);
  padding: var(--mobius-space-sm) var(--mobius-space-md);
  font-size: var(--mobius-font-sm);
  color: var(--mobius-text-primary);
  cursor: pointer;
}

.mobius-menu-item:hover {
  background: var(--mobius-bg-hover);
}

.mobius-menu-item.active {
  background: var(--mobius-bg-active);
}

.mobius-menu-divider {
  height: 1px;
  background: var(--mobius-border-light);
  margin: var(--mobius-space-xs) 0;
}

/* Input */
.mobius-input {
  width: 100%;
  height: var(--mobius-input-height);
  padding: 0 var(--mobius-space-sm);
  font-size: var(--mobius-font-sm);
  background: var(--mobius-bg-primary);
  color: var(--mobius-text-primary);
  border: 1px solid var(--mobius-border);
  border-radius: var(--mobius-radius-base);
}

.mobius-input:focus {
  outline: none;
  border-color: var(--mobius-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--mobius-accent) 20%, transparent);
}

.mobius-input::placeholder {
  color: var(--mobius-text-muted);
}

/* Badges */
.mobius-badge {
  display: inline-flex;
  align-items: center;
  padding: var(--mobius-space-xs) var(--mobius-space-sm);
  font-size: var(--mobius-font-xs);
  font-weight: 500;
  border-radius: var(--mobius-radius-sm);
}

.mobius-badge-success {
  background: color-mix(in srgb, var(--mobius-success) 15%, transparent);
  color: var(--mobius-success);
}

.mobius-badge-warning {
  background: color-mix(in srgb, var(--mobius-warning) 15%, transparent);
  color: var(--mobius-warning);
}

.mobius-badge-error {
  background: color-mix(in srgb, var(--mobius-error) 15%, transparent);
  color: var(--mobius-error);
}

.mobius-badge-info {
  background: color-mix(in srgb, var(--mobius-info) 15%, transparent);
  color: var(--mobius-info);
}

/* Toggle */
.mobius-toggle {
  position: relative;
  display: inline-flex;
  width: 36px;
  height: 20px;
  cursor: pointer;
}

.mobius-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.mobius-toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--mobius-bg-tertiary);
  border-radius: 10px;
  transition: 0.2s;
}

.mobius-toggle-slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background: white;
  border-radius: 50%;
  transition: 0.2s;
  box-shadow: 0 1px 3px var(--mobius-shadow);
}

.mobius-toggle input:checked + .mobius-toggle-slider {
  background: var(--mobius-accent);
}

.mobius-toggle input:checked + .mobius-toggle-slider:before {
  transform: translateX(16px);
}
`;

/**
 * Inject base CSS into document
 */
export function injectBaseCSS(): void {
  const existingStyle = document.getElementById('mobius-base-css');
  if (existingStyle) return;
  
  const style = document.createElement('style');
  style.id = 'mobius-base-css';
  style.textContent = BASE_CSS;
  document.head.appendChild(style);
}
