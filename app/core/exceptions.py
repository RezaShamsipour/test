"""
Custom exception classes for the application.
"""
from fastapi import HTTPException, status


class QuizGameException(HTTPException):
    """Base exception for Quiz Game application."""
    pass


class AuthenticationError(QuizGameException):
    """Authentication related errors."""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class AuthorizationError(QuizGameException):
    """Authorization related errors."""
    def __init__(self, detail: str = "Not authorized"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class NotFoundError(QuizGameException):
    """Resource not found errors."""
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class ValidationError(QuizGameException):
    """Validation errors."""
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


class ConflictError(QuizGameException):
    """Conflict errors (e.g., duplicate resources)."""
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )


class RateLimitError(QuizGameException):
    """Rate limiting errors."""
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )
