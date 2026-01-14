/**
 * Content script for Mobius OS extension
 * Injects the Mobius OS sidebar into web pages
 */

import './styles/sidebar.css';
import { getOrCreateSessionId } from './utils/session';
import { sendChatMessage } from './services/api';
import { getUiDefaultsForMode } from './utils/uiDefaults';
import { 
  ClientLogo, 
  MobiusLogo, 
  ContextDisplay,
  AlertButton,
  SettingsButton,
  ContextSummary,
  QuickActionButton,
  TasksPanel,
  ChatArea,
  ChatInput,
  RecordIDInput,
  WorkflowButtons,
  UserDetails,
  PreferencesPanel
} from './components';
import { Message, Status, Task, StatusIndicatorStatus, LLMChoice, AgentMode } from './types';

// App state
let sessionId: string;
let messages: Message[] = [];
let mobiusStatus: Status = 'idle';
let currentMode = 'Chat';
let currentStatus: StatusIndicatorStatus = 'proceed';
let recordType: 'Patient ID' | 'Claim ID' | 'Visit ID' | 'Authorization ID' | 'Other' = 'Patient ID';
let recordId = '';
let llmChoice: LLMChoice = 'Gemini';
let agentMode: AgentMode = 'Agentic';
let tasks: Task[] = [];
let sidebarContainer: HTMLElement | null = null;

function setVisible(el: HTMLElement, visible: boolean) {
  el.style.display = visible ? '' : 'none';
}

