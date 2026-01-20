/**
 * Patient Context Detector Service
 * 
 * A reusable service that monitors webpages for patient identifiers
 * and emits events when patient context is detected or changes.
 * 
 * Features:
 * - MutationObserver for DOM change detection
 * - Multi-strategy detection (data attributes, URL, DOM text)
 * - Debouncing to avoid excessive API calls
 * - Event-based notification system
 * - Configurable patterns with tenant overrides
 */

import {
  DetectedPatient,
  PatientContextDetectorOptions,
  PatientDetectionEvent,
  PatientDetectionCallback,
  PatternConfig,
} from '../types';

import {
  DEFAULT_PATTERNS,
  detectPatient,
  mergePatterns,
  parsePatternConfig,
} from './patternMatchers';

/**
 * Default detector options
 */
const DEFAULT_OPTIONS: Required<PatientContextDetectorOptions> = {
  debounceMs: 500,
  strategies: ['dataAttributes', 'url', 'domText'],
  customPatterns: {},
  autoStart: false,
  observeMutations: true,
};

/**
 * PatientContextDetector - Monitors webpages for patient identifiers
 * 
 * Usage:
 * ```typescript
 * const detector = new PatientContextDetector({ debounceMs: 500 });
 * 
 * detector.on('patientDetected', (patient) => {
 *   console.log('Patient detected:', patient);
 * });
 * 
 * detector.start();
 * ```
 */
export class PatientContextDetector {
  private options: Required<PatientContextDetectorOptions>;
  private patterns: PatternConfig;
  private observer: MutationObserver | null = null;
  private debounceTimer: number | null = null;
  private isRunning = false;
  private currentPatient: DetectedPatient | null = null;
  private listeners: Map<PatientDetectionEvent, Set<PatientDetectionCallback>> = new Map();
  private lastUrl: string = '';

  constructor(options: PatientContextDetectorOptions = {}) {
    this.options = { ...DEFAULT_OPTIONS, ...options };
    this.patterns = mergePatterns(DEFAULT_PATTERNS, this.options.customPatterns || {});
    
    // Initialize listener maps
    this.listeners.set('patientDetected', new Set());
    this.listeners.set('patientChanged', new Set());
    this.listeners.set('patientCleared', new Set());
    this.listeners.set('detectionError', new Set());
    
    if (this.options.autoStart) {
      this.start();
    }
  }

  /**
   * Start monitoring for patient context
   */
  start(): void {
    if (this.isRunning) {
      console.log('[PatientContextDetector] Already running');
      return;
    }
    
    console.log('[PatientContextDetector] Starting...');
    this.isRunning = true;
    this.lastUrl = window.location.href;
    
    // Initial detection
    this.scheduleDetection();
    
    // Set up URL change detection (for SPAs)
    this.setupUrlChangeDetection();
    
    // Set up MutationObserver if enabled
    if (this.options.observeMutations) {
      this.setupMutationObserver();
    }
  }

  /**
   * Stop monitoring for patient context
   */
  stop(): void {
    if (!this.isRunning) {
      return;
    }
    
    console.log('[PatientContextDetector] Stopping...');
    this.isRunning = false;
    
    // Cancel pending detection
    if (this.debounceTimer !== null) {
      window.clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
    
    // Disconnect observer
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
  }

  /**
   * Force an immediate detection scan
   */
  detect(): DetectedPatient | null {
    try {
      const patient = detectPatient(this.options.strategies, this.patterns);
      this.handleDetectionResult(patient);
      return patient;
    } catch (error) {
      console.error('[PatientContextDetector] Detection error:', error);
      this.emit('detectionError', null);
      return null;
    }
  }

  /**
   * Subscribe to detection events
   */
  on(event: PatientDetectionEvent, callback: PatientDetectionCallback): () => void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.add(callback);
    }
    
