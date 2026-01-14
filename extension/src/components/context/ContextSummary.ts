/**
 * ContextSummary Component
 * Summary of current context/work
 */

export interface ContextSummaryProps {
  summary: string;
}

export function ContextSummary({ summary }: ContextSummaryProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'context-summary';
  container.innerHTML = `<strong>Context:</strong> ${summary}`;
  return container;
}
