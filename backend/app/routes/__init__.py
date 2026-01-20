"""
API Routes for Mobius OS.

User Awareness Sprint routes:
- auth.py: Authentication endpoints
"""

from .auth import bp as auth_bp

__all__ = ["auth_bp"]
