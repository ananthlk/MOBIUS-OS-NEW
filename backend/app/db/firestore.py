"""
Firestore client wrapper.

Supports multiple databases based on DATABASE_MODE:
- local: uses 'mobius-dev' database
- cloud: uses '(default)' database

Includes connection testing and graceful degradation when Firestore is unavailable.
"""

import os
from pathlib import Path

from app.config import config

# Firestore client (initialized lazily)
_firestore_client = None
_firestore_available = None  # None = not tested, True/False = tested


def firestore_enabled() -> bool:
    """Check if Firestore is enabled in config."""
    return config.ENABLE_FIRESTORE


def firestore_available() -> bool:
    """
    Check if Firestore is both enabled AND reachable.
    
    Returns False if disabled or connection failed.
    """
    global _firestore_available
    
    if not firestore_enabled():
        return False
    
    if _firestore_available is not None:
        return _firestore_available
    
    # Test connection
    client = get_firestore_client()
    return _firestore_available if _firestore_available is not None else False


def test_firestore_connection(client, timeout: float = 3.0) -> bool:
    """
    Test Firestore connection with a quick read operation.
    
    Returns True if connection succeeds within timeout.
    """
    global _firestore_available
    
    try:
        import threading
        
        result = {"success": False}
        
        def _test():
            try:
                # Try a simple collection list operation
                list(client.collections())
                result["success"] = True
            except Exception:
                result["success"] = False
        
        thread = threading.Thread(target=_test, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            print(f"[Firestore] Connection test timed out ({timeout}s)")
            _firestore_available = False
            return False
        
        _firestore_available = result["success"]
        if result["success"]:
            print("[Firestore] Connection test passed")
        else:
            print("[Firestore] Connection test failed")
        
        return result["success"]
        
    except Exception as e:
        print(f"[Firestore] Connection test error: {e}")
        _firestore_available = False
        return False


def get_firestore_client():
    """
    Get or create Firestore client.
    
    Uses the database specified by DATABASE_MODE:
    - local mode → mobius-dev database
    - cloud mode → (default) database
    
    Returns None if Firestore is disabled or unavailable.
    """
    global _firestore_client, _firestore_available

    if not firestore_enabled():
        return None
    
    # If we've tested and it's unavailable, don't retry
    if _firestore_available is False:
        return None

    if _firestore_client is not None:
        return _firestore_client

    # Resolve credentials path
    creds_path = config.GCP_CREDENTIALS_PATH
    if not os.path.isabs(creds_path):
        backend_dir = Path(__file__).parent.parent.parent
        creds_path = backend_dir / creds_path

    if not os.path.exists(creds_path):
        print(f"[Firestore] Credentials not found: {creds_path}")
        _firestore_available = False
        return None

    # Set credentials environment variable
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)

    try:
        from google.cloud import firestore

        # Get the database ID based on mode
        database_id = config.get_firestore_database()
        
        print(f"[Config] Firestore: {config.DATABASE_MODE.upper()} ({database_id})")
        
        # Create client with specific database
        _firestore_client = firestore.Client(
            project=config.GCP_PROJECT_ID,
            database=database_id
        )
        print(f"[Firestore] Connected to project: {config.GCP_PROJECT_ID}, database: {database_id}")
        
        # Test the connection (non-blocking, with timeout)
        test_firestore_connection(_firestore_client, timeout=3.0)
        
        return _firestore_client

    except Exception as e:
        print(f"[Firestore] Connection error: {e}")
        _firestore_available = False
        return None


def reset_firestore_state():
    """Reset Firestore state for testing or retry."""
    global _firestore_client, _firestore_available
    _firestore_client = None
    _firestore_available = None
