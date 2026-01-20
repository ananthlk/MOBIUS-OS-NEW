/**
 * Authentication Service for User Awareness Sprint
 * 
 * Handles:
 * - Email/password login and registration
 * - Token storage in chrome.storage.session
 * - Token refresh
 * - Current user state management
 */

import { AuthTokens, UserProfile, AuthState } from '../types';

const API_BASE = 'http://localhost:5001/api/v1';

const STORAGE_KEYS = {
  accessToken: 'mobius.auth.accessToken',
  refreshToken: 'mobius.auth.refreshToken',
  expiresAt: 'mobius.auth.expiresAt',
  userProfile: 'mobius.auth.userProfile',
};

/**
 * Auth event types
 */
export type AuthEvent = 'login' | 'logout' | 'tokenRefreshed' | 'profileUpdated';
export type AuthEventCallback = (event: AuthEvent, data?: unknown) => void;

/**
 * Authentication Service
 */
class AuthService {
  private listeners: Set<AuthEventCallback> = new Set();
  private refreshTimer: number | null = null;

  /**
   * Subscribe to auth events
   */
  on(callback: AuthEventCallback): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  /**
   * Emit an auth event
   */
  private emit(event: AuthEvent, data?: unknown): void {
    this.listeners.forEach(callback => {
      try {
        callback(event, data);
      } catch (error) {
        console.error('[AuthService] Error in event listener:', error);
      }
    });
  }

  // ===========================================================================
  // Storage Helpers (via background script for content script compatibility)
  // ===========================================================================

