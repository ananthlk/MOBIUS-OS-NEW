/**
 * QuickChat Component
 * 
 * Chat area with message container and input.
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
  
  // Messages container (bounded, scrollable area for 4-5 lines)
  const messagesContainer = document.createElement('div');
  messagesContainer.className = 'sidecar-chat-messages';
  
  // Empty state placeholder
  const emptyState = document.createElement('div');
  emptyState.className = 'sidecar-chat-empty';
  emptyState.textContent = 'Ask questions about coverage, auth requirements, history...';
  messagesContainer.appendChild(emptyState);
  
  container.appendChild(messagesContainer);
  
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
 * Add a user message to the chat
 */
export function addUserMessage(element: HTMLElement, message: string): void {
  const messagesContainer = element.querySelector('.sidecar-chat-messages');
  if (!messagesContainer) return;
  
  // Remove empty state if present
  const emptyState = messagesContainer.querySelector('.sidecar-chat-empty');
  if (emptyState) emptyState.remove();
  
  // Add user message
  const msgEl = document.createElement('div');
  msgEl.className = 'sidecar-chat-message user-message';
  msgEl.textContent = message;
  messagesContainer.appendChild(msgEl);
  
  // Scroll to bottom
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Update (or create) a transient status line — used while an answer is
 * being generated. Replaced in place on every update, removed on finish.
 */
export function setQuickChatStatus(element: HTMLElement, status: string | null): void {
  const messagesContainer = element.querySelector('.sidecar-chat-messages');
  if (!messagesContainer) return;
  let statusEl = messagesContainer.querySelector('.sidecar-chat-status') as HTMLElement | null;
  if (status === null) {
    statusEl?.remove();
    return;
  }
  if (!statusEl) {
    statusEl = document.createElement('div');
    statusEl.className = 'sidecar-chat-status';
    statusEl.style.cssText = 'font-size: 10px; color: #94a3b8; font-style: italic; padding: 4px 2px;';
    messagesContainer.appendChild(statusEl);
  }
  statusEl.textContent = status;
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Render markdown-lite (bold + bullet lines) into safe DOM nodes.
 * LLM output never touches innerHTML.
 */
function renderMarkdownLite(target: HTMLElement, markdown: string): void {
  const appendInline = (parent: HTMLElement, line: string) => {
    const parts = line.split('**');
    parts.forEach((part, i) => {
      if (!part) return;
      if (i % 2 === 1) {
        const b = document.createElement('strong');
        b.textContent = part;
        parent.appendChild(b);
      } else {
        parent.appendChild(document.createTextNode(part));
      }
    });
  };
  markdown.split('\n').forEach((rawLine) => {
    const line = rawLine.trimEnd();
    if (!line.trim()) return;
    const el = document.createElement('div');
    const bullet = line.match(/^\s*[*-]\s+(.*)$/);
    if (bullet) {
      el.style.cssText = 'padding-left: 12px; text-indent: -8px;';
      el.appendChild(document.createTextNode('• '));
      appendInline(el, bullet[1]);
    } else {
      appendInline(el, line);
    }
    target.appendChild(el);
  });
}

/**
 * Show a response in the chat area
 */
export function showQuickChatResponse(element: HTMLElement, response: string, source?: string): void {
  const messagesContainer = element.querySelector('.sidecar-chat-messages');
  if (!messagesContainer) return;

  // Remove empty state if present
  const emptyState = messagesContainer.querySelector('.sidecar-chat-empty');
  if (emptyState) emptyState.remove();

  // Add system response
  const msgEl = document.createElement('div');
  msgEl.className = 'sidecar-chat-message system-message';

  // Response text (markdown-lite: bold + bullets)
  const text = document.createElement('div');
  text.className = 'sidecar-chat-message-text';
  renderMarkdownLite(text, response);
  msgEl.appendChild(text);
  
  // Source citation (if provided)
  if (source) {
    const citation = document.createElement('div');
    citation.className = 'sidecar-chat-message-source';
    citation.textContent = `Source: ${source}`;
    msgEl.appendChild(citation);
  }
  
  messagesContainer.appendChild(msgEl);
  
  // Scroll to bottom
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
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
