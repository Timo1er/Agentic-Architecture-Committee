import os
from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Architecture Review Board"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Security & JWT
    SECRET_KEY: str = "super-secret-arb-key-change-in-production-min-32-chars-key!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ENCRYPTION_KEY: str = "ARB_DEFAULT_KEY_32BYTES_LONG_00000000000="

    # Default Admin
    ADMIN_EMAIL: str = "admin@arb.local"
    ADMIN_PASSWORD: str = "AdminPassword123!"

    # Relational Database
    DATABASE_URL: str = "sqlite:///./arb_database.db"

    # Vector Store
    VECTOR_DB_TYPE: str = "qdrant" # "qdrant" or "pgvector"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "arb_historical_feedback"

    # Default LLM Provider
    DEFAULT_LLM_PROVIDER: str = "google" # google, anthropic, openai, mistral, aws
    DEFAULT_MODEL_NAME: str = "gemini-1.5-pro"

    # Provider Keys
    GOOGLE_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_BEDROCK_MODEL_ID: str = "anthropic.claude-3-sonnet-20240229-v1:0"

    # SSO / Okta
    SSO_ENABLED: bool = False
    SSO_PROVIDER: str = "okta"
    OKTA_CLIENT_ID: Optional[str] = None
    OKTA_CLIENT_SECRET: Optional[str] = None
    OKTA_DOMAIN: Optional[str] = None
    OKTA_REDIRECT_URI: str = "http://localhost:8000/api/auth/sso/callback"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
