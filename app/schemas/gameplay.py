"""
Pydantic schemas for gameplay.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.competition import QuestionState


class AnswerSubmission(BaseModel):
    """Schema for answer submission."""
    answer_text: str = Field(..., min_length=1, max_length=500, description="User's answer")
    client_timestamp: Optional[float] = Field(None, description="Client-side timestamp for validation")


class AnswerResponse(BaseModel):
    """Schema for answer response."""
    answer_id: int
    question_id: int
    is_correct: bool
    correct_answer: str
    response_time: Optional[float]
    submitted_at: datetime
    
    class Config:
        from_attributes = True


class QuestionTimerResponse(BaseModel):
    """Schema for question timer information."""
    question_id: int
    time_limit: int
    started_at: datetime
    expires_at: datetime
    remaining_seconds: int
    
    class Config:
        from_attributes = True


class QuestionStateResponse(BaseModel):
    """Schema for question state."""
    question_id: int
    state: QuestionState
    question_text: str
    time_limit: int
    question_order: int
    started_at: Optional[datetime]
    expires_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class QuestionResultResponse(BaseModel):
    """Schema for question result."""
    question_id: int
    question_order: int
    player1_answer: Optional[str]
    player1_correct: Optional[bool]
    player2_answer: Optional[str]
    player2_correct: Optional[bool]
    winner: Optional[int]  # user_id of winner, None if tie
    correct_answer: str
    
    class Config:
        from_attributes = True


class CompetitionProgressResponse(BaseModel):
    """Schema for competition progress."""
    competition_id: int
    current_question_order: int
    total_questions: int
    player1_score: int
    player2_score: int
    status: str
    
    class Config:
        from_attributes = True
