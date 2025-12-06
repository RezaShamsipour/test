"""
Pydantic schemas for scoring and leaderboard.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class QuestionScoreResponse(BaseModel):
    """Schema for question score."""
    question_id: int
    question_order: int
    player1_score: float
    player2_score: float


class CompetitionScoreResponse(BaseModel):
    """Schema for competition score."""
    competition_id: int
    player1_id: int
    player2_id: int
    player1_total_score: float
    player2_total_score: float
    question_scores: List[QuestionScoreResponse]
    winner_id: Optional[int]
    
    class Config:
        from_attributes = True


class LeaderboardEntry(BaseModel):
    """Schema for leaderboard entry."""
    user_id: int
    username: str
    rank: float
    wins: int
    losses: int
    total_competitions: int
    win_rate: float
    
    class Config:
        from_attributes = True


class CompetitionDetailResponse(BaseModel):
    """Schema for detailed competition result."""
    competition_id: int
    player1_id: int
    player1_username: str
    player2_id: int
    player2_username: str
    player1_score: float
    player2_score: float
    winner_id: Optional[int]
    winner_username: Optional[str]
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    questions: List[dict]
    
    class Config:
        from_attributes = True


class UserStatisticsResponse(BaseModel):
    """Schema for user statistics."""
    user_id: int
    username: str
    rank: float
    total_competitions: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    average_score: Optional[float]
    best_rank: Optional[float]
    current_streak: Optional[int]
    
    class Config:
        from_attributes = True
