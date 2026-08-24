/**
 * Mobius OS Extension Configuration
 * 
 * PRODUCTION flag is injected at build time by webpack:
 *   - npm run build:prod  → PRODUCTION = true  → points to Cloud Run
 *   - npm run build:dev   → PRODUCTION = false → points to localhost
 */

// Injected by webpack DefinePlugin at build time
declare const process: { env: { PRODUCTION: boolean } };
export const PRODUCTION = process.env.PRODUCTION ?? false;

// API Base URLs
const DEV_API_BASE = 'http://localhost:5001';
const PROD_API_BASE = 'https://mobius-os-backend-ortabkknqa-uc.a.run.app';

// Export the active API base URL
export const API_BASE_URL = PRODUCTION ? PROD_API_BASE : DEV_API_BASE;
export const API_V1_URL = `${API_BASE_URL}/api/v1`;

// Auth is NOT served by the mobius-os backend: identity lives in the shared
// mobius-user service (same accounts + JWT as mobius-chat and every other
// surface). The mobius-os backend accepts these tokens via the shared
// JWT_SECRET and JIT-provisions its local user row on first request.
export const AUTH_BASE_URL = 'https://mobius-user-ortabkknqa-uc.a.run.app';
export const AUTH_API_V1_URL = `${AUTH_BASE_URL}/api/v1`;

// Shared mobius-chat service — the same chat pipeline every Mobius surface
// uses. The extension's QuickChat is a no-PHI general assistant: it sends
// only what the user types (never page/EMR context) and relies on chat's
// server-side PHI gate as the backstop.
export const CHAT_BASE_URL = 'https://mobius-chat-ortabkknqa-uc.a.run.app';

// Log which environment is active (only in dev)
if (!PRODUCTION) {
  console.log('[Mobius] Running in DEVELOPMENT mode, API:', API_BASE_URL);
}
