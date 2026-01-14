/**
 * SystemMessage Component
 * System/assistant message display (left-aligned)
 */

import { SystemMessage as SystemMessageType } from '../../types';
import { ThinkingBox } from './ThinkingBox';
import { FeedbackComponent } from '../feedback/FeedbackComponent';
import { GuidanceActions } from '../guidance/GuidanceActions';

export interface SystemMessageProps {
  message: SystemMessageType;
  onFeedbackSubmit?: (messageId: string, rating: 'up' | 'down', feedback?: any) => void;
}

export function SystemMessage({ message, onFeedbackSubmit }: SystemMessageProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'message system-message';
  
  // Thinking box
  if (message.thinkingBox) {
    container.appendChild(ThinkingBox({
      content: message.thinkingBox.content,
      isCollapsed: message.thinkingBox.isCollapsed
    }));
  }
  
  // Message content
  const content = document.createElement('div');
  content.style.marginTop = '8px';
  content.textContent = message.content;
  container.appendChild(content);
  
  // Feedback component
  if (message.feedbackComponent && onFeedbackSubmit) {
    container.appendChild(FeedbackComponent({
      messageId: message.id,
      onSubmit: onFeedbackSubmit,
      isVisible: true
    }));
  }
  
  // Guidance actions
  if (message.guidanceActions && message.guidanceActions.length > 0) {
    container.appendChild(GuidanceActions({
      actions: message.guidanceActions,
      isVisible: true
    }));
  }
  
  return container;
}
