"""
Pydantic schemas for user management.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    username: str
    email: str
    rank: float
    total_competitions: int
    wins: int
    losses: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for user profile update."""
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Username (3-50 characters)")
    email: Optional[EmailStr] = Field(None, description="User email address")
    
    @validator("username")
    def validate_username(cls, v):
        if v is not None:
            if not v.isalnum() and "_" not in v:
                raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v


class UserStatistics(BaseModel):
    """Schema for user statistics."""
    total_competitions: int
    wins: int
    losses: int
    win_rate: float  # Calculated: wins / total_competitions * 100
    rank: float
    current_streak: Optional[int] = None  # Can be calculated from recent competitions
    
    class Config:
        from_attributes = True