  /**
   * Get items from session storage via background script
   */
  private async storageGet(keys: string[]): Promise<Record<string, unknown>> {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: 'mobius:auth:getStorage', keys },
        (response) => {
          if (chrome.runtime.lastError) {
            console.error('[AuthService] Storage get error:', chrome.runtime.lastError);
            resolve({});
            return;
          }
          resolve(response?.ok ? response.data : {});
        }
      );
    });
  }

  /**
   * Set items in session storage via background script
   */
  private async storageSet(items: Record<string, unknown>): Promise<void> {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: 'mobius:auth:setStorage', items },
        (response) => {
          if (chrome.runtime.lastError) {
            console.error('[AuthService] Storage set error:', chrome.runtime.lastError);
          }
          resolve();
        }
      );
    });
  }

  /**
   * Clear items from session storage via background script
   */
  private async storageClear(keys?: string[]): Promise<void> {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: 'mobius:auth:clearStorage', keys },
        (response) => {
          if (chrome.runtime.lastError) {
            console.error('[AuthService] Storage clear error:', chrome.runtime.lastError);
          }
          resolve();
        }
      );
    });
  }

  // ===========================================================================
  // Token Storage
  // ===========================================================================

  /**
   * Store auth tokens in chrome.storage.session
   */
  async storeTokens(tokens: AuthTokens): Promise<void> {
    const expiresAt = Date.now() + (tokens.expires_in * 1000);
    
    await this.storageSet({
      [STORAGE_KEYS.accessToken]: tokens.access_token,
      [STORAGE_KEYS.refreshToken]: tokens.refresh_token,
      [STORAGE_KEYS.expiresAt]: expiresAt,
    });
    
    // Schedule token refresh
    this.scheduleTokenRefresh(tokens.expires_in);
    
    console.log('[AuthService] Tokens stored, expires at:', new Date(expiresAt).toISOString());
  }

  /**
   * Get stored access token
   */
  async getAccessToken(): Promise<string | null> {
    try {
      const result = await this.storageGet([
        STORAGE_KEYS.accessToken,
        STORAGE_KEYS.expiresAt,
      ]);
      
      const token = result[STORAGE_KEYS.accessToken] as string | undefined;
      const expiresAt = result[STORAGE_KEYS.expiresAt] as number | undefined;
      
      if (!token) {
        return null;
      }
      
      // Check if expired (with 60 second buffer)
      if (expiresAt && Date.now() > expiresAt - 60000) {
        console.log('[AuthService] Token expired, attempting refresh...');
        const refreshed = await this.refreshAccessToken();
        return refreshed ? await this.getAccessToken() : null;
      }
      
      return token;
    } catch (error) {
      console.error('[AuthService] Error getting access token:', error);
      return null;
    }
  }

  /**
   * Get stored refresh token
   */
  async getRefreshToken(): Promise<string | null> {
    try {
      const result = await this.storageGet([STORAGE_KEYS.refreshToken]);
      return (result[STORAGE_KEYS.refreshToken] as string) || null;
    } catch (error) {
      console.error('[AuthService] Error getting refresh token:', error);
      return null;
    }
  }

  /**
   * Clear all stored tokens
   */
  async clearTokens(): Promise<void> {
    await this.storageClear([
      STORAGE_KEYS.accessToken,
      STORAGE_KEYS.refreshToken,
      STORAGE_KEYS.expiresAt,
      STORAGE_KEYS.userProfile,
    ]);
    
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
    
    console.log('[AuthService] Tokens cleared');
  }

  /**
   * Store user profile
   */
  async storeUserProfile(profile: UserProfile): Promise<void> {
    await this.storageSet({
      [STORAGE_KEYS.userProfile]: profile,
    });
  }

  /**
   * Get stored user profile
   */
  async getUserProfile(): Promise<UserProfile | null> {
    try {
      const result = await this.storageGet([STORAGE_KEYS.userProfile]);
      return (result[STORAGE_KEYS.userProfile] as UserProfile) || null;
    } catch (error) {
      console.error('[AuthService] Error getting user profile:', error);
      return null;
    }
  }

  // ===========================================================================
  // Token Refresh
  // ===========================================================================

  /**
   * Schedule automatic token refresh
   */
  private scheduleTokenRefresh(expiresIn: number): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }
    
    // Refresh 5 minutes before expiry
    const refreshIn = Math.max((expiresIn - 300) * 1000, 60000);
    
    this.refreshTimer = window.setTimeout(async () => {
      console.log('[AuthService] Auto-refreshing token...');
      await this.refreshAccessToken();
    }, refreshIn);
  }

  /**
   * Refresh the access token
   */
  async refreshAccessToken(): Promise<boolean> {
    const refreshToken = await this.getRefreshToken();
    if (!refreshToken) {
      console.log('[AuthService] No refresh token available');
      return false;
    }
    
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      
      if (!response.ok) {
        console.error('[AuthService] Token refresh failed');
        await this.clearTokens();
        return false;
      }
      
      const data = await response.json();
      
      // Store new access token (keep existing refresh token)
      const expiresAt = Date.now() + (data.expires_in * 1000);
      await chrome.storage.session.set({
        [STORAGE_KEYS.accessToken]: data.access_token,
        [STORAGE_KEYS.expiresAt]: expiresAt,
      });
      
      this.scheduleTokenRefresh(data.expires_in);
      this.emit('tokenRefreshed');
      
      console.log('[AuthService] Token refreshed successfully');
      return true;
    } catch (error) {
      console.error('[AuthService] Token refresh error:', error);
      return false;
    }
  }

  // ===========================================================================
  // Authentication
  // ===========================================================================

  /**
   * Login with email and password
   */
  async login(email: string, password: string, tenantId?: string): Promise<{ success: boolean; error?: string; user?: UserProfile }> {
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          tenant_id: tenantId,
        }),
      });
      
      const data = await response.json();
      
      if (!response.ok || !data.ok) {
        return { success: false, error: data.error || 'Login failed' };
      }
      
      // Store tokens
      await this.storeTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_in: data.expires_in,
      });
      
      // Store user profile
      if (data.user) {
        await this.storeUserProfile(data.user as UserProfile);
      }
      
      this.emit('login', data.user);
      
      return { success: true, user: data.user };
    } catch (error) {
      console.error('[AuthService] Login error:', error);
      return { success: false, error: 'Network error' };
    }
  }

  /**
   * Register a new account
   */
  async register(
    email: string,
    password: string,
    displayName?: string,
    firstName?: string,
    tenantId?: string
  ): Promise<{ success: boolean; error?: string; user?: UserProfile }> {
    try {
      const response = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          password,
          display_name: displayName,
          first_name: firstName,
          tenant_id: tenantId,
        }),
      });
      
      const data = await response.json();
      
      if (!response.ok || !data.ok) {
        return { success: false, error: data.error || 'Registration failed' };
      }
      
      // Store tokens (auto-login after registration)
      await this.storeTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_in: data.expires_in,
      });
      
      // Store user profile
      if (data.user) {
        await this.storeUserProfile(data.user as UserProfile);
      }
      
      this.emit('login', data.user);
      
      return { success: true, user: data.user };
    } catch (error) {
      console.error('[AuthService] Registration error:', error);
      return { success: false, error: 'Network error' };
    }
  }

  /**
   * Logout
   */
  async logout(): Promise<void> {
    const refreshToken = await this.getRefreshToken();
    
    // Call backend to invalidate session
    if (refreshToken) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch (error) {
        console.warn('[AuthService] Logout API call failed:', error);
      }
    }
    
    await this.clearTokens();
    this.emit('logout');
  }

  /**
   * Get current user from backend
   */
  async getCurrentUser(): Promise<UserProfile | null> {
    const token = await this.getAccessToken();
    if (!token) {
      return null;
    }
    
    try {
      const response = await fetch(`${API_BASE}/auth/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        return null;
      }
      
      const data = await response.json();
      if (data.ok && data.user) {
        // Flatten nested preference into user profile
        const user = data.user;
        const pref = user.preference || {};
        
        const profile: UserProfile = {
          user_id: user.user_id,
          tenant_id: user.tenant_id,
          email: user.email,
          display_name: user.display_name,
          first_name: user.first_name,
          preferred_name: user.preferred_name,
          greeting_name: user.preferred_name || user.first_name || user.display_name || 'there',
          avatar_url: user.avatar_url,
          timezone: user.timezone || 'America/New_York',
          locale: user.locale || 'en-US',
          is_onboarded: user.is_onboarded || false,
          activities: (user.activities || []).map((a: { activity_code: string }) => a.activity_code),
          tone: pref.tone || 'professional',
          greeting_enabled: pref.greeting_enabled !== false,
          autonomy_routine_tasks: pref.autonomy_routine_tasks || 'confirm_first',
          autonomy_sensitive_tasks: pref.autonomy_sensitive_tasks || 'manual',
        };
        
        await this.storeUserProfile(profile);
        return profile;
      }
      
      return null;
    } catch (error) {
      console.error('[AuthService] Error fetching current user:', error);
      return null;
    }
  }

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    const token = await this.getAccessToken();
    return token !== null;
  }

  /**
   * Get auth state
   */
  async getAuthState(): Promise<AuthState> {
    const token = await this.getAccessToken();
    if (!token) {
      return 'unauthenticated';
    }
    
    const profile = await this.getUserProfile();
    if (profile && !profile.is_onboarded) {
      return 'onboarding';
    }
    
    return 'authenticated';
  }

  /**
   * Check if email exists in system (for page detection)
   */
  async checkEmail(email: string, tenantId?: string): Promise<{ exists: boolean; user?: { display_name?: string; is_onboarded?: boolean } }> {
    try {
      const response = await fetch(`${API_BASE}/auth/check-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, tenant_id: tenantId }),
      });
      
      const data = await response.json();
      return {
        exists: data.exists === true,
        user: data.user,
      };
    } catch (error) {
      console.error('[AuthService] Error checking email:', error);
      return { exists: false };
    }
  }
}

// Singleton instance
let _authService: AuthService | null = null;

export function getAuthService(): AuthService {
  if (!_authService) {
    _authService = new AuthService();
  }
  return _authService;
}

export { AuthService };
