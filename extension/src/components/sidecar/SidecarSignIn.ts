/**
 * SidecarSignIn — the signed-out state of the sidebar.
 *
 * Phase 1 (icon + side panel only): the mini is retired, so the sidebar
 * hosts sign-in itself. Token-styled (replaces the mini's pre-token
 * locked overlay). Uses the shared AuthService, which talks to mobius-user
 * via the background proxy — same identity as every Mobius surface.
 *
 * OAuth buttons are stubs today (server flow not wired); email/password and
 * "create one" are live.
 */

import { getAuthService } from '../../services/auth';
import { ICONS } from './icons';

export function SidecarSignIn(onSignedIn: () => void): HTMLElement {
  const root = document.createElement('div');
  root.className = 'sidecar-signin';

  const head = document.createElement('div');
  head.className = 'sidecar-signin-head';
  head.innerHTML = `${ICONS.mobius}<span>Sign in to Mobius</span>`;
  root.appendChild(head);

  const sub = document.createElement('div');
  sub.className = 'sidecar-signin-sub';
  sub.textContent = 'Your Mobius account works across every surface.';
  root.appendChild(sub);

  const email = document.createElement('input');
  email.type = 'email';
  email.className = 'sidecar-signin-input';
  email.placeholder = 'Email';
  email.autocomplete = 'username';

  const password = document.createElement('input');
  password.type = 'password';
  password.className = 'sidecar-signin-input';
  password.placeholder = 'Password';
  password.autocomplete = 'current-password';

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'sidecar-signin-btn';
  btn.textContent = 'Sign in';

  const err = document.createElement('div');
  err.className = 'sidecar-signin-err';
  err.hidden = true;

  const showErr = (m: string) => {
    err.textContent = m;
    err.hidden = false;
  };

  let mode: 'login' | 'register' = 'login';

  const submit = async () => {
    const e = email.value.trim();
    const p = password.value;
    if (!e || !p) {
      showErr('Enter your email and password.');
      return;
    }
    err.hidden = true;
    btn.disabled = true;
    btn.textContent = mode === 'login' ? 'Signing in…' : 'Creating account…';
    try {
      const svc = getAuthService();
      const result =
        mode === 'login' ? await svc.login(e, p) : await svc.register(e, p);
      if (result.success) {
        onSignedIn();
      } else {
        showErr(result.error || 'Could not sign in.');
        btn.disabled = false;
        btn.textContent = mode === 'login' ? 'Sign in' : 'Create account';
      }
    } catch {
      showErr('Connection error — try again.');
      btn.disabled = false;
      btn.textContent = mode === 'login' ? 'Sign in' : 'Create account';
    }
  };

  btn.addEventListener('click', () => void submit());
  password.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') void submit();
  });
  [email, password].forEach((i) =>
    i.addEventListener('input', () => {
      err.hidden = true;
    })
  );

  root.appendChild(email);
  root.appendChild(password);
  root.appendChild(btn);
  root.appendChild(err);

  // Divider + OAuth stubs
  const divider = document.createElement('div');
  divider.className = 'sidecar-signin-divider';
  divider.innerHTML = '<span>or continue with</span>';
  root.appendChild(divider);

  const oauthRow = document.createElement('div');
  oauthRow.className = 'sidecar-signin-oauth';
  for (const [label] of [['Google'], ['Microsoft']]) {
    const o = document.createElement('button');
    o.type = 'button';
    o.className = 'sidecar-signin-oauth-btn';
    o.textContent = label;
    o.addEventListener('click', () => showErr(`${label} sign-in is coming soon.`));
    oauthRow.appendChild(o);
  }
  root.appendChild(oauthRow);

  // Toggle login / create
  const toggle = document.createElement('div');
  toggle.className = 'sidecar-signin-toggle';
  const rebuild = () => {
    toggle.innerHTML =
      mode === 'login'
        ? `Don't have an account? <a href="#">Create one</a>`
        : `Already have an account? <a href="#">Sign in</a>`;
    toggle.querySelector('a')?.addEventListener('click', (ev) => {
      ev.preventDefault();
      mode = mode === 'login' ? 'register' : 'login';
      btn.textContent = mode === 'login' ? 'Sign in' : 'Create account';
      err.hidden = true;
      rebuild();
    });
  };
  rebuild();
  root.appendChild(toggle);

  return root;
}
