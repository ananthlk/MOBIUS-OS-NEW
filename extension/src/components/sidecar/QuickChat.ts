/**
 * QuickChat Component
 * 
 * Single-line chat input at bottom of sidecar.
 * Uses knowledge context for intelligent responses.
 */

import type { KnowledgeContext, RecordContext } from '../../types/record';

export interface QuickChatProps {
  record: RecordContext;
  knowledgeContext: KnowledgeContext;
  onSend: (message: string) => void;
  placeholder?: string;
}

/**
 * Create the QuickChat element
 */
export function QuickChat(props: QuickChatProps): HTMLElement {
  const { record, onSend, placeholder } = props;
  
  const container = document.createElement('div');
  container.className = 'sidecar-quick-chat';
  
  // Input wrapper
  const inputWrapper = document.createElement('div');
  inputWrapper.className = 'sidecar-quick-chat-wrapper';
  
  // Input field
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'sidecar-quick-chat-input';
  input.placeholder = placeholder || `Ask about ${record.shortName}...`;
  
  // Send button
  const sendBtn = document.createElement('button');
  sendBtn.className = 'sidecar-quick-chat-send';
  sendBtn.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
    </svg>
  `;
  sendBtn.disabled = true;
  sendBtn.title = 'Send';
  
  // Enable/disable send button based on input
  input.addEventListener('input', () => {
    sendBtn.disabled = input.value.trim().length === 0;
  });
  
  // Send on button click
  sendBtn.addEventListener('click', () => {
    const message = input.value.trim();
    if (message) {
      onSend(message);
      input.value = '';
      sendBtn.disabled = true;
    }
  });
  
  // Send on Enter key
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const message = input.value.trim();
      if (message) {
        onSend(message);
        input.value = '';
        sendBtn.disabled = true;
      }
    }
  });
  
  inputWrapper.appendChild(input);
  inputWrapper.appendChild(sendBtn);
  container.appendChild(inputWrapper);
  
  // Hint text
  const hint = document.createElement('div');
  hint.className = 'sidecar-quick-chat-hint';
  hint.textContent = 'Ask questions about coverage, auth requirements, history...';
  container.appendChild(hint);
  
  return container;
}

/**
 * Show loading state in chat
 */
export function setQuickChatLoading(element: HTMLElement, loading: boolean): void {
  const input = element.querySelector('.sidecar-quick-chat-input') as HTMLInputElement;
  const sendBtn = element.querySelector('.sidecar-quick-chat-send') as HTMLButtonElement;
  
  if (input && sendBtn) {
    input.disabled = loading;
    sendBtn.disabled = loading || input.value.trim().length === 0;
    
    if (loading) {
      sendBtn.textContent = '…';
    } else {
      sendBtn.innerHTML = `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
        </svg>
      `;
    }
  }
}

/**
 * Show a response in the chat area
 */
export function showQuickChatResponse(element: HTMLElement, response: string, source?: string): void {
  // Find or create response area
  let responseArea = element.querySelector('.sidecar-quick-chat-response') as HTMLElement;
  if (!responseArea) {
    responseArea = document.createElement('div');
    responseArea.className = 'sidecar-quick-chat-response';
    element.insertBefore(responseArea, element.querySelector('.sidecar-quick-chat-wrapper'));
  }
  
  // Clear previous response
  responseArea.innerHTML = '';
  
  // Response text
  const text = document.createElement('div');
  text.className = 'sidecar-quick-chat-response-text';
  text.textContent = response;
  responseArea.appendChild(text);
  
  // Source citation (if provided)
  if (source) {
    const citation = document.createElement('div');
    citation.className = 'sidecar-quick-chat-response-source';
    citation.textContent = `Source: ${source}`;
    responseArea.appendChild(citation);
  }
  
  // Dismiss button
  const dismissBtn = document.createElement('button');
  dismissBtn.className = 'sidecar-quick-chat-response-dismiss';
  dismissBtn.textContent = '×';
  dismissBtn.addEventListener('click', () => {
    responseArea.remove();
  });
  responseArea.appendChild(dismissBtn);
}

/**
 * Clear any response
 */
export function clearQuickChatResponse(element: HTMLElement): void {
  const responseArea = element.querySelector('.sidecar-quick-chat-response');
  if (responseArea) {
    responseArea.remove();
  }
}
