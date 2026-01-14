"""
Integration tests for Chat Mode endpoint
Tests the full request/response cycle for /api/v1/modes/chat/message
"""

import unittest
import json
from app import create_app


class TestChatModeEndpoint(unittest.TestCase):
    """
    Integration tests for chat mode endpoint
    Tests HTTP requests, responses, and error handling
    """
    
    def setUp(self):
        """Set up test client"""
        self.app = create_app()
        self.client = self.app.test_client()
        self.app.config['TESTING'] = True
        self.base_url = '/api/v1/modes/chat/message'
        self.test_session_id = "session_integration_test_123"
    
    def test_post_message_success(self):
        """Test successful POST request with valid data"""
        data = {
            "message": "Hello, this is an integration test",
            "session_id": self.test_session_id
        }
        
        response = self.client.post(
            self.base_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        result = json.loads(response.data)
        self.assertTrue(result["success"])
        self.assertEqual(result["session_id"], self.test_session_id)
        self.assertIn("replayed", result)
        self.assertIn("acknowledgement", result)
        self.assertIn("captured", result)
    
    def test_post_message_missing_session_id(self):
        """Test POST request without session_id (should return 400)"""
        data = {
            "message": "Test message"
        }
        
        response = self.client.post(
            self.base_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.data)
        self.assertIn("error", result)
        self.assertIn("session_id is required", result["error"])
    
    def test_post_message_empty_session_id(self):
        """Test POST request with empty session_id (should return 400)"""
        data = {
            "message": "Test message",
            "session_id": ""
        }
        
        response = self.client.post(
            self.base_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        result = json.loads(response.data)
        self.assertIn("error", result)
    
    def test_post_message_missing_message(self):
        """Test POST request without message field"""
        data = {
            "session_id": self.test_session_id
        }
        
        response = self.client.post(
            self.base_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # Should still succeed (empty message is valid)
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result["success"])
    
    def test_post_message_empty_message(self):
        """Test POST request with empty message"""
        data = {
            "message": "",
            "session_id": self.test_session_id
        }
        
        response = self.client.post(
            self.base_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result["replayed"], "You said: ")
    
    def test_post_message_with_context(self):
        """Test POST request with additional context data"""
        data = {
            "message": "Test with context",
            "session_id": self.test_session_id,
            "context": {
                "mode": "chat",
                "user_id": "user123"
            }
        }
        
        response = self.client.post(
            self.base_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result["success"])
    
    def test_cors_headers(self):
        """Test that CORS headers are present"""
        data = {
            "message": "Test CORS",
            "session_id": self.test_session_id
        }
        
        response = self.client.post(
            self.base_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertIn('Access-Control-Allow-Origin', response.headers)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')
    
    def test_multiple_requests_same_session(self):
        """Test multiple requests with same session_id"""
        data1 = {
            "message": "First message",
            "session_id": self.test_session_id
        }
        data2 = {
            "message": "Second message",
            "session_id": self.test_session_id
        }
        
        response1 = self.client.post(
            self.base_url,
            data=json.dumps(data1),
            content_type='application/json'
        )
        response2 = self.client.post(
            self.base_url,
            data=json.dumps(data2),
            content_type='application/json'
        )
        
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        
        result1 = json.loads(response1.data)
        result2 = json.loads(response2.data)
        
        self.assertEqual(result1["session_id"], self.test_session_id)
        self.assertEqual(result2["session_id"], self.test_session_id)
        self.assertNotEqual(result1["replayed"], result2["replayed"])
    
    def test_invalid_json(self):
        """Test request with invalid JSON"""
        response = self.client.post(
            self.base_url,
            data="invalid json",
            content_type='application/json'
        )
        
        # Flask should return 400 for invalid JSON
        self.assertIn(response.status_code, [400, 500])
    
    def test_wrong_content_type(self):
        """Test request with wrong content type"""
        data = {
            "message": "Test",
            "session_id": self.test_session_id
        }
        
        response = self.client.post(
            self.base_url,
            data=json.dumps(data),
            content_type='text/plain'
        )
        
        # Should still work or return appropriate error
        self.assertIn(response.status_code, [200, 400, 415])
    
    def test_get_method_not_allowed(self):
        """Test that GET method is not allowed"""
        response = self.client.get(self.base_url)
        self.assertEqual(response.status_code, 405)  # Method Not Allowed


if __name__ == '__main__':
    unittest.main()
