"""
Database connections for Mobius OS.

- PostgreSQL: authoritative system of record (via SQLAlchemy)
- Firestore: realtime projection layer (optional, via google-cloud-firestore)
"""

from .postgres import db, init_db, get_db_session
from .firestore import get_firestore_client, firestore_enabled

__all__ = [
    "db",
    "init_db",
    "get_db_session",
    "get_firestore_client",
    "firestore_enabled",
]
