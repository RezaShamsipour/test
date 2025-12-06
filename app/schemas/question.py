"""
Pydantic schemas for questions.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from app.models.question_bank import QuestionDifficulty, QuestionCategory


class QuestionBankCreate(BaseModel):
    """Schema for creating a question in the bank."""
    question_text: str = Field(..., min_length=10, max_length=1000, description="Question text")
    correct_answer: str = Field(..., min_length=1, max_length=500, description="Correct answer")
    category: QuestionCategory = Field(default=QuestionCategory.GENERAL, description="Question category")
    difficulty: QuestionDifficulty = Field(default=QuestionDifficulty.MEDIUM, description="Question difficulty")
    tags: Optional[str] = Field(None, max_length=500, description="Comma-separated tags")
    
    @validator("question_text")
    def validate_question_text(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("Question text must be at least 10 characters")
        return v.strip()


class QuestionBankUpdate(BaseModel):
    """Schema for updating a question in the bank."""
    question_text: Optional[str] = Field(None, min_length=10, max_length=1000)
    correct_answer: Optional[str] = Field(None, min_length=1, max_length=500)
    category: Optional[QuestionCategory] = None
    difficulty: Optional[QuestionDifficulty] = None
    tags: Optional[str] = Field(None, max_length=500)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class QuestionBankResponse(BaseModel):
    """Schema for question bank response."""
    id: int
    question_text: str
    correct_answer: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    tags: Optional[str]
    is_active: int
    usage_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class QuestionBankBulkCreate(BaseModel):
    """Schema for bulk question creation."""
    questions: List[QuestionBankCreate] = Field(..., min_items=1, max_items=100)


class CompetitionQuestionResponse(BaseModel):
    """Schema for competition question response."""
    id: int
    competition_id: int
    question_text: str
    time_limit: int
    question_order: int
    created_at: datetime
    
    class Config:
        from_attributes = True
