"""
Competition, Question, and Answer models.
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class CompetitionStatus(str, enum.Enum):
    """Competition status enumeration."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class QuestionState(str, enum.Enum):
    """Question state enumeration."""
    PENDING = "pending"
    ACTIVE = "active"
    ANSWERED = "answered"
    EXPIRED = "expired"


class Competition(Base):
    """Competition model."""
    __tablename__ = "competitions"
    
    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    player2_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(Enum(CompetitionStatus), default=CompetitionStatus.PENDING, nullable=False, index=True)
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    current_question_order = Column(Integer, default=0, nullable=False)  # Current question being answered
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    player1 = relationship("User", foreign_keys=[player1_id], back_populates="competitions_as_player1")
    player2 = relationship("User", foreign_keys=[player2_id], back_populates="competitions_as_player2")
    questions = relationship("Question", back_populates="competition", cascade="all, delete-orphan", order_by="Question.question_order")
    
    __table_args__ = (
        Index("idx_competition_player1", "player1_id"),
        Index("idx_competition_player2", "player2_id"),
        Index("idx_competition_status", "status"),
        Index("idx_competition_winner", "winner_id"),
    )


class Question(Base):
    """Question model for competitions."""
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False, index=True)
    question_text = Column(String(1000), nullable=False)
    correct_answer = Column(String(500), nullable=False)
    time_limit = Column(Integer, nullable=False)  # Time in seconds (15-30)
    question_order = Column(Integer, nullable=False)  # Order in competition (1-11)
    state = Column(Enum(QuestionState), default=QuestionState.PENDING, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)  # When question was activated
    expires_at = Column(DateTime(timezone=True), nullable=True)  # When question expires
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    competition = relationship("Competition", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_question_competition", "competition_id"),
        Index("idx_question_order", "competition_id", "question_order"),
        Index("idx_question_state", "state"),
    )


class Answer(Base):
    """Answer model for user responses."""
    __tablename__ = "answers"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    answer_text = Column(String(500), nullable=False)
    is_correct = Column(Integer, default=0, nullable=False)  # 0 = incorrect, 1 = correct
    response_time = Column(Float, nullable=True)  # Time taken to answer in seconds
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    question = relationship("Question", back_populates="answers")
    user = relationship("User", back_populates="answers")
    
    __table_args__ = (
        Index("idx_answer_question", "question_id"),
        Index("idx_answer_user", "user_id"),
        Index("idx_answer_question_user", "question_id", "user_id"),  # Unique constraint for one answer per user per question
    )
