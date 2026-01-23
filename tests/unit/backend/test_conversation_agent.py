"""
Comprehensive unit test for ConversationAgent (Chat Mode)
Tests all functionality of the conversation agent
"""

import sys
import os

# Add backend to path BEFORE any app imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import unittest
from datetime import datetime
from app.agents.base_agent.conversation_agent import ConversationAgent


class TestConversationAgent(unittest.TestCase):
    """
    Comprehensive test suite for ConversationAgent
    Covers all methods and edge cases for chat mode
    """
    
    def setUp(self):
        """Set up test fixtures"""
        self.agent = ConversationAgent()
        self.test_session_id = "session_test_123"
        self.test_message = "Hello, this is a test message"
        self.test_context = {"mode": "chat", "user_id": "user123"}
    
    def test_process_message_success(self):
        """Test successful message processing with all required fields"""
        result = self.agent.process_message(
            self.test_message,
            self.test_session_id,
            self.test_context
        )
        
        # Verify response structure
        self.assertTrue(result["success"])
        self.assertEqual(result["session_id"], self.test_session_id)
        self.assertIn("replayed", result)
        self.assertIn("acknowledgement", result)
        self.assertIn("captured", result)
        self.assertIn("ui_defaults", result)
        self.assertIn("messages", result)
        
        # Verify replayed message
        self.assertEqual(result["replayed"], self.test_message)
        
        # Verify acknowledgement
        self.assertEqual(result["acknowledgement"], "Message received and acknowledged.")
        
        # Verify UI defaults and per-message overrides
        ui_defaults = result["ui_defaults"]
        self.assertIsInstance(ui_defaults, dict)
        self.assertEqual(len(ui_defaults.keys()), 27)
        self.assertIn("feedbackComponent", ui_defaults)
        self.assertTrue(ui_defaults["feedbackComponent"])

        messages = result["messages"]
        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["kind"], "replayed")
        self.assertEqual(messages[0]["content"], result["replayed"])
        self.assertEqual(messages[0]["ui_overrides"]["feedbackComponent"], False)
        self.assertEqual(messages[1]["kind"], "acknowledgement")
        self.assertEqual(messages[1]["content"], result["acknowledgement"])
        self.assertEqual(messages[1]["ui_overrides"]["feedbackComponent"], False)

        # Verify captured data
        captured = result["captured"]
        self.assertEqual(captured["message"], self.test_message)
        self.assertEqual(captured["session_id"], self.test_session_id)
        self.assertEqual(captured["context"], self.test_context)
        self.assertIn("timestamp", captured)

    def test_process_message_per_message_ui_overrides(self):
        """Test that callers can override per-message UI visibility"""
        result = self.agent.process_message(
            self.test_message,
            self.test_session_id,
            self.test_context,
            per_message_ui_overrides={
                "replayed": {"feedbackComponent": True},
            },
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["messages"][0]["kind"], "replayed")
        self.assertEqual(result["messages"][0]["ui_overrides"]["feedbackComponent"], True)
    
    def test_process_message_without_context(self):
        """Test message processing without context (should use empty dict)"""
        result = self.agent.process_message(
            self.test_message,
            self.test_session_id
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["captured"]["context"], {})
    
    def test_process_message_missing_session_id(self):
        """Test that missing session_id raises ValueError"""
        with self.assertRaises(ValueError) as context:
            self.agent.process_message(self.test_message, "")
        
        self.assertIn("session_id is required", str(context.exception))
    
    def test_process_message_empty_session_id(self):
        """Test that empty session_id raises ValueError"""
        with self.assertRaises(ValueError):
            self.agent.process_message(self.test_message, None)
    
    def test_capture_message(self):
        """Test message capture functionality"""
        captured = self.agent._capture_message(
            self.test_message,
            self.test_session_id,
            self.test_context
        )
        
        self.assertEqual(captured["message"], self.test_message)
        self.assertEqual(captured["session_id"], self.test_session_id)
        self.assertEqual(captured["context"], self.test_context)
        self.assertIsInstance(captured["timestamp"], str)
        
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(captured["timestamp"])
    
    def test_replay_message(self):
        """Test message replay functionality"""
        replayed = self.agent._replay_message(self.test_message)
        self.assertEqual(replayed, self.test_message)
    
    def test_replay_message_empty_string(self):
        """Test replay with empty message"""
        replayed = self.agent._replay_message("")
        self.assertEqual(replayed, "")
    
    def test_send_acknowledgement(self):
        """Test acknowledgement message"""
        acknowledgement = self.agent._send_acknowledgement(self.test_message)
        self.assertEqual(acknowledgement, "Message received and acknowledged.")
    
    def test_get_timestamp(self):
        """Test timestamp generation"""
        timestamp = self.agent._get_timestamp()
        self.assertIsInstance(timestamp, str)
        
        # Verify it's a valid ISO format datetime
        parsed = datetime.fromisoformat(timestamp)
        self.assertIsInstance(parsed, datetime)
    
    def test_multiple_messages_same_session(self):
        """Test processing multiple messages with same session_id"""
        message1 = "First message"
        message2 = "Second message"
        
        result1 = self.agent.process_message(message1, self.test_session_id)
        result2 = self.agent.process_message(message2, self.test_session_id)
        
        self.assertEqual(result1["session_id"], self.test_session_id)
        self.assertEqual(result2["session_id"], self.test_session_id)
        self.assertEqual(result1["replayed"], message1)
        self.assertEqual(result2["replayed"], message2)
    
    def test_different_session_ids(self):
        """Test processing messages with different session IDs"""
        session1 = "session_1"
        session2 = "session_2"
        
        result1 = self.agent.process_message(self.test_message, session1)
        result2 = self.agent.process_message(self.test_message, session2)
        
        self.assertEqual(result1["session_id"], session1)
        self.assertEqual(result2["session_id"], session2)
    
    def test_special_characters_in_message(self):
        """Test handling of special characters in messages"""
        special_message = "Hello! @#$%^&*() Test with émojis 🎉"
        result = self.agent.process_message(special_message, self.test_session_id)
        
        self.assertEqual(result["replayed"], special_message)
        self.assertEqual(result["captured"]["message"], special_message)
    
    def test_long_message(self):
        """Test handling of very long messages"""
        long_message = "A" * 10000  # 10KB message
        result = self.agent.process_message(long_message, self.test_session_id)
        
        self.assertEqual(result["replayed"], long_message)
        self.assertEqual(len(result["captured"]["message"]), 10000)
    
    def test_context_preservation(self):
        """Test that context is preserved through processing"""
        custom_context = {
            "mode": "chat",
            "user_id": "user123",
            "patient_id": "MRN553",
            "custom_field": "custom_value"
        }
        
        result = self.agent.process_message(
            self.test_message,
            self.test_session_id,
            custom_context
        )
        
        self.assertEqual(result["captured"]["context"], custom_context)
        self.assertEqual(result["captured"]["context"]["patient_id"], "MRN553")


if __name__ == '__main__':
    unittest.main()
