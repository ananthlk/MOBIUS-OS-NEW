/**
 * TasksPanel Component
 * Collapsible panel for tasks and reminders
 */

import { Task } from '../../types';
import { TaskItem, TaskItemProps } from './TaskItem';

export interface TasksPanelProps {
  tasks: Task[];
  status: 'active' | 'pending';
  isCollapsed?: boolean;
  onTaskToggle: (taskId: string, checked: boolean) => void;
}

export function TasksPanel({ tasks, status, isCollapsed = false, onTaskToggle }: TasksPanelProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'tasks-panel';
  
  const header = document.createElement('div');
  header.className = 'tasks-panel-header';
  
  const left = document.createElement('div');
  left.style.display = 'flex';
  left.style.alignItems = 'center';
  
  const statusIndicator = document.createElement('span');
  statusIndicator.className = `tasks-status-indicator tasks-status-${status}`;
  left.appendChild(statusIndicator);
  
  const label = document.createElement('span');
  label.textContent = '📋 Tasks & Reminders';
  left.appendChild(label);
  
  const arrow = document.createElement('span');
  arrow.textContent = isCollapsed ? '▶' : '▼';
  arrow.id = 'tasksArrow';
  
  header.appendChild(left);
  header.appendChild(arrow);
  
  const content = document.createElement('div');
  content.className = `tasks-panel-content ${isCollapsed ? '' : 'show'}`;
  content.id = 'tasksContent';
  
  tasks.forEach(task => {
    content.appendChild(TaskItem({ task, onToggle: onTaskToggle }));
  });
  
  header.addEventListener('click', () => {
    const newCollapsed = !content.classList.contains('show');
    content.classList.toggle('show');
    arrow.textContent = newCollapsed ? '▶' : '▼';
  });
  
  container.appendChild(header);
  container.appendChild(content);
  
  return container;
}
