/**
 * ThinkingBox Component
 * Collapsible system thinking/processing display
 */

export interface ThinkingBoxProps {
  content: string[];
  isCollapsed?: boolean;
}

export function ThinkingBox({ content, isCollapsed = true }: ThinkingBoxProps): HTMLElement {
  // Minimalist, reliable collapse using native <details>/<summary>
  const details = document.createElement('details');
  details.className = 'thinking-line';
  details.open = !isCollapsed;

  const summary = document.createElement('summary');
  summary.className = 'thinking-summary';
  summary.textContent = 'Thinking';

  const body = document.createElement('div');
  body.className = 'thinking-body';
  body.textContent = content.join('\n');

  details.appendChild(summary);
  details.appendChild(body);
  return details;
}