    // Return unsubscribe function
    return () => this.off(event, callback);
  }

  /**
   * Unsubscribe from detection events
   */
  off(event: PatientDetectionEvent, callback: PatientDetectionCallback): void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.delete(callback);
    }
  }

  /**
   * Get the currently detected patient (if any)
   */
  getCurrentPatient(): DetectedPatient | null {
    return this.currentPatient;
  }

  /**
   * Update patterns (e.g., from tenant configuration)
   */
  updatePatterns(customPatterns: Partial<PatternConfig>): void {
    this.patterns = mergePatterns(DEFAULT_PATTERNS, customPatterns);
    
    // Re-detect with new patterns
    if (this.isRunning) {
      this.scheduleDetection();
    }
  }

  /**
   * Update patterns from backend response (handles string -> RegExp conversion)
   */
  updatePatternsFromConfig(config: unknown): void {
    const parsed = parsePatternConfig(config);
    this.updatePatterns(parsed);
  }

  /**
   * Check if the detector is currently running
   */
  isActive(): boolean {
    return this.isRunning;
  }

  // ===========================================================================
  // Private Methods
  // ===========================================================================

  private setupMutationObserver(): void {
    this.observer = new MutationObserver((mutations) => {
      // Filter for relevant mutations (avoid triggering on trivial changes)
      const hasRelevantMutation = mutations.some(mutation => {
        // Check for added/removed nodes
        if (mutation.addedNodes.length > 0 || mutation.removedNodes.length > 0) {
          return true;
        }
        
        // Check for attribute changes on relevant elements
        if (mutation.type === 'attributes') {
          const target = mutation.target as Element;
          const attrName = mutation.attributeName || '';
          
          // Debug: log attribute changes
          if (attrName.includes('patient') || attrName.includes('mrn') || attrName.includes('selected')) {
            console.log('[PatientContextDetector] Attribute mutation:', attrName, 'on', target.id || target.className);
          }
          
          // Check if the attribute matches any of our patterns
          return this.patterns.dataAttributes.some(p => p.attr === attrName) ||
                 attrName.includes('patient') ||
                 attrName.includes('mrn') ||
                 attrName.includes('id');
        }
        
        return false;
      });
      
      if (hasRelevantMutation) {
        console.log('[PatientContextDetector] Relevant mutation detected, scheduling detection');
        this.scheduleDetection();
      }
    });

    // Observe the entire document - watch ALL attributes (no filter)
    // to ensure we catch patient context changes
    this.observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      // Removed attributeFilter to catch all attribute changes
      // The callback filters for relevant ones
    });
  }

  private setupUrlChangeDetection(): void {
    // Use popstate for browser navigation
    window.addEventListener('popstate', () => {
      if (window.location.href !== this.lastUrl) {
        this.lastUrl = window.location.href;
        this.scheduleDetection();
      }
    });
    
    // Use MutationObserver on <head> or <title> as a proxy for SPA navigation
    // Many SPAs update the title when navigating
    const titleObserver = new MutationObserver(() => {
      if (window.location.href !== this.lastUrl) {
        this.lastUrl = window.location.href;
        this.scheduleDetection();
      }
    });
    
    const titleElement = document.querySelector('title');
    if (titleElement) {
      titleObserver.observe(titleElement, { childList: true, characterData: true });
    }
    
    // Also check periodically for URL changes (handles edge cases)
    setInterval(() => {
      if (this.isRunning && window.location.href !== this.lastUrl) {
        this.lastUrl = window.location.href;
        this.scheduleDetection();
      }
    }, 1000);
  }

  private scheduleDetection(): void {
    // Cancel any pending detection
    if (this.debounceTimer !== null) {
      window.clearTimeout(this.debounceTimer);
    }
    
    // Schedule new detection
    this.debounceTimer = window.setTimeout(() => {
      this.debounceTimer = null;
      this.detect();
    }, this.options.debounceMs);
  }

  private handleDetectionResult(patient: DetectedPatient | null): void {
    const previousPatient = this.currentPatient;
    
    if (patient === null && previousPatient !== null) {
      // Patient was cleared
      this.currentPatient = null;
      this.emit('patientCleared', null);
      console.log('[PatientContextDetector] Patient context cleared');
    } else if (patient !== null && previousPatient === null) {
      // New patient detected
      this.currentPatient = patient;
      this.emit('patientDetected', patient);
      console.log('[PatientContextDetector] Patient detected:', patient);
    } else if (patient !== null && previousPatient !== null) {
      // Check if patient changed
      if (!this.isSamePatient(patient, previousPatient)) {
        this.currentPatient = patient;
        this.emit('patientChanged', patient);
        console.log('[PatientContextDetector] Patient changed:', patient);
      }
      // If same patient, no event needed
    }
    // If both null, no event needed
  }

  private isSamePatient(a: DetectedPatient, b: DetectedPatient): boolean {
    return a.id_type === b.id_type && a.id_value === b.id_value;
  }

  private emit(event: PatientDetectionEvent, patient: DetectedPatient | null): void {
    const listeners = this.listeners.get(event);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(patient, event);
        } catch (error) {
          console.error(`[PatientContextDetector] Error in ${event} listener:`, error);
        }
      });
    }
  }
}

/**
 * Create a singleton instance for easy use
 */
let defaultDetector: PatientContextDetector | null = null;

export function getDefaultDetector(): PatientContextDetector {
  if (!defaultDetector) {
    defaultDetector = new PatientContextDetector({
      debounceMs: 500,
      strategies: ['dataAttributes', 'url', 'domText'],
      observeMutations: true,
    });
  }
  return defaultDetector;
}

/**
 * Utility function to reset the default detector (mainly for testing)
 */
export function resetDefaultDetector(): void {
  if (defaultDetector) {
    defaultDetector.stop();
    defaultDetector = null;
  }
}
