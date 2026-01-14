"""
Test script for ConversationAgent
"""

import sys
sys.path.insert(0, '.')

from app.agents.base_agent.conversation_agent import ConversationAgent


def test_conversation_agent():
    """Test the ConversationAgent class"""
    print("Testing ConversationAgent...")
    
    # Create agent
    agent = ConversationAgent()
    
    # Test with valid session_id
    print("\n1. Testing with valid session_id:")
    result = agent.process_message(
        user_message="Hello, this is a test message",
        session_id="session_abc123xyz"
    )
    print(f"   Result: {result}")
    
    # Verify structure
    assert result["success"] == True
    assert result["session_id"] == "session_abc123xyz"
    assert "replayed" in result
    assert "acknowledgement" in result
    assert "captured" in result
    assert result["captured"]["session_id"] == "session_abc123xyz"
    print("   ✓ All assertions passed!")
    
    # Test without session_id (should raise ValueError)
    print("\n2. Testing without session_id (should raise ValueError):")
    try:
        agent.process_message(
            user_message="Test message",
            session_id=""
        )
        print("   ✗ ERROR: Should have raised ValueError")
    except ValueError as e:
        print(f"   ✓ Correctly raised ValueError: {e}")
    
    # Test with context
    print("\n3. Testing with context:")
    result = agent.process_message(
        user_message="Test with context",
        session_id="session_test123",
        context={"mode": "chat", "user_id": "user123"}
    )
    assert result["captured"]["context"]["mode"] == "chat"
    assert result["captured"]["context"]["user_id"] == "user123"
    print(f"   Result: {result}")
    print("   ✓ Context handling works!")
    
    print("\n✅ All tests passed!")


if __name__ == '__main__':
    test_conversation_agent()
