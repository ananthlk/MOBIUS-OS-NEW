/**
 * ThinkingBox Component
 * Collapsible system thinking/processing display
 */

export interface ThinkingBoxProps {
  content: string[];
  isCollapsed?: boolean;
}

export function ThinkingBox({ content, isCollapsed = false }: ThinkingBoxProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'thinking-box';
  
  const header = document.createElement('div');
  header.className = 'thinking-box-header';
  
  const label = document.createElement('span');
  label.textContent = '🤔 System Thinking';
  
  const arrow = document.createElement('span');
  arrow.className = `thinking-box-arrow ${isCollapsed ? 'collapsed' : ''}`;
  arrow.textContent = '▼';
  
  header.appendChild(label);
  header.appendChild(arrow);
  
  const contentDiv = document.createElement('div');
  contentDiv.className = `thinking-box-content ${isCollapsed ? 'collapsed' : ''}`;
  contentDiv.textContent = content.join('\n');
  
  header.addEventListener('click', () => {
    const newCollapsed = !contentDiv.classList.contains('collapsed');
    contentDiv.classList.toggle('collapsed');
    arrow.classList.toggle('collapsed');
  });
  
  container.appendChild(header);
  container.appendChild(contentDiv);
  
  return container;
}
