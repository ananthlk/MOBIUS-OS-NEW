/**
 * User Context Detector Service
 * 
 * Detects the logged-in user from the host EHR/application page.
 * Similar to PatientContextDetector but for user identity.
 * 
 * Features:
 * - Multiple detection strategies (data attributes, DOM elements, URL)
 * - Configurable patterns per tenant
 * - Event-based notification when user is detected
 */

import { DetectedUser, UserContextDetectorOptions, UserDetectionEvent, UserDetectionCallback, UserIdType } from '../types';

/**
 * Pattern types for user detection
 */
interface DataAttributePattern {
  selector: string;
  attr: string;
  type: UserIdType;
}

interface DomSelectorPattern {
  selector: string;
  extract: string;
  type: UserIdType;
}

interface UrlPattern {
  pattern: RegExp;
  type: UserIdType;
}

interface UserPatterns {
  dataAttributes: DataAttributePattern[];
  domSelectors: DomSelectorPattern[];
  urlPatterns: UrlPattern[];
}

/**
 * Default patterns for detecting user from host page
 */
export const DEFAULT_USER_PATTERNS: UserPatterns = {
  dataAttributes: [
    { selector: '[data-user-id]', attr: 'data-user-id', type: 'user_id' },
    { selector: '[data-staff-id]', attr: 'data-staff-id', type: 'staff_id' },
    { selector: '[data-logged-in-user]', attr: 'data-logged-in-user', type: 'user_id' },
    { selector: '[data-current-user]', attr: 'data-current-user', type: 'user_id' },
    { selector: '[data-user-email]', attr: 'data-user-email', type: 'email' },
  ],
  domSelectors: [
    { selector: '.logged-in-user', extract: 'text', type: 'name' },
    { selector: '.user-name', extract: 'text', type: 'name' },
    { selector: '#current-user', extract: 'text', type: 'name' },
    { selector: '.staff-header .name', extract: 'text', type: 'name' },
    { selector: '[class*="user-display"]', extract: 'text', type: 'name' },
    { selector: '.user-email', extract: 'text', type: 'email' },
  ],
  urlPatterns: [
    { pattern: /user[_-]?id=([^&]+)/i, type: 'user_id' },
    { pattern: /staff[_-]?id=([^&]+)/i, type: 'staff_id' },
    { pattern: /logged[_-]?in[_-]?as=([^&]+)/i, type: 'user_id' },
  ],
};

/**
 * Default detector options
 */
const DEFAULT_OPTIONS: Required<UserContextDetectorOptions> = {
  debounceMs: 500,
  strategies: ['dataAttributes', 'domSelectors', 'url'],
  customPatterns: {},
  autoStart: false,
};

/**
 * UserContextDetector - Monitors host page for user identity
 * 
 * Usage:
 * ```typescript
 * const detector = new UserContextDetector({ debounceMs: 500 });
 * 
 * detector.on('userDetected', (user) => {
 *   console.log('User detected:', user);
 * });
 * 
 * detector.start();
 * ```
 */
export class UserContextDetector {
  private options: Required<UserContextDetectorOptions>;
  private patterns: UserPatterns;
  private debounceTimer: number | null = null;
  private isRunning = false;
  private currentUser: DetectedUser | null = null;
  private listeners: Map<UserDetectionEvent, Set<UserDetectionCallback>> = new Map();

  constructor(options: UserContextDetectorOptions = {}) {
    this.options = { ...DEFAULT_OPTIONS, ...options };
    this.patterns = { ...DEFAULT_USER_PATTERNS, ...this.options.customPatterns };
    
    // Initialize listener maps
    this.listeners.set('userDetected', new Set());
    this.listeners.set('userChanged', new Set());
    this.listeners.set('userCleared', new Set());
    this.listeners.set('detectionError', new Set());
    
    if (this.options.autoStart) {
      this.start();
    }
  }

  /**
   * Start monitoring for user context
   */
  start(): void {
    if (this.isRunning) {
      console.log('[UserContextDetector] Already running');
      return;
    }
    
    console.log('[UserContextDetector] Starting...');
    this.isRunning = true;
    
    // Initial detection
    this.scheduleDetection();
  }

  /**
   * Stop monitoring
   */
  stop(): void {
    if (!this.isRunning) {
      return;
    }
    
    console.log('[UserContextDetector] Stopping...');
    this.isRunning = false;
    
    if (this.debounceTimer !== null) {
      window.clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
  }

  /**
   * Force an immediate detection scan
   */
  detect(): DetectedUser | null {
    try {
      const user = this.detectUser();
      this.handleDetectionResult(user);
      return user;
    } catch (error) {
      console.error('[UserContextDetector] Detection error:', error);
      this.emit('detectionError', null);
      return null;
    }
  }

  /**
   * Subscribe to detection events
   */
  on(event: UserDetectionEvent, callback: UserDetectionCallback): () => void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.add(callback);
    }
    
