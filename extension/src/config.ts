/**
 * Mobius OS Extension Configuration
 * 
 * Toggle PRODUCTION to switch between dev and production servers.
 */

// Set to true for production build, false for local development
export const PRODUCTION = false;

// API Base URLs
const DEV_API_BASE = 'http://localhost:5001';
const PROD_API_BASE = 'https://mobius-os-backend-mc2ivyhdxq-uc.a.run.app';

// Export the active API base URL
export const API_BASE_URL = PRODUCTION ? PROD_API_BASE : DEV_API_BASE;
export const API_V1_URL = `${API_BASE_URL}/api/v1`;
