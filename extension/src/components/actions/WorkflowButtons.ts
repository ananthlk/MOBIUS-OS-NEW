/**
 * WorkflowButtons Component
 * Workflow-specific action buttons
 */

export interface WorkflowButton {
  label: string;
  onClick: () => void;
}

export interface WorkflowButtonsProps {
  buttons: WorkflowButton[];
}

export function WorkflowButtons({ buttons }: WorkflowButtonsProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'workflow-buttons';
  
  buttons.forEach(button => {
    const btn = document.createElement('button');
    btn.className = 'context-button';
    btn.textContent = button.label;
    btn.addEventListener('click', button.onClick);
    container.appendChild(btn);
  });
  
  return container;
}
