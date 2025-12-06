"""
Pydantic schemas for matchmaking.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.matchmaking import MatchmakingStrategy, MatchmakingStatus


class MatchmakingJoinRequest(BaseModel):
    """Schema for joining matchmaking queue."""
    strategy: MatchmakingStrategy = Field(
        default=MatchmakingStrategy.RANDOM,
        description="Matchmaking strategy (random or rank_based)"
    )


class MatchmakingStatusResponse(BaseModel):
    """Schema for matchmaking status response."""
    user_id: int
    status: MatchmakingStatus
    strategy: MatchmakingStrategy
    entered_at: datetime
    wait_time_seconds: Optional[int] = None
    
    class Config:
        from_attributes = True


class MatchFoundResponse(BaseModel):
    """Schema for match found response."""
    competition_id: int
    player1_id: int
    player2_id: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True
