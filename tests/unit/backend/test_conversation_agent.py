"""
Comprehensive unit test for ConversationAgent (Chat Mode)
Tests all functionality of the conversation agent
"""

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
        
        # Verify replayed message
        self.assertEqual(result["replayed"], f"You said: {self.test_message}")
        
        # Verify acknowledgement
        self.assertEqual(result["acknowledgement"], "Message received and acknowledged.")
        
        # Verify captured data
        captured = result["captured"]
        self.assertEqual(captured["message"], self.test_message)
        self.assertEqual(captured["session_id"], self.test_session_id)
        self.assertEqual(captured["context"], self.test_context)
        self.assertIn("timestamp", captured)
    
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
        self.assertEqual(replayed, f"You said: {self.test_message}")
    
    def test_replay_message_empty_string(self):
        """Test replay with empty message"""
        replayed = self.agent._replay_message("")
        self.assertEqual(replayed, "You said: ")
    
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
        self.assertEqual(result1["replayed"], f"You said: {message1}")
        self.assertEqual(result2["replayed"], f"You said: {message2}")
    
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
        
        self.assertEqual(result["replayed"], f"You said: {special_message}")
        self.assertEqual(result["captured"]["message"], special_message)
    
    def test_long_message(self):
        """Test handling of very long messages"""
        long_message = "A" * 10000  # 10KB message
        result = self.agent.process_message(long_message, self.test_session_id)
        
        self.assertEqual(result["replayed"], f"You said: {long_message}")
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
