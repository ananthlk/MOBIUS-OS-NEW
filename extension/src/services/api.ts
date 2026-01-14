/**
 * API service for backend communication
 */

import { SessionId, ChatResponse } from '../types';

const API_BASE_URL = 'http://localhost:5001/api/v1';

/**
 * Send a chat message to the backend
 */
export async function sendChatMessage(
  message: string,
  sessionId: SessionId
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/modes/chat/message`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      message,
      session_id: sessionId
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to send message');
  }

  return response.json();
}
