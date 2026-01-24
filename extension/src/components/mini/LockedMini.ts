/**
 * Locked Mini Component for User Awareness Sprint
 * 
 * Shows sign-in options when user is not authenticated.
 * No patient data or actions are available in this state.
 */

import { getAuthService } from '../../services/auth';

export interface LockedMiniProps {
  /** Detected user info (if page detection found something) */
  detectedUser?: {
    email?: string;
    display_name?: string;
  };
  /** Callback when user successfully signs in */
  onSignIn: () => void;
  /** Callback to show full sign-in form */
  onShowSignIn: () => void;
  /** Callback for "Not you?" action */
  onSignInDifferent: () => void;
}

/**
 * Create the locked Mini component
 */
export function LockedMini(props: LockedMiniProps): HTMLElement {
  const { detectedUser, onSignIn, onShowSignIn, onSignInDifferent } = props;
  
  const root = document.createElement('div');
  root.className = 'mobius-mini-locked';
  
  // Header with logo
  const header = document.createElement('div');
  header.className = 'mobius-mini-locked-header';
  header.innerHTML = `
    <div class="mobius-mini-brand">
      <div class="mobius-mini-logo">
        <svg viewBox="0 0 24 24" width="20" height="20">
          <circle cx="12" cy="12" r="10" fill="#3B82F6"/>
          <path d="M12 7 L12 17 M7 12 L17 12" stroke="white" stroke-width="2"/>
        </svg>
      </div>
      <span class="mobius-mini-brand-text">Mobius</span>
    </div>
  `;
  root.appendChild(header);
  
  // Content area
  const content = document.createElement('div');
  content.className = 'mobius-mini-locked-content';
  
  if (detectedUser?.email || detectedUser?.display_name) {
    // Page detection found a user - prompt to confirm or sign in differently
    content.innerHTML = `
      <div class="mobius-mini-locked-detected">
        <p class="mobius-mini-locked-title">Welcome!</p>
        <p class="mobius-mini-locked-subtitle">We detected you as:</p>
        <div class="mobius-mini-locked-user">
          <div class="mobius-mini-locked-avatar">
            ${(detectedUser.display_name || detectedUser.email || '?')[0].toUpperCase()}
          </div>
          <div class="mobius-mini-locked-user-info">
            ${detectedUser.display_name ? `<div class="mobius-mini-locked-user-name">${escapeHtml(detectedUser.display_name)}</div>` : ''}
            ${detectedUser.email ? `<div class="mobius-mini-locked-user-email">${escapeHtml(detectedUser.email)}</div>` : ''}
          </div>
        </div>
        <button class="mobius-mini-btn-primary mobius-mini-create-btn" type="button">
          Create my Mobius account
        </button>
        <div class="mobius-mini-locked-alt">
          <span>Not you?</span>
          <button class="mobius-mini-link-btn" type="button">Sign in differently</button>
        </div>
      </div>
    `;
    
    // Wire up create account button
    const createBtn = content.querySelector('.mobius-mini-create-btn');
    createBtn?.addEventListener('click', () => {
      // Pre-fill with detected info
      onShowSignIn();
    });
    
    // Wire up "Not you?" link
    const signInDiffBtn = content.querySelector('.mobius-mini-link-btn');
    signInDiffBtn?.addEventListener('click', () => {
      onSignInDifferent();
    });
  } else {
    // No detected user - show sign-in options
    content.innerHTML = `
      <div class="mobius-mini-locked-signin">
        <p class="mobius-mini-locked-title">Sign in to continue</p>
        <p class="mobius-mini-locked-subtitle">Mobius helps you manage patient workflows efficiently.</p>
        
        <div class="mobius-mini-auth-buttons">
          <button class="mobius-mini-auth-btn mobius-mini-auth-google" type="button">
            <svg viewBox="0 0 24 24" width="16" height="16">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            <span>Sign in with Google</span>
          </button>
          
          <button class="mobius-mini-auth-btn mobius-mini-auth-email" type="button">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
            </svg>
            <span>Sign in with Email</span>
          </button>
          
          <button class="mobius-mini-auth-btn mobius-mini-auth-sso" type="button">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>
            </svg>
            <span>Enterprise SSO</span>
          </button>
        </div>
        
        <div class="mobius-mini-locked-why">
          <button class="mobius-mini-link-btn" type="button">Why do I need to sign in?</button>
        </div>
      </div>
    `;
    
    // Wire up sign-in buttons
    const emailBtn = content.querySelector('.mobius-mini-auth-email');
    emailBtn?.addEventListener('click', () => onShowSignIn());
    
    const googleBtn = content.querySelector('.mobius-mini-auth-google');
    googleBtn?.addEventListener('click', () => {
      // For now, just show email sign-in
      // TODO: Implement Google OAuth
      onShowSignIn();
    });
    
    const ssoBtn = content.querySelector('.mobius-mini-auth-sso');
    ssoBtn?.addEventListener('click', () => {
      // For now, just show email sign-in
      // TODO: Implement SSO
      onShowSignIn();
    });
    
    // Wire up "Why?" link
    const whyBtn = content.querySelector('.mobius-mini-locked-why .mobius-mini-link-btn');
    whyBtn?.addEventListener('click', () => {
      alert('Mobius requires sign-in to:\n\n• Personalize your experience based on your activities\n• Show relevant quick actions and tasks\n• Keep your preferences across sessions\n• Protect patient information');
    });
  }
  
  root.appendChild(content);
  
  return root;
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
 * CSS styles for locked Mini (uses CSS variables for theming)
 */
export const LOCKED_MINI_STYLES = `
.mobius-mini-locked {
  padding: var(--mobius-space-md, 12px);
  background: var(--mobius-bg-primary, white);
  border-radius: var(--mobius-radius-lg, 12px);
  box-shadow: 0 4px 24px var(--mobius-shadow-strong, rgba(0,0,0,0.15));
}

.mobius-mini-locked-header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-bottom: var(--mobius-space-md, 12px);
  border-bottom: 1px solid var(--mobius-border, #e2e8f0);
  margin-bottom: var(--mobius-space-lg, 16px);
}

.mobius-mini-locked-content {
  text-align: center;
}

.mobius-mini-locked-title {
  font-size: var(--mobius-font-base, 13px);
  font-weight: 500;
  color: var(--mobius-text-primary, #0b1220);
  margin: 0 0 var(--mobius-space-xs, 4px);
}

.mobius-mini-locked-subtitle {
  font-size: var(--mobius-font-sm, 10px);
  color: var(--mobius-text-secondary, #64748b);
  margin: 0 0 var(--mobius-space-lg, 16px);
}

.mobius-mini-locked-user {
  display: flex;
  align-items: center;
  gap: var(--mobius-space-sm, 10px);
  padding: var(--mobius-space-sm, 10px);
  background: var(--mobius-bg-secondary, #f8fafc);
  border-radius: var(--mobius-radius-sm, 8px);
  margin-bottom: var(--mobius-space-md, 12px);
}

.mobius-mini-locked-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--mobius-accent, #3b82f6);
  color: var(--mobius-bg-primary, white);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 500;
  font-size: var(--mobius-font-base, 14px);
}

.mobius-mini-locked-user-info {
  text-align: left;
}

.mobius-mini-locked-user-name {
  font-size: var(--mobius-font-sm, 11px);
  font-weight: 500;
  color: var(--mobius-text-primary, #0b1220);
}

.mobius-mini-locked-user-email {
  font-size: var(--mobius-font-xs, 9px);
  color: var(--mobius-text-secondary, #64748b);
}

.mobius-mini-auth-buttons {
  display: flex;
  flex-direction: column;
  gap: var(--mobius-space-sm, 8px);
  margin-bottom: var(--mobius-space-md, 12px);
}

.mobius-mini-auth-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--mobius-space-sm, 8px);
  padding: var(--mobius-space-sm, 10px) var(--mobius-space-md, 12px);
  border-radius: var(--mobius-radius-sm, 6px);
  font-size: var(--mobius-font-sm, 11px);
  font-weight: 400;
  cursor: pointer;
  transition: all 0.15s;
}

.mobius-mini-auth-google {
  background: var(--mobius-bg-primary, white);
  border: 1px solid var(--mobius-border, #e2e8f0);
  color: var(--mobius-text-secondary, #374151);
}

.mobius-mini-auth-google:hover {
  background: var(--mobius-bg-secondary, #f8fafc);
  border-color: var(--mobius-border, #d1d5db);
}

.mobius-mini-auth-email {
  background: var(--mobius-accent, #3b82f6);
  border: none;
  color: var(--mobius-bg-primary, white);
}

.mobius-mini-auth-email:hover {
  background: var(--mobius-accent-hover, #2563eb);
}

.mobius-mini-auth-sso {
  background: var(--mobius-text-primary, #1e293b);
  border: none;
  color: var(--mobius-bg-primary, white);
}

.mobius-mini-auth-sso:hover {
  background: var(--mobius-text-primary, #0f172a);
}

.mobius-mini-create-btn {
  width: 100%;
  padding: var(--mobius-space-sm, 10px) var(--mobius-space-lg, 16px);
  background: var(--mobius-accent, #3b82f6);
  border: none;
  border-radius: var(--mobius-radius-sm, 6px);
  color: var(--mobius-bg-primary, white);
  font-size: var(--mobius-font-sm, 11px);
  font-weight: 500;
  cursor: pointer;
}

.mobius-mini-create-btn:hover {
  background: var(--mobius-accent-hover, #2563eb);
}

.mobius-mini-locked-alt {
  margin-top: var(--mobius-space-md, 12px);
  font-size: var(--mobius-font-sm, 10px);
  color: var(--mobius-text-secondary, #64748b);
}

.mobius-mini-link-btn {
  background: none;
  border: none;
  color: var(--mobius-accent, #3b82f6);
  cursor: pointer;
  font-size: var(--mobius-font-sm, 10px);
  text-decoration: underline;
}

.mobius-mini-link-btn:hover {
  color: var(--mobius-accent-hover, #2563eb);
}

.mobius-mini-locked-why {
  margin-top: var(--mobius-space-lg, 16px);
  padding-top: var(--mobius-space-md, 12px);
  border-top: 1px solid var(--mobius-border, #e2e8f0);
}
`;
