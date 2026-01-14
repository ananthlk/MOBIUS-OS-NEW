/**
 * ChatArea Component
 * Container for chat messages
 */

import { Message } from '../../types';
import { SystemMessage, SystemMessageProps } from './SystemMessage';
import { UserMessage } from './UserMessage';

export interface ChatAreaProps {
  messages: Message[];
  onFeedbackSubmit?: (messageId: string, rating: 'up' | 'down', feedback?: any) => void;
}

export function ChatArea({ messages, onFeedbackSubmit }: ChatAreaProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'chat-area';
  
  messages.forEach((message) => {
    if (message.type === 'user') {
      container.appendChild(UserMessage({ message: message as import('../../types').UserMessage }));
    } else {
      const systemMessage = message as import('../../types').SystemMessage;
      container.appendChild(SystemMessage({ 
        message: systemMessage,
        onFeedbackSubmit
      }));
    }
  });
  
  // Scroll to bottom
  setTimeout(() => {
    container.scrollTop = container.scrollHeight;
  }, 0);
  
  return container;
}
