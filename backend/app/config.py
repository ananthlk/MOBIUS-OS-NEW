"""
Application configuration loaded from environment variables.

Supports switching between local and cloud environments for both
PostgreSQL and Firestore via DATABASE_MODE.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from backend directory
backend_dir = Path(__file__).parent.parent
load_dotenv(backend_dir / ".env")


class Config:
    """Application configuration."""

    # Flask settings
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    # Environment mode: "local" or "cloud"
    # Controls both PostgreSQL and Firestore database selection
    DATABASE_MODE = os.getenv("DATABASE_MODE", "local")

    # PostgreSQL - Local
    POSTGRES_HOST_LOCAL = os.getenv("POSTGRES_HOST_LOCAL", "localhost")
    POSTGRES_PORT_LOCAL = os.getenv("POSTGRES_PORT_LOCAL", "5432")
    POSTGRES_DB_LOCAL = os.getenv("POSTGRES_DB_LOCAL", "mobius")
    POSTGRES_USER_LOCAL = os.getenv("POSTGRES_USER_LOCAL", "postgres")
    POSTGRES_PASSWORD_LOCAL = os.getenv("POSTGRES_PASSWORD_LOCAL", "")

    # PostgreSQL - Cloud (GCP Cloud SQL)
    POSTGRES_HOST_CLOUD = os.getenv("POSTGRES_HOST_CLOUD", "")
    POSTGRES_PORT_CLOUD = os.getenv("POSTGRES_PORT_CLOUD", "5432")
    POSTGRES_DB_CLOUD = os.getenv("POSTGRES_DB_CLOUD", "mobius")
    POSTGRES_USER_CLOUD = os.getenv("POSTGRES_USER_CLOUD", "postgres")
    POSTGRES_PASSWORD_CLOUD = os.getenv("POSTGRES_PASSWORD_CLOUD", "")

    # Firestore / GCP
    GCP_CREDENTIALS_PATH = os.getenv("GCP_CREDENTIALS_PATH", "./gcp-credentials.json")
    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
    FIRESTORE_DATABASE_LOCAL = os.getenv("FIRESTORE_DATABASE_LOCAL", "mobius-dev")
    FIRESTORE_DATABASE_CLOUD = os.getenv("FIRESTORE_DATABASE_CLOUD", "(default)")
    ENABLE_FIRESTORE = os.getenv("ENABLE_FIRESTORE", "false").lower() == "true"

    @classmethod
    def get_database_url(cls) -> str:
        """Build PostgreSQL connection URL based on DATABASE_MODE."""
        if cls.DATABASE_MODE == "cloud":
            host = cls.POSTGRES_HOST_CLOUD
            port = cls.POSTGRES_PORT_CLOUD
            db = cls.POSTGRES_DB_CLOUD
            user = cls.POSTGRES_USER_CLOUD
            password = cls.POSTGRES_PASSWORD_CLOUD
            mode_label = "CLOUD"
        else:
            host = cls.POSTGRES_HOST_LOCAL
            port = cls.POSTGRES_PORT_LOCAL
            db = cls.POSTGRES_DB_LOCAL
            user = cls.POSTGRES_USER_LOCAL
            password = cls.POSTGRES_PASSWORD_LOCAL
            mode_label = "LOCAL"

        if password:
            url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        else:
            url = f"postgresql://{user}@{host}:{port}/{db}"

        print(f"[Config] PostgreSQL: {mode_label} ({host})")
        return url

    @classmethod
    def get_firestore_database(cls) -> str:
        """Get Firestore database ID based on DATABASE_MODE."""
        if cls.DATABASE_MODE == "cloud":
            db = cls.FIRESTORE_DATABASE_CLOUD
            mode_label = "CLOUD"
        else:
            db = cls.FIRESTORE_DATABASE_LOCAL
            mode_label = "LOCAL"

        print(f"[Config] Firestore: {mode_label} ({db})")
        return db


# Singleton instance
config = Config()
