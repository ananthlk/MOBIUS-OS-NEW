/**
 * TaskItem Component
 * Individual task/reminder item
 */

import { Task, TaskType } from '../../types';

export interface TaskItemProps {
  task: Task;
  onToggle: (taskId: string, checked: boolean) => void;
}

export function TaskItem({ task, onToggle }: TaskItemProps): HTMLElement {
  const container = document.createElement('div');
  container.className = `task-item ${task.type}`;
  
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.id = `task-${task.id}`;
  checkbox.checked = task.checked;
  checkbox.disabled = task.disabled;
  checkbox.addEventListener('change', (e) => {
    onToggle(task.id, (e.target as HTMLInputElement).checked);
  });
  
  const label = document.createElement('label');
  label.htmlFor = `task-${task.id}`;
  label.textContent = task.label;
  
  container.appendChild(checkbox);
  container.appendChild(label);
  
  return container;
}
