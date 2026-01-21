/**
 * Data Hierarchy Service
 * 
 * Resolves data precedence when multiple sources have different values.
 * Hierarchy: User (real-time) > Page (detected) > Backend (knowledge) > Batch (periodic)
 */

import type { BottleneckSources, SourceType } from '../types/record';

/**
 * Source priority order (higher index = higher priority)
 */
const SOURCE_PRIORITY: SourceType[] = ['batch', 'backend', 'page', 'user'];

/**
 * Source display badges
 */
const SOURCE_BADGES: Record<SourceType, string> = {
  batch: '🌙',      // Moon = ran overnight/periodically
  backend: '📚',    // Book = from knowledge base
  page: '📄',       // Document = from current page
  user: '✓',        // Checkmark = user confirmed
};

/**
 * Source display labels
 */
const SOURCE_LABELS: Record<SourceType, string> = {
  batch: 'From batch analysis',
  backend: 'From system records',
  page: 'Detected on page',
  user: 'You confirmed',
};

/**
 * Result of resolving data hierarchy
 */
export interface ResolvedValue {
  value: string;
  source: SourceType;
  timestamp: string;
  hasConflict: boolean;
  conflictingSources?: SourceType[];
}

/**
 * Resolve the highest-priority value from multiple sources
 */
export function resolveValue(sources: BottleneckSources): ResolvedValue | null {
  // Collect all available sources with their values
  const available: Array<{ source: SourceType; value: string; timestamp: string }> = [];
  
  if (sources.user) {
    available.push({ source: 'user', value: sources.user.value, timestamp: sources.user.set_at });
  }
  if (sources.page) {
    available.push({ source: 'page', value: sources.page.value, timestamp: sources.page.detected_at });
  }
  if (sources.backend) {
    available.push({ source: 'backend', value: sources.backend.value, timestamp: sources.backend.fetched_at });
  }
  if (sources.batch) {
    available.push({ source: 'batch', value: sources.batch.value, timestamp: sources.batch.updated_at });
  }
  
  if (available.length === 0) {
    return null;
  }
  
  // Sort by priority (highest first)
  available.sort((a, b) => 
    SOURCE_PRIORITY.indexOf(b.source) - SOURCE_PRIORITY.indexOf(a.source)
  );
  
  const winner = available[0];
  
  // Check for conflicts (different values from different sources)
  const uniqueValues = new Set(available.map(s => s.value.toLowerCase().trim()));
  const hasConflict = uniqueValues.size > 1;
  
  let conflictingSources: SourceType[] | undefined;
  if (hasConflict) {
    conflictingSources = available
      .filter(s => s.value.toLowerCase().trim() !== winner.value.toLowerCase().trim())
      .map(s => s.source);
  }
  
  return {
    value: winner.value,
    source: winner.source,
    timestamp: winner.timestamp,
    hasConflict,
    conflictingSources,
  };
}

/**
 * Check if sources have conflicting values
 */
export function hasConflict(sources: BottleneckSources): boolean {
  const values: string[] = [];
  
  if (sources.user) values.push(sources.user.value.toLowerCase().trim());
  if (sources.page) values.push(sources.page.value.toLowerCase().trim());
  if (sources.backend) values.push(sources.backend.value.toLowerCase().trim());
  if (sources.batch) values.push(sources.batch.value.toLowerCase().trim());
  
  const uniqueValues = new Set(values);
  return uniqueValues.size > 1;
}

/**
 * Get the display badge for a source type
 */
export function getSourceBadge(source: SourceType): string {
  return SOURCE_BADGES[source] || '';
}

/**
 * Get the display label for a source type
 */
export function getSourceLabel(source: SourceType): string {
  return SOURCE_LABELS[source] || 'Unknown source';
}

/**
 * Format a conflict message for display
 */
export function formatConflictMessage(sources: BottleneckSources): string | null {
  const resolved = resolveValue(sources);
  if (!resolved || !resolved.hasConflict || !resolved.conflictingSources) {
    return null;
  }
  
  // Get the conflicting value (from highest priority conflicting source)
  const conflictSource = resolved.conflictingSources[0];
  const conflictValue = sources[conflictSource]?.value || 'different value';
  
  return `Using "${resolved.value}" (${getSourceLabel(resolved.source)}). ` +
    `${getSourceLabel(conflictSource)} shows "${conflictValue}".`;
}

/**
 * Build a summary of all sources for tooltip/detail view
 */
export function buildSourcesSummary(sources: BottleneckSources): string[] {
  const summary: string[] = [];
  
  if (sources.user) {
    summary.push(`${SOURCE_BADGES.user} You: "${sources.user.value}" (${formatTimestamp(sources.user.set_at)})`);
  }
  if (sources.page) {
    summary.push(`${SOURCE_BADGES.page} Page: "${sources.page.value}" (${formatTimestamp(sources.page.detected_at)})`);
  }
  if (sources.backend) {
    summary.push(`${SOURCE_BADGES.backend} System: "${sources.backend.value}" (${formatTimestamp(sources.backend.fetched_at)})`);
  }
  if (sources.batch) {
    summary.push(`${SOURCE_BADGES.batch} Batch: "${sources.batch.value}" (${formatTimestamp(sources.batch.updated_at)})`);
  }
  
  return summary;
}

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
  } catch {
    return 'unknown time';
  }
}

/**
 * Get relative time string
 */
export function getRelativeTime(isoString: string): string {
  return formatTimestamp(isoString);
}
