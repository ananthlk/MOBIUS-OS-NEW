/**
 * Integration tests for Chat Mode
 * Tests the full flow from frontend to backend
 */

import { sendChatMessage } from '../../../extension/src/services/api';
import { getOrCreateSessionId } from '../../../extension/src/utils/session';

// Mock chrome.storage for integration tests
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

describe('Chat Mode Integration Tests', () => {
  const apiBaseUrl = 'http://localhost:5001/api/v1';

  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(mockStorage).forEach(key => delete mockStorage[key]);
  });

  describe('End-to-End Message Flow', () => {
    test('should complete full message flow: session creation -> send message -> receive response', async () => {
      // Step 1: Create/get session ID
      const sessionId = await getOrCreateSessionId();
      expect(sessionId).toBeDefined();
      expect(sessionId).toMatch(/^session_/);

      // Step 2: Mock successful API response
      const testMessage = 'Hello from integration test';
      const uiDefaults = {
        clientLogo: true,
        mobiusLogo: true,
        statusIndicator: true,
        modeBadge: true,
        alertButton: true,
        settingsButton: true,
        contextDisplay: true,
        contextSummary: true,
        quickActionButton: true,
        tasksPanel: true,
        taskItem: true,
        thinkingBox: true,
        systemMessage: true,
        userMessage: true,
        feedbackComponent: true,
        guidanceActions: true,
        chatInput: true,
        chatTools: true,
        recordIdInput: true,
        workflowButtons: true,
        userDetails: true,
        preferencesPanel: true,
        chatMessage: true,
        header: true,
        chatArea: true,
        collapsiblePanel: true,
        dropdownMenu: true
      };
      const mockResponse = {
        success: true,
        session_id: sessionId,
        replayed: `You said: ${testMessage}`,
        acknowledgement: 'Message received and acknowledged.',
        captured: {
          message: testMessage,
          session_id: sessionId,
          timestamp: new Date().toISOString(),
          context: {}
        },
        ui_defaults: uiDefaults,
        messages: [
          { kind: 'replayed', content: `You said: ${testMessage}`, ui_overrides: { feedbackComponent: false } },
          { kind: 'acknowledgement', content: 'Message received and acknowledged.', ui_overrides: { feedbackComponent: false } }
        ]
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      // Step 3: Send message
      const response = await sendChatMessage(testMessage, sessionId);

      // Step 4: Verify response
      expect(response.success).toBe(true);
      expect(response.session_id).toBe(sessionId);
      expect(response.replayed).toContain(testMessage);
      expect(response.acknowledgement).toBeDefined();
      expect(response.messages).toBeDefined();
    });

    test('should handle multiple messages in same session', async () => {
      const sessionId = await getOrCreateSessionId();

      const messages = ['First message', 'Second message', 'Third message'];
      const responses = [];

      for (const message of messages) {
        const uiDefaults = {
          clientLogo: true,
          mobiusLogo: true,
          statusIndicator: true,
          modeBadge: true,
          alertButton: true,
          settingsButton: true,
          contextDisplay: true,
          contextSummary: true,
          quickActionButton: true,
          tasksPanel: true,
          taskItem: true,
          thinkingBox: true,
          systemMessage: true,
          userMessage: true,
          feedbackComponent: true,
          guidanceActions: true,
          chatInput: true,
          chatTools: true,
          recordIdInput: true,
          workflowButtons: true,
          userDetails: true,
          preferencesPanel: true,
          chatMessage: true,
          header: true,
          chatArea: true,
          collapsiblePanel: true,
          dropdownMenu: true
        };
        const mockResponse = {
          success: true,
          session_id: sessionId,
          replayed: `You said: ${message}`,
          acknowledgement: 'Message received and acknowledged.',
          captured: {
            message,
            session_id: sessionId,
            timestamp: new Date().toISOString(),
            context: {}
          },
          ui_defaults: uiDefaults,
          messages: [
            { kind: 'replayed', content: `You said: ${message}`, ui_overrides: { feedbackComponent: false } },
            { kind: 'acknowledgement', content: 'Message received and acknowledged.', ui_overrides: { feedbackComponent: false } }
          ]
        };

        (global.fetch as jest.Mock).mockResolvedValueOnce({
          ok: true,
          json: async () => mockResponse
        });

        const response = await sendChatMessage(message, sessionId);
        responses.push(response);
      }

      expect(responses).toHaveLength(3);
      responses.forEach((response, index) => {
        expect(response.session_id).toBe(sessionId);
        expect(response.replayed).toContain(messages[index]);
      });
    });
  });

  describe('Error Handling', () => {
    test('should handle missing session_id error', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'session_id is required' })
      });

      await expect(
        sendChatMessage('Test message', '')
      ).rejects.toThrow('session_id is required');
    });

    test('should handle network timeout', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Network request failed')
      );

      const sessionId = await getOrCreateSessionId();
      await expect(
        sendChatMessage('Test message', sessionId)
      ).rejects.toThrow('Network request failed');
    });

    test('should handle server error (500)', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Internal server error' })
      });

      const sessionId = await getOrCreateSessionId();
      await expect(
        sendChatMessage('Test message', sessionId)
      ).rejects.toThrow();
    });
  });

  describe('Session Persistence', () => {
    test('should persist session ID across page reloads', async () => {
      // First "page load"
      const sessionId1 = await getOrCreateSessionId();
      expect(mockStorage.current_session_id).toBe(sessionId1);

      // Simulate page reload - storage persists
      const sessionId2 = await getOrCreateSessionId();
      expect(sessionId2).toBe(sessionId1);
      expect(mockStorage.current_session_id).toBe(sessionId1);
    });
  });

  describe('Request Format Validation', () => {
    test('should send correctly formatted JSON request', async () => {
      const sessionId = await getOrCreateSessionId();
      const testMessage = 'Test message';

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      });

      await sendChatMessage(testMessage, sessionId);

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const requestBody = JSON.parse(fetchCall[1].body);

      expect(requestBody).toHaveProperty('message');
      expect(requestBody).toHaveProperty('session_id');
      expect(requestBody.message).toBe(testMessage);
      expect(requestBody.session_id).toBe(sessionId);
      expect(typeof requestBody.message).toBe('string');
      expect(typeof requestBody.session_id).toBe('string');
    });
  });
});
