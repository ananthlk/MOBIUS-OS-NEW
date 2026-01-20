/**
 * Pattern Matchers for Patient Context Detection
 * 
 * Defines detection patterns for various EMR systems including:
 * - Epic
 * - Cerner
 * - Athena
 * - Allscripts
 * - Generic/Legacy patterns
 * 
 * These patterns are used by PatientContextDetector to identify patient
 * identifiers on webpages through data attributes, URL parameters, and DOM text.
 */

import {
  PatternConfig,
  DataAttributePattern,
  UrlPattern,
  TextPattern,
  DetectedPatient,
  PatientIdType,
  EmrSourceHint,
  DetectionConfidence,
} from '../types';

// =============================================================================
// Default Pattern Definitions
// =============================================================================

/**
 * Data attribute patterns for different EMR systems
 * These are checked first as they provide the most reliable detection
 */
export const DEFAULT_DATA_ATTRIBUTE_PATTERNS: DataAttributePattern[] = [
  // Selected patient context (highest priority - set by EMR when patient is selected)
  // Check the hidden context element first (always present, always updated)
  { attr: 'data-patient-mrn', type: 'mrn', source: 'context', selector: '#mobius-patient-context' },
  // Then check visible detail panels
  { attr: 'data-selected-patient-mrn', type: 'mrn', source: 'selected', selector: '.detail-panel[style*="block"]' },
  { attr: 'data-selected-patient-mrn', type: 'mrn', source: 'selected' },
  
  // Epic patterns
  { attr: 'data-patient-mrn', type: 'mrn', source: 'epic' },
  { attr: 'data-patient-name', type: 'patient_key', source: 'epic' },
  { attr: 'data-epic-mrn', type: 'mrn', source: 'epic' },
  { attr: 'data-epic-patient-id', type: 'patient_key', source: 'epic' },
  
  // Cerner patterns
  { attr: 'data-cerner-mrn', type: 'mrn', source: 'cerner' },
  { attr: 'data-cerner-patient', type: 'patient_key', source: 'cerner' },
  { attr: 'data-cerner-patient-id', type: 'patient_key', source: 'cerner' },
  
  // Athena patterns
  { attr: 'data-athena-record-number', type: 'mrn', source: 'athena' },
  { attr: 'data-athena-full-name', type: 'patient_key', source: 'athena' },
  { attr: 'data-athena-patient-id', type: 'patient_key', source: 'athena' },
  
  // Allscripts patterns
  { attr: 'data-allscripts-id', type: 'mrn', source: 'allscripts' },
  { attr: 'data-allscripts-name', type: 'patient_key', source: 'allscripts' },
  { attr: 'data-allscripts-mrn', type: 'mrn', source: 'allscripts' },
  
  // Netsmart (myAvatar) patterns
  { attr: 'data-netsmart-mrn', type: 'mrn', source: 'netsmart' },
  { attr: 'data-netsmart-client', type: 'patient_key', source: 'netsmart' },
  
  // Qualifacts (CareLogic) patterns
  { attr: 'data-qualifacts-mrn', type: 'mrn', source: 'qualifacts' },
  { attr: 'data-qualifacts-client', type: 'patient_key', source: 'qualifacts' },
  
  // Generic/legacy patterns (lowest priority)
  { attr: 'data-id', type: 'mrn', source: 'legacy' },
  { attr: 'data-name', type: 'patient_key', source: 'legacy' },
  { attr: 'data-mrn', type: 'mrn', source: 'unknown' },
  { attr: 'data-patient-id', type: 'patient_key', source: 'unknown' },
  { attr: 'data-record-id', type: 'mrn', source: 'unknown' },
];

/**
 * URL patterns for extracting patient identifiers
 * Supports query parameters and path segments
 */
