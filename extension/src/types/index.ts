/**
 * Type definitions for Mobius OS
 */

export type SessionId = string;
export type MessageId = string;
export type UserId = string;

export type Status = 'idle' | 'processing';
export type StatusIndicatorStatus = 'proceed' | 'pending' | 'error';
export type TaskType = 'normal' | 'shared' | 'backend';
export type LLMChoice = 'Gemini' | 'GPT-4' | 'Claude';
export type AgentMode = 'Agentic' | 'Co-pilot' | 'Manual';

export interface Message {
  id: MessageId;
  content: string;
  timestamp: string;
  sessionId: SessionId;
  type: 'user' | 'system';
  thinkingBox?: ThinkingBoxContent;
  feedbackComponent?: boolean;
  guidanceActions?: GuidanceAction[];
}

export interface SystemMessage extends Message {
  type: 'system';
  thinkingBox?: ThinkingBoxContent;
  feedbackComponent?: boolean;
  guidanceActions?: GuidanceAction[];
}

export interface UserMessage extends Message {
  type: 'user';
}

export interface ThinkingBoxContent {
  content: string[];
  isCollapsed: boolean;
}

export interface GuidanceAction {
  label: string;
  onClick: () => void;
  actionType?: string;
}

export interface Task {
  id: string;
  label: string;
  checked: boolean;
  disabled: boolean;
  type: TaskType;
}

export interface Context {
  context: string;
  status: StatusIndicatorStatus;
  mode: string;
}

export interface ChatResponse {
  success: boolean;
  session_id: SessionId;
  replayed: string;
  acknowledgement: string;
  captured: {
    message: string;
    session_id: SessionId;
    timestamp: string;
    context: Record<string, any>;
  };
}