// Initialize sidebar
async function initSidebar() {
  console.log('[Mobius OS] Initializing sidebar...');
  
  // Check if sidebar already exists
  if (document.getElementById('mobius-os-sidebar')) {
    console.log('[Mobius OS] Sidebar already exists, skipping initialization');
    return Promise.resolve();
  }

  // Create sidebar container
  sidebarContainer = document.createElement('div');
  sidebarContainer.id = 'mobius-os-sidebar';
  sidebarContainer.setAttribute('style', `
    position: fixed !important;
    top: 0 !important;
    right: 0 !important;
    width: 450px !important;
    height: 100vh !important;
    min-height: 100vh !important;
    max-height: 100vh !important;
    background: white !important;
    z-index: 2147483647 !important;
    box-shadow: -2px 0 8px rgba(0,0,0,0.1) !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
    margin: 0 !important;
    padding: 0 !important;
  `);

  // Adjust page content to make room for sidebar
  const style = document.createElement('style');
  style.id = 'mobius-os-page-adjust';
  style.textContent = `
    body {
      margin-right: 450px !important;
      transition: margin-right 0.3s ease !important;
    }
    html {
      overflow-x: hidden !important;
    }
  `;
  document.head.appendChild(style);

  // Get or create session ID
  sessionId = await getOrCreateSessionId();

  // Create top row / header
  const topRow = document.createElement('div');
  topRow.className = 'top-row';
  
  const headerLeft = document.createElement('div');
  headerLeft.className = 'header-left';
  
  headerLeft.appendChild(ClientLogo({ clientName: 'CMHC' }));
  
  const logoSection = document.createElement('div');
  logoSection.className = 'logo-section';
  const mobiusLogo = MobiusLogo({ status: mobiusStatus });
  logoSection.appendChild(mobiusLogo);
  const logoLabel = document.createElement('span');
  logoLabel.className = 'logo-label';
  logoLabel.textContent = 'Mobius OS';
  logoSection.appendChild(logoLabel);
  headerLeft.appendChild(logoSection);
  
  topRow.appendChild(headerLeft);
  let contextDisplayEl = ContextDisplay({ status: currentStatus, mode: currentMode });
  topRow.appendChild(contextDisplayEl);

  const headerActions = document.createElement('div');
  headerActions.className = 'header-actions';
  headerActions.appendChild(AlertButton({ 
    hasAlerts: false, 
    onClick: () => alert('Live Alerts:\n- No active alerts') 
  }));
  headerActions.appendChild(SettingsButton({ onClick: () => alert('Settings') }));
  topRow.appendChild(headerActions);
  
  sidebarContainer.appendChild(topRow);

  // Second row - context summary
  const secondRow = document.createElement('div');
  secondRow.className = 'second-row';
  const contextSummaryEl = ContextSummary({ 
    summary: 'Chat mode active - ready to assist with questions and tasks.' 
  });
  const quickActionEl = QuickActionButton({ 
    label: 'Start Chat', 
    onClick: () => console.log('Quick action clicked') 
  });
  secondRow.appendChild(contextSummaryEl);
  secondRow.appendChild(quickActionEl);
  sidebarContainer.appendChild(secondRow);

  // Tasks panel
  const tasksPanel = TasksPanel({
    tasks: tasks,
    status: 'active',
    isCollapsed: false,
    onTaskToggle: (taskId, checked) => {
      const task = tasks.find(t => t.id === taskId);
      if (task) task.checked = checked;
    }
  });
  sidebarContainer.appendChild(tasksPanel);

  // Chat area container
  const chatAreaContainer = document.createElement('div');
  chatAreaContainer.className = 'chat-area';
  chatAreaContainer.id = 'chatArea';
  sidebarContainer.appendChild(chatAreaContainer);

  // Function to render messages
  function renderMessages() {
    chatAreaContainer.innerHTML = '';
    const chatArea = ChatArea({ 
      messages, 
      onFeedbackSubmit: (messageId, rating, feedback) => {
        console.log('Feedback submitted:', { messageId, rating, feedback });
      }
    });
    chatAreaContainer.appendChild(chatArea);
  }

  // Chat input
  const chatInput = ChatInput({
    onSend: async (messageText: string) => {
      // Add user message
      const userMessage: Message = {
        id: `msg_${Date.now()}`,
        content: messageText,
        timestamp: new Date().toISOString(),
        sessionId,
        type: 'user'
      };
      messages.push(userMessage);
      renderMessages();
      
      // Update Mobius logo to processing
      mobiusStatus = 'processing';
      const newMobiusLogo = MobiusLogo({ status: mobiusStatus });
      logoSection.replaceChild(newMobiusLogo, mobiusLogo);
      const currentMobiusLogo = newMobiusLogo;
      
      try {
        // Send to backend
        const response = await sendChatMessage(messageText, sessionId);

        // Client is the source of truth for mode UI defaults. Backend is per-message overrides only.
        const uiDefaults = getUiDefaultsForMode(currentMode);
        const serverMessages = Array.isArray(response.messages) ? response.messages : [];

        if (serverMessages.length > 0) {
          for (const m of serverMessages) {
            const ui = { ...uiDefaults, ...(m.ui_overrides || {}) };

            const systemMsg: Message = {
              id: `msg_${Date.now()}_${m.kind}`,
              content: m.content,
              timestamp: new Date().toISOString(),
              sessionId,
              type: 'system',
              // Backend-driven visibility
              feedbackComponent: ui.feedbackComponent === true,
            };

            // Optional local thinking / guidance scaffolding (only if visible)
            if (ui.thinkingBox) {
              systemMsg.thinkingBox = {
                content: ['Processing message...', 'Generating response...'],
                isCollapsed: false,
              };
            }
            if (ui.guidanceActions) {
              systemMsg.guidanceActions = [
                { label: 'View Details', onClick: () => console.log('View details') },
                { label: 'Follow Up', onClick: () => console.log('Follow up') },
              ];
            }

            messages.push(systemMsg);
          }
        } else {
          // Fallback (older backend)
          messages.push({
            id: `msg_${Date.now()}_replayed`,
            content: response.replayed,
            timestamp: new Date().toISOString(),
            sessionId,
            type: 'system',
            thinkingBox: {
              content: ['Processing message...', 'Generating response...'],
              isCollapsed: false,
            },
            feedbackComponent: false,
          });

          messages.push({
            id: `msg_${Date.now()}_ack`,
            content: response.acknowledgement,
            timestamp: new Date().toISOString(),
            sessionId,
            type: 'system',
            feedbackComponent: false,
          });
        }
        
        renderMessages();
      } catch (error) {
        console.error('Error sending message:', error);
        const errorMessage: Message = {
          id: `msg_${Date.now()}_error`,
          content: `Error: ${error instanceof Error ? error.message : 'Failed to send message'}`,
          timestamp: new Date().toISOString(),
          sessionId,
          type: 'system'
        };
        messages.push(errorMessage);
        renderMessages();
      } finally {
        // Update Mobius logo back to idle
        mobiusStatus = 'idle';
        const idleMobiusLogo = MobiusLogo({ status: mobiusStatus });
        logoSection.replaceChild(idleMobiusLogo, currentMobiusLogo);
      }
    }
  });
  sidebarContainer.appendChild(chatInput);

  // Record ID input
  const recordInput = RecordIDInput({
    recordType,
    value: recordId,
    onChange: (type, value) => {
      recordType = type;
      recordId = value;
      console.log('Record ID changed:', type, value);
    }
  });
  sidebarContainer.appendChild(recordInput);

  // Workflow buttons
  const workflowButtons = WorkflowButtons({
    buttons: [
      { label: 'Generate Report', onClick: () => console.log('Generate report') },
      { label: 'Schedule Follow-up', onClick: () => console.log('Schedule follow-up') }
    ]
  });
  sidebarContainer.appendChild(workflowButtons);

  // Footer
  const footer = document.createElement('div');
  footer.className = 'footer';
  
  const userDetailsEl = UserDetails({ userName: 'Dr. Smith', userRole: 'Provider' });
  const preferencesEl = PreferencesPanel({
    llmChoice,
    agentMode,
    onLLMChange: (llm) => {
      llmChoice = llm;
      console.log('LLM changed:', llm);
    },
    onAgentModeChange: (mode) => {
      agentMode = mode;
      console.log('Agent mode changed:', mode);
    },
    isExpanded: false
  });

  // One-line footer row: User | Role | LLM | Agent (with expandable preferences below)
  const footerRow = document.createElement('div');
  footerRow.className = 'user-details';
  footerRow.appendChild(userDetailsEl);
  footerRow.appendChild(preferencesEl);
  footer.appendChild(footerRow);
  sidebarContainer.appendChild(footer);

  function applyModeUiDefaults(mode: string) {
    const ui = getUiDefaultsForMode(mode);

    setVisible(topRow, ui.header);
    setVisible(contextSummaryEl, ui.contextSummary);
    setVisible(quickActionEl, ui.quickActionButton);
    setVisible(secondRow, ui.contextSummary || ui.quickActionButton);
    setVisible(tasksPanel, ui.tasksPanel);
    setVisible(chatAreaContainer, ui.chatArea);
    setVisible(chatInput, ui.chatInput);
    setVisible(recordInput, ui.recordIdInput);
    setVisible(workflowButtons, ui.workflowButtons);
    setVisible(userDetailsEl, ui.userDetails);
    setVisible(preferencesEl, ui.preferencesPanel);
    setVisible(footer, ui.userDetails || ui.preferencesPanel);
  }

  function setMode(nextMode: string) {
    currentMode = nextMode;
    const nextContext = ContextDisplay({ status: currentStatus, mode: currentMode });
    topRow.replaceChild(nextContext, contextDisplayEl);
    contextDisplayEl = nextContext;

    applyModeUiDefaults(currentMode);
  }

  // Example hook for future mode changes:
  // quickActionEl.addEventListener('click', () => setMode('Chat'));

  // Apply initial mode defaults.
  applyModeUiDefaults(currentMode);

  // Append to body (or html if body doesn't exist yet)
  const target = document.body || document.documentElement;
  if (!target) {
    console.error('[Mobius OS] No body or documentElement found!');
    return;
  }
  
  target.appendChild(sidebarContainer);
  console.log('[Mobius OS] Sidebar appended to DOM');

  // Initial render
  renderMessages();
  
  // Force a reflow to ensure styles are applied
  sidebarContainer.offsetHeight;
  
  console.log('[Mobius OS] Sidebar initialization complete. Position:', {
    top: sidebarContainer.offsetTop,
    right: window.innerWidth - sidebarContainer.offsetLeft - sidebarContainer.offsetWidth,
    width: sidebarContainer.offsetWidth,
    height: sidebarContainer.offsetHeight,
    computedStyle: window.getComputedStyle(sidebarContainer).position
  });
  
  return Promise.resolve();
}

// When injected via chrome.scripting.executeScript, toggle the sidebar immediately.
console.log('[Mobius OS] Content script injected. URL:', window.location.href);

(async () => {
  const existingSidebar = document.getElementById('mobius-os-sidebar');
  if (existingSidebar) {
    existingSidebar.remove();
    const style = document.getElementById('mobius-os-page-adjust');
    if (style) style.remove();
    console.log('[Mobius OS] Sidebar removed (toggle off)');
    return;
  }

  await initSidebar();
  console.log('[Mobius OS] Sidebar created (toggle on)');
})();
