/**
 * Comprehensive unit test for Chat Mode API Service
 * Tests all functionality of the API service from frontend perspective
 */

import { sendChatMessage } from '../../../extension/src/services/api';
import { getOrCreateSessionId, generateSessionId } from '../../../extension/src/utils/session';

// Mock chrome.storage
const mockStorage: { [key: string]: any } = {};
global.chrome = {
  storage: {
    local: {
      get: (keys: string[], callback: (result: { [key: string]: any }) => void) => {
        const result: { [key: string]: any } = {};
        keys.forEach(key => {
          result[key] = mockStorage[key] || null;
        });
        callback(result);
      },
      set: (items: { [key: string]: any }, callback?: () => void) => {
        Object.assign(mockStorage, items);
        if (callback) callback();
      }
    }
  }
} as any;

// Mock fetch
global.fetch = jest.fn();

describe('Chat Mode API Service - Unit Tests', () => {
  let testSessionId: string;
  const testMessage = 'Hello, this is a test message';
  const apiBaseUrl = 'http://localhost:5001/api/v1';

  beforeEach(() => {
    testSessionId = generateSessionId();
    jest.clearAllMocks();
    Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
  });

  describe('Session Management', () => {
    test('should generate unique session IDs', async () => {
      const id1 = await getOrCreateSessionId();
      const id2 = await getOrCreateSessionId();
      
      // First call should create and store
      expect(id1).toBeDefined();
      expect(id1).toMatch(/^session_/);
      
      // Second call should return same ID
      expect(id2).toBe(id1);
    });

    test('should create new session ID if none exists', async () => {
      mockStorage.current_session_id = undefined;
      const sessionId = await getOrCreateSessionId();
      
      expect(sessionId).toBeDefined();
      expect(mockStorage.current_session_id).toBe(sessionId);
    });
  });

  describe('Message Sending', () => {
    test('should send message successfully', async () => {
      const mockResponse = {
        success: true,
        session_id: testSessionId,
        replayed: `${testMessage}`,
        acknowledgement: 'Message received and acknowledged.',
        captured: {
          message: testMessage,
          session_id: testSessionId,
          timestamp: new Date().toISOString(),
          context: {}
        },
        messages: [
          { kind: 'replayed', content: `${testMessage}`, ui_overrides: { feedbackComponent: false } },
          { kind: 'acknowledgement', content: 'Message received and acknowledged.', ui_overrides: { feedbackComponent: false } }
        ]
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const response = await sendChatMessage(testMessage, testSessionId);

      expect(global.fetch).toHaveBeenCalledWith(
        `${apiBaseUrl}/modes/chat/message`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            message: testMessage,
            session_id: testSessionId
          })
        }
      );

      expect(response).toEqual(mockResponse);
      expect(response.success).toBe(true);
      expect(response.session_id).toBe(testSessionId);
    });

    test('should handle API errors', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ error: 'session_id is required' })
      });

      await expect(
        sendChatMessage(testMessage, testSessionId)
      ).rejects.toThrow('session_id is required');
    });

    test('should handle network errors', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Network error')
      );

      await expect(
        sendChatMessage(testMessage, testSessionId)
      ).rejects.toThrow('Network error');
    });
  });

  describe('Request Format', () => {
    test('should format request correctly', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      });

      await sendChatMessage(testMessage, testSessionId);

      const callArgs = (global.fetch as jest.Mock).mock.calls[0];
      expect(callArgs[0]).toBe(`${apiBaseUrl}/modes/chat/message`);
      expect(callArgs[1].method).toBe('POST');
      expect(callArgs[1].headers['Content-Type']).toBe('application/json');
      
      const body = JSON.parse(callArgs[1].body);
      expect(body.message).toBe(testMessage);
      expect(body.session_id).toBe(testSessionId);
    });
  });

  describe('Response Handling', () => {
    test('should parse successful response', async () => {
      const mockResponse = {
        success: true,
        session_id: testSessionId,
        replayed: `${testMessage}`,
        acknowledgement: 'Message received and acknowledged.',
        captured: {
          message: testMessage,
          session_id: testSessionId,
          timestamp: new Date().toISOString(),
          context: {}
        },
        messages: [
          { kind: 'replayed', content: `${testMessage}`, ui_overrides: { feedbackComponent: false } },
          { kind: 'acknowledgement', content: 'Message received and acknowledged.', ui_overrides: { feedbackComponent: false } }
        ]
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const response = await sendChatMessage(testMessage, testSessionId);

      expect(response.replayed).toContain(testMessage);
      expect(response.acknowledgement).toBeDefined();
      expect(response.captured).toBeDefined();
      expect(response.messages).toBeDefined();
    });

    test('should handle error responses', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'session_id is required' })
      });

      await expect(
        sendChatMessage(testMessage, '')
      ).rejects.toThrow();
    });
  });
});