export const DEFAULT_URL_PATTERNS: UrlPattern[] = [
  // Query parameter patterns
  { regex: /[?&]mrn=([^&]+)/i, type: 'mrn' },
  { regex: /[?&]MRN=([^&]+)/, type: 'mrn' },
  { regex: /[?&]patient_id=([^&]+)/i, type: 'patient_key' },
  { regex: /[?&]patientId=([^&]+)/i, type: 'patient_key' },
  { regex: /[?&]patient=([^&]+)/i, type: 'patient_key' },
  { regex: /[?&]record_id=([^&]+)/i, type: 'mrn' },
  { regex: /[?&]chart_id=([^&]+)/i, type: 'mrn' },
  
  // Path segment patterns
  { regex: /\/patient\/([A-Za-z0-9-]+)/i, type: 'patient_key' },
  { regex: /\/patients\/([A-Za-z0-9-]+)/i, type: 'patient_key' },
  { regex: /\/chart\/([A-Za-z0-9-]+)/i, type: 'mrn' },
  { regex: /\/record\/([A-Za-z0-9-]+)/i, type: 'mrn' },
  { regex: /\/mrn\/([A-Za-z0-9-]+)/i, type: 'mrn' },
  
  // EMR-specific URL patterns
  { regex: /\/Epic\/Patient\/([A-Za-z0-9-]+)/i, type: 'patient_key' },
  { regex: /\/powerchart\/patient\/([A-Za-z0-9-]+)/i, type: 'patient_key' },
  { regex: /\/athenaone\/patient\/([A-Za-z0-9-]+)/i, type: 'patient_key' },
];

/**
 * DOM text patterns for extracting patient identifiers from page content
 * These are checked last as they can be less reliable
 */
