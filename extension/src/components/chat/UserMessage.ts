/**
 * UserMessage Component
 * User message display (right-aligned)
 */

import { UserMessage as UserMessageType } from '../../types';

export interface UserMessageProps {
  message: UserMessageType;
}

export function UserMessage({ message }: UserMessageProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'message user-message';
  container.textContent = message.content;
  return container;
}
