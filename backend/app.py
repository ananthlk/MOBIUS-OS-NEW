"""
Flask application entry point for Mobius OS backend.

Registers Mini and Sidecar surface routes (separate paths, shared state).
"""

from flask import Flask

from app.config import config
from app.modes.chat import bp as chat_bp
from app.modes.mini import bp as mini_bp
from app.modes.sidecar import bp as sidecar_bp
from app.modes.mock_emr import bp as mock_emr_bp


def create_app(init_database: bool = False):
    """Create and configure Flask app."""
    app = Flask(__name__)

    # Load config
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["DEBUG"] = config.DEBUG

    # Enable CORS for browser extension
    @app.after_request
    def after_request(response):
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
        return response

    # Register blueprints (surface-specific routes)
    app.register_blueprint(chat_bp)      # /api/v1/modes/chat/*
    app.register_blueprint(mini_bp)      # /api/v1/mini/*
    app.register_blueprint(sidecar_bp)   # /api/v1/sidecar/*
    app.register_blueprint(mock_emr_bp)  # /mock-emr/*

    # Health check endpoint
    @app.route("/health")
    def health():
        return {"status": "ok", "firestore_enabled": config.ENABLE_FIRESTORE}

    # Initialize database tables if requested (development only)
    if init_database:
        with app.app_context():
            from app.db.postgres import init_db
            init_db()
            print("[Mobius] Database tables initialized")

    return app


if __name__ == "__main__":
    app = create_app(init_database=False)
    print(f"[Mobius] Starting server on port 5001...")
    print(f"[Mobius] Firestore enabled: {config.ENABLE_FIRESTORE}")
    print(f"[Mobius] Debug mode: {config.DEBUG}")
    print(f"[Mobius] Routes:")
    print(f"  - /api/v1/mini/* (Mini surface)")
    print(f"  - /api/v1/sidecar/* (Sidecar surface)")
    print(f"  - /api/v1/modes/chat/* (Chat mode)")
    print(f"  - /mock-emr (Mock EMR page)")
    print(f"  - /health (Health check)")
    app.run(debug=config.DEBUG, port=5001)
