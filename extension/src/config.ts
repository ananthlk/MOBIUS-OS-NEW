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
const PROD_API_BASE = 'https://mobius-os-backend-mc2ivyhdxq-uc.a.run.app';

// Export the active API base URL
export const API_BASE_URL = PRODUCTION ? PROD_API_BASE : DEV_API_BASE;
export const API_V1_URL = `${API_BASE_URL}/api/v1`;

// Log which environment is active (only in dev)
if (!PRODUCTION) {
  console.log('[Mobius] Running in DEVELOPMENT mode, API:', API_BASE_URL);
}
