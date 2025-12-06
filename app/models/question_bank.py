"""
Question bank model for storing available questions.
"""
from sqlalchemy import Column, Integer, String, DateTime, Enum, Index, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class QuestionDifficulty(str, enum.Enum):
    """Question difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionCategory(str, enum.Enum):
    """Question categories."""
    GENERAL = "general"
    SCIENCE = "science"
    HISTORY = "history"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    GEOGRAPHY = "geography"
    LITERATURE = "literature"
    TECHNOLOGY = "technology"
    MATH = "math"
    OTHER = "other"


class QuestionBank(Base):
    """Question bank model for storing available questions."""
    __tablename__ = "question_bank"
    
    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    correct_answer = Column(String(500), nullable=False)
    category = Column(Enum(QuestionCategory), default=QuestionCategory.GENERAL, nullable=False, index=True)
    difficulty = Column(Enum(QuestionDifficulty), default=QuestionDifficulty.MEDIUM, nullable=False, index=True)
    tags = Column(String(500), nullable=True)  # Comma-separated tags
    is_active = Column(Integer, default=1, nullable=False)  # 1 = active, 0 = inactive
    usage_count = Column(Integer, default=0, nullable=False)  # Track how many times used
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("idx_question_bank_category", "category"),
        Index("idx_question_bank_difficulty", "difficulty"),
        Index("idx_question_bank_active", "is_active"),
        Index("idx_question_bank_category_difficulty", "category", "difficulty"),
    )
