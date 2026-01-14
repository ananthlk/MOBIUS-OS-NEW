/**
 * Popup entry point for Mobius OS extension
 * Full UI implementation with all 27 components
 */

import './styles/popup.css';
// When the user clicks the extension icon, the popup opens.
// We use that click to inject/toggle the right-side sidebar on the active tab.
async function toggleSidebarOnActiveTab(): Promise<{ ok: true } | { ok: false; reason: string }> {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id || !tab.url) return { ok: false, reason: 'No active tab found.' };

    // Chrome blocks injection on internal pages.
    const blockedSchemes = ['chrome://', 'chrome-extension://', 'edge://', 'about:'];
    if (blockedSchemes.some((s) => tab.url!.startsWith(s))) {
      return { ok: false, reason: `Cannot run on this page: ${tab.url}` };
    }

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js'],
    });

    return { ok: true };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, reason: msg };
  }
}

import { getOrCreateSessionId } from './utils/session';
import { sendChatMessage } from './services/api';
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
  ChatTools,
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

// Initialize app
async function init() {
  // If we can toggle the sidebar, do it immediately and close the popup.
  // If we can't (e.g., chrome:// pages), fall back to rendering the popup UI.
  const autoToggle = await toggleSidebarOnActiveTab();
  if (autoToggle.ok) {
    window.close();
    return;
  }

  const app = document.getElementById('app');
  if (!app) return;

  // If sidebar toggle failed, show a small notice at the top of the popup.
  const notice = document.createElement('div');
  notice.style.cssText =
    'padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: 12px; color: #b3261e; background: #fff;';
  notice.textContent = `Sidebar not available: ${autoToggle.reason}`;
  app.appendChild(notice);

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
  topRow.appendChild(ContextDisplay({ status: currentStatus, mode: currentMode }));
  topRow.appendChild(AlertButton({ 
    hasAlerts: false, 
    onClick: () => alert('Live Alerts:\n- No active alerts') 
  }));
  topRow.appendChild(SettingsButton({ onClick: () => alert('Settings') }));
  
  app.appendChild(topRow);

  // Second row - context summary
  const secondRow = document.createElement('div');
  secondRow.className = 'second-row';
  secondRow.appendChild(ContextSummary({ 
    summary: 'Chat mode active - ready to assist with questions and tasks.' 
  }));
  secondRow.appendChild(QuickActionButton({ 
    label: 'Start Chat', 
    onClick: () => console.log('Quick action clicked') 
  }));
  app.appendChild(secondRow);

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
  app.appendChild(tasksPanel);

  // Chat area container
  const chatAreaContainer = document.createElement('div');
  chatAreaContainer.className = 'chat-area';
  chatAreaContainer.id = 'chatArea';
  app.appendChild(chatAreaContainer);

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

        const uiDefaults = response.ui_defaults || ({} as any);
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
  app.appendChild(chatInput);

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
  app.appendChild(recordInput);

  // Workflow buttons
  const workflowButtons = WorkflowButtons({
    buttons: [
      { label: 'Generate Report', onClick: () => console.log('Generate report') },
      { label: 'Schedule Follow-up', onClick: () => console.log('Schedule follow-up') }
    ]
  });
  app.appendChild(workflowButtons);

  // Footer
  const footer = document.createElement('div');
  footer.className = 'footer';
  
  const userDetails = UserDetails({ userName: 'Dr. Smith', userRole: 'Provider' });
  const preferences = PreferencesPanel({
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
  
  footer.appendChild(userDetails);
  footer.appendChild(preferences);
  app.appendChild(footer);

  // Initial render
  renderMessages();
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
