"""
Pydantic schemas for authentication.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50, description="Username (3-50 characters)")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 characters)")
    
    @validator("username")
    def validate_username(cls, v):
        if not v.isalnum() and "_" not in v:
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class UserResponse(BaseModel):
    """Schema for user response (for auth endpoints)."""
    id: int
    username: str
    email: str
    rank: float
    created_at: datetime
    
    class Config:
        from_attributes = True
