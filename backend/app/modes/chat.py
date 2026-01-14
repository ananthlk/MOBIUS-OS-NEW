"""
Chat mode endpoint for conversation agent
"""

from flask import Blueprint, request, jsonify
from app.agents.base_agent.conversation_agent import ConversationAgent

bp = Blueprint('chat', __name__, url_prefix='/api/v1/modes/chat')


@bp.route('/message', methods=['POST'])
def chat_message():
    """Chat mode endpoint for conversation agent"""
    data = request.json
    user_message = data.get('message', '')
    session_id = data.get('session_id', '')
    
    # Validate session_id
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    # Create conversation agent
    agent = ConversationAgent()
    
    # Process message (with session_id)
    result = agent.process_message(user_message, session_id)
    
    return jsonify(result)