export const DEFAULT_TEXT_PATTERNS: TextPattern[] = [
  // MRN patterns
  { regex: /MRN[:\s]+([A-Z0-9-]+)/i, type: 'mrn' },
  { regex: /Medical\s*Record\s*(?:Number|#|No\.?)[:\s]+([A-Z0-9-]+)/i, type: 'mrn' },
  { regex: /Record\s*#[:\s]*([A-Z0-9-]+)/i, type: 'mrn' },
  { regex: /Chart\s*#[:\s]*([A-Z0-9-]+)/i, type: 'mrn' },
  
  // Patient ID patterns
  { regex: /Patient\s*ID[:\s]+([A-Z0-9-]+)/i, type: 'patient_key' },
  { regex: /Patient\s*#[:\s]*([A-Z0-9-]+)/i, type: 'patient_key' },
  { regex: /Patient\s*Number[:\s]+([A-Z0-9-]+)/i, type: 'patient_key' },
  
  // Account/encounter patterns
  { regex: /Account\s*#[:\s]*([A-Z0-9-]+)/i, type: 'patient_key' },
  { regex: /Encounter\s*#[:\s]*([A-Z0-9-]+)/i, type: 'patient_key' },
];

/**
 * Complete default pattern configuration
 */
export const DEFAULT_PATTERNS: PatternConfig = {
  dataAttributes: DEFAULT_DATA_ATTRIBUTE_PATTERNS,
  urlPatterns: DEFAULT_URL_PATTERNS,
  textPatterns: DEFAULT_TEXT_PATTERNS,
};

// =============================================================================
// Pattern Matcher Functions
// =============================================================================

/**
 * Scan DOM elements for data attributes matching patient identifier patterns
 */
export function matchDataAttributes(
  patterns: DataAttributePattern[] = DEFAULT_DATA_ATTRIBUTE_PATTERNS,
  root: Document | Element = document
): DetectedPatient | null {
  // Debug: Check if mobius-patient-context exists
  const contextEl = document.getElementById('mobius-patient-context');
  if (contextEl) {
    const contextMrn = contextEl.getAttribute('data-patient-mrn');
    console.log('[PatternMatcher] Context element found, MRN:', contextMrn);
    if (contextMrn && contextMrn.trim()) {
      return {
        id_type: 'mrn',
        id_value: contextMrn.trim(),
        source_hint: 'context',
        confidence: 'high',
        detected_at: new Date().toISOString(),
      };
    }
  }
  
  for (const pattern of patterns) {
    const selector = pattern.selector 
      ? `${pattern.selector}[${pattern.attr}]`
      : `[${pattern.attr}]`;
    
    const element = root.querySelector(selector);
    if (element) {
      const value = element.getAttribute(pattern.attr);
      if (value && value.trim()) {
        console.log('[PatternMatcher] Found:', pattern.attr, '=', value, 'on', (element as HTMLElement).id || (element as HTMLElement).className);
        return {
          id_type: pattern.type,
          id_value: value.trim(),
          source_hint: pattern.source,
          confidence: 'high',
          detected_at: new Date().toISOString(),
        };
      }
    }
  }
  return null;
}

/**
 * Extract patient identifier from URL using defined patterns
 */
export function matchUrlPatterns(
  patterns: UrlPattern[] = DEFAULT_URL_PATTERNS,
  url: string = window.location.href
): DetectedPatient | null {
  for (const pattern of patterns) {
    const regex = typeof pattern.regex === 'string' 
      ? new RegExp(pattern.regex) 
      : pattern.regex;
    
    const match = url.match(regex);
    if (match) {
      const captureGroup = pattern.captureGroup ?? 1;
      const value = match[captureGroup];
      if (value && value.trim()) {
        return {
          id_type: pattern.type,
          id_value: decodeURIComponent(value.trim()),
          source_hint: 'url',
          confidence: 'high',
          detected_at: new Date().toISOString(),
        };
      }
    }
  }
  return null;
}

/**
 * Scan DOM text content for patient identifier patterns
 */
export function matchTextPatterns(
  patterns: TextPattern[] = DEFAULT_TEXT_PATTERNS,
  root: Document | Element = document
): DetectedPatient | null {
  for (const pattern of patterns) {
    const regex = typeof pattern.regex === 'string'
      ? new RegExp(pattern.regex)
      : pattern.regex;
    
    // Get text content to search
    let textContent: string;
    if (pattern.selector) {
      const element = root.querySelector(pattern.selector);
      textContent = element?.textContent || '';
    } else {
      // Search in common areas that typically contain patient info
      const searchAreas = [
        'header',
        '[class*="patient"]',
        '[class*="header"]',
        '[class*="banner"]',
        '[id*="patient"]',
        'main',
      ];
      
      textContent = '';
      for (const selector of searchAreas) {
        const elements = root.querySelectorAll(selector);
        elements.forEach(el => {
          textContent += ' ' + (el.textContent || '');
        });
      }
      
      // Fallback to body if nothing found
      if (!textContent.trim()) {
        textContent = (root as Document).body?.textContent || '';
      }
    }
    
    const match = textContent.match(regex);
    if (match) {
      const captureGroup = pattern.captureGroup ?? 1;
      const value = match[captureGroup];
      if (value && value.trim()) {
        return {
          id_type: pattern.type,
          id_value: value.trim(),
          source_hint: 'text',
          confidence: 'medium',
          detected_at: new Date().toISOString(),
        };
      }
    }
  }
  return null;
}

/**
 * Run all detection strategies in priority order
 */
export function detectPatient(
  strategies: Array<'dataAttributes' | 'url' | 'domText'> = ['dataAttributes', 'url', 'domText'],
  patterns: PatternConfig = DEFAULT_PATTERNS
): DetectedPatient | null {
  for (const strategy of strategies) {
    let result: DetectedPatient | null = null;
    
    switch (strategy) {
      case 'dataAttributes':
        result = matchDataAttributes(patterns.dataAttributes);
        break;
      case 'url':
        result = matchUrlPatterns(patterns.urlPatterns);
        break;
      case 'domText':
        result = matchTextPatterns(patterns.textPatterns);
        break;
    }
    
    if (result) {
      return result;
    }
  }
  
  return null;
}

/**
 * Merge custom patterns with defaults
 */
export function mergePatterns(
  defaults: PatternConfig,
  custom: Partial<PatternConfig>
): PatternConfig {
  return {
    dataAttributes: [
      ...(custom.dataAttributes || []),
      ...defaults.dataAttributes,
    ],
    urlPatterns: [
      ...(custom.urlPatterns || []),
      ...defaults.urlPatterns,
    ],
    textPatterns: [
      ...(custom.textPatterns || []),
      ...defaults.textPatterns,
    ],
  };
}

/**
 * Convert backend pattern config (with string regexes) to runtime config
 */
export function parsePatternConfig(config: unknown): Partial<PatternConfig> {
  if (!config || typeof config !== 'object') {
    return {};
  }
  
  const parsed: Partial<PatternConfig> = {};
  const c = config as Record<string, unknown>;
  
  if (Array.isArray(c.dataAttributes)) {
    parsed.dataAttributes = c.dataAttributes as DataAttributePattern[];
  }
  
  if (Array.isArray(c.urlPatterns)) {
    parsed.urlPatterns = (c.urlPatterns as Array<{ regex: string; type: PatientIdType; captureGroup?: number }>)
      .map(p => ({
        regex: new RegExp(p.regex),
        type: p.type,
        captureGroup: p.captureGroup,
      }));
  }
  
  if (Array.isArray(c.textPatterns)) {
    parsed.textPatterns = (c.textPatterns as Array<{ regex: string; type: PatientIdType; captureGroup?: number; selector?: string }>)
      .map(p => ({
        regex: new RegExp(p.regex),
        type: p.type,
        captureGroup: p.captureGroup,
        selector: p.selector,
      }));
  }
  
  return parsed;
}
