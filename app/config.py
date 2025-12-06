"""
Configuration management for the application.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "Quiz Game API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/quizgame"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # JWT Authentication
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password Hashing
    PASSWORD_HASH_ALGORITHM: str = "bcrypt"  # or "argon2"
    BCRYPT_ROUNDS: int = 12
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Question Settings
    DEFAULT_QUESTIONS_PER_COMPETITION: int = 11
    MIN_QUESTION_TIME_LIMIT: int = 15
    MAX_QUESTION_TIME_LIMIT: int = 30
    
    # Matchmaking
    MATCHMAKING_TIMEOUT_MINUTES: int = 5
    DEFAULT_MATCHMAKING_STRATEGY: str = "random"  # "random" or "rank_based"
    RANK_BASED_MATCHMAKING_RANGE: int = 200  # Rank difference for rank-based matching
    MATCHMAKING_PROCESS_INTERVAL_SECONDS: int = 5  # How often to process queue
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