    return () => this.off(event, callback);
  }

  /**
   * Unsubscribe from events
   */
  off(event: UserDetectionEvent, callback: UserDetectionCallback): void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.delete(callback);
    }
  }

  /**
   * Get currently detected user
   */
  getCurrentUser(): DetectedUser | null {
    return this.currentUser;
  }

  /**
   * Check if detector is running
   */
  isActive(): boolean {
    return this.isRunning;
  }

  /**
   * Update detection patterns
   */
  updatePatterns(customPatterns: Partial<typeof DEFAULT_USER_PATTERNS>): void {
    this.patterns = { ...DEFAULT_USER_PATTERNS, ...customPatterns };
    
    if (this.isRunning) {
      this.scheduleDetection();
    }
  }

  // ===========================================================================
  // Private Methods
  // ===========================================================================

  private scheduleDetection(): void {
    if (this.debounceTimer !== null) {
      window.clearTimeout(this.debounceTimer);
    }
    
    this.debounceTimer = window.setTimeout(() => {
      this.debounceTimer = null;
      this.detect();
    }, this.options.debounceMs);
  }

  private detectUser(): DetectedUser | null {
    const strategies = this.options.strategies;
    
    // Try each strategy in order
    for (const strategy of strategies) {
      let result: DetectedUser | null = null;
      
      switch (strategy) {
        case 'dataAttributes':
          result = this.detectFromDataAttributes();
          break;
        case 'domSelectors':
          result = this.detectFromDomSelectors();
          break;
        case 'url':
          result = this.detectFromUrl();
          break;
      }
      
      if (result) {
        console.log(`[UserContextDetector] Found user via ${strategy}:`, result);
        return result;
      }
    }
    
    return null;
  }

  private detectFromDataAttributes(): DetectedUser | null {
    for (const pattern of this.patterns.dataAttributes) {
      const element = document.querySelector(pattern.selector);
      if (element) {
        const value = element.getAttribute(pattern.attr);
        if (value) {
          return {
            id_type: pattern.type,
            id_value: value,
            source: 'dataAttributes',
          };
        }
      }
    }
    return null;
  }

  private detectFromDomSelectors(): DetectedUser | null {
    for (const pattern of this.patterns.domSelectors) {
      const element = document.querySelector(pattern.selector);
      if (element) {
        let value: string | null = null;
        
        if (pattern.extract === 'text') {
          value = element.textContent?.trim() || null;
        }
        
        if (value) {
          // Try to extract email if it looks like one
          const emailMatch = value.match(/[\w.+-]+@[\w.-]+\.\w+/);
          if (emailMatch) {
            return {
              id_type: 'email',
              id_value: emailMatch[0],
              display_name: value.replace(emailMatch[0], '').trim() || undefined,
              source: 'domSelectors',
            };
          }
          
          return {
            id_type: pattern.type,
            id_value: value,
            display_name: pattern.type === 'name' ? value : undefined,
            source: 'domSelectors',
          };
        }
      }
    }
    return null;
  }

  private detectFromUrl(): DetectedUser | null {
    const url = window.location.href;
    
    for (const pattern of this.patterns.urlPatterns) {
      const match = url.match(pattern.pattern);
      if (match && match[1]) {
        return {
          id_type: pattern.type,
          id_value: decodeURIComponent(match[1]),
          source: 'url',
        };
      }
    }
    return null;
  }

  private handleDetectionResult(user: DetectedUser | null): void {
    const previousUser = this.currentUser;
    
    if (user === null && previousUser !== null) {
      this.currentUser = null;
      this.emit('userCleared', null);
      console.log('[UserContextDetector] User context cleared');
    } else if (user !== null && previousUser === null) {
      this.currentUser = user;
      this.emit('userDetected', user);
      console.log('[UserContextDetector] User detected:', user);
    } else if (user !== null && previousUser !== null) {
      if (!this.isSameUser(user, previousUser)) {
        this.currentUser = user;
        this.emit('userChanged', user);
        console.log('[UserContextDetector] User changed:', user);
      }
    }
  }

  private isSameUser(a: DetectedUser, b: DetectedUser): boolean {
    return a.id_type === b.id_type && a.id_value === b.id_value;
  }

  private emit(event: UserDetectionEvent, user: DetectedUser | null): void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(user, event);
        } catch (error) {
          console.error(`[UserContextDetector] Error in ${event} listener:`, error);
        }
      });
    }
  }
}

/**
 * Singleton instance
 */
let defaultDetector: UserContextDetector | null = null;

export function getDefaultUserDetector(): UserContextDetector {
  if (!defaultDetector) {
    defaultDetector = new UserContextDetector({
      debounceMs: 500,
      strategies: ['dataAttributes', 'domSelectors', 'url'],
    });
  }
  return defaultDetector;
}

export function resetDefaultUserDetector(): void {
  if (defaultDetector) {
    defaultDetector.stop();
    defaultDetector = null;
  }
}
