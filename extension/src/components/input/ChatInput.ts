/**
 * ChatInput Component
 * Multiline input for chat messages (wraps)
 */

export interface ChatInputProps {
  onSend: (message: string) => void;
  placeholder?: string;
}

export function ChatInput({ onSend, placeholder = 'Type your message...' }: ChatInputProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'chat-input-area';
  
  const input = document.createElement('textarea');
  input.className = 'chat-input';
  input.placeholder = placeholder;
  input.rows = 1;

  const autosize = () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  };
  input.addEventListener('input', autosize);
  autosize();

  input.addEventListener('keydown', (e) => {
    // Enter sends, Shift+Enter adds a newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      onSend(text);
      input.value = '';
      autosize();
    }
  });

  container.appendChild(input);
  
  return container;
}
