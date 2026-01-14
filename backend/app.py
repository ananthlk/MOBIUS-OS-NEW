"""
Flask application entry point for testing
"""

from flask import Flask
from app.modes.chat import bp as chat_bp


def create_app():
    """Create and configure Flask app"""
    app = Flask(__name__)
    
    # Enable CORS for browser extension
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    # Register blueprints
    app.register_blueprint(chat_bp)
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5001)
