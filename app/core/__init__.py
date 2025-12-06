"""
Core utilities for the Quiz Game application.
"""
from app.core.database import Base, get_db, init_db, close_db, AsyncSessionLocal
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_password_strength,
)
from app.core.middleware import get_current_user, check_rate_limit
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import (
    QuizGameException,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    ConflictError,
    RateLimitError,
)

__all__ = [
    # Database
    "Base",
    "get_db",
    "init_db",
    "close_db",
    "AsyncSessionLocal",
    # Security
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "validate_password_strength",
    # Middleware
    "get_current_user",
    "check_rate_limit",
    # Logging
    "setup_logging",
    "get_logger",
    # Exceptions
    "QuizGameException",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "RateLimitError",
]
