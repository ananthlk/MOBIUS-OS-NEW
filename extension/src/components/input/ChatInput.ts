/**
 * ChatInput Component
 * Input field for chat messages with tools
 */

import { ChatTools } from './ChatTools';

export interface ChatInputProps {
  onSend: (message: string) => void;
  placeholder?: string;
}

export function ChatInput({ onSend, placeholder = 'Type your message...' }: ChatInputProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'chat-input-area';
  
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'chat-input';
  input.placeholder = placeholder;
  
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && input.value.trim()) {
      onSend(input.value.trim());
      input.value = '';
    }
  });
  
  container.appendChild(input);
  container.appendChild(ChatTools({}));
  
  return container;
}
