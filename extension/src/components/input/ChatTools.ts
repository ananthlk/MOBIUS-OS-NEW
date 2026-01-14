/**
 * ChatTools Component
 * Standard tools (copy, email, save, more)
 */

export interface ChatTool {
  icon: string;
  label: string;
  onClick: () => void;
}

export interface ChatToolsProps {
  tools?: ChatTool[];
}

const defaultTools: ChatTool[] = [
  { icon: '📋', label: 'Copy', onClick: () => console.log('Copy') },
  { icon: '📧', label: 'Email', onClick: () => console.log('Email') },
  { icon: '💾', label: 'Save', onClick: () => console.log('Save') }
];

const dropdownTools: ChatTool[] = [
  { icon: '🖨️', label: 'Print', onClick: () => console.log('Print') },
  { icon: '📤', label: 'Export', onClick: () => console.log('Export') }
];

export function ChatTools({ tools = defaultTools }: ChatToolsProps): HTMLElement {
  const container = document.createElement('div');
  container.className = 'chat-tools';
  
  tools.forEach(tool => {
    const button = document.createElement('button');
    button.className = 'chat-tool-btn';
    button.textContent = tool.icon;
    button.title = tool.label;
    button.addEventListener('click', tool.onClick);
    container.appendChild(button);
  });
  
  // More tools dropdown
  const menuContainer = document.createElement('div');
  menuContainer.className = 'tools-menu';
  
  const menuBtn = document.createElement('button');
  menuBtn.className = 'chat-tool-btn tools-menu-btn';
  menuBtn.textContent = '⋯';
  menuBtn.title = 'More';
  
  const dropdown = document.createElement('div');
  dropdown.className = 'tools-dropdown';
  dropdown.id = 'toolsDropdown';
  
  dropdownTools.forEach(tool => {
    const btn = document.createElement('button');
    btn.textContent = `${tool.icon} ${tool.label}`;
    btn.addEventListener('click', () => {
      tool.onClick();
      dropdown.classList.remove('show');
    });
    dropdown.appendChild(btn);
  });
  
  menuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('show');
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!menuContainer.contains(e.target as Node)) {
      dropdown.classList.remove('show');
    }
  });
  
  menuContainer.appendChild(menuBtn);
  menuContainer.appendChild(dropdown);
  container.appendChild(menuContainer);
  
  return container;
}
