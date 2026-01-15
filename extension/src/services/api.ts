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

type MiniStatusColor = 'green' | 'yellow' | 'grey' | 'blue';

export type MiniStatusResponse = {
  ok: true;
  session_id: SessionId;
  proceed: { color: MiniStatusColor; text: string };
  tasking: { color: MiniStatusColor; text: string };
};

export async function fetchMiniStatus(sessionId: SessionId): Promise<MiniStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/mini/status`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      session_id: sessionId
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to fetch mini status');
  }

  return response.json();
}

export async function submitMiniNote(
  sessionId: SessionId,
  note: string,
  patient?: { name?: string; id?: string }
): Promise<{ ok: true; session_id: SessionId; note: string }> {
  const response = await fetch(`${API_BASE_URL}/mini/note`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      session_id: sessionId,
      note,
      patient: patient || {}
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to submit note');
  }

  return response.json();
}

export type MiniPatientSearchResult = { name: string; id: string };

export async function searchMiniPatients(
  query: string,
  limit = 8
): Promise<{ ok: true; q: string; results: MiniPatientSearchResult[] }> {
  const q = (query || '').trim();
  const url = new URL(`${API_BASE_URL}/mini/patient/search`);
  url.searchParams.set('q', q);
  url.searchParams.set('limit', String(limit));

  const response = await fetch(url.toString(), { method: 'GET' });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to search patients');
  }
  return response.json();
}
