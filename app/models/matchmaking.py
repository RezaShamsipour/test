"""
Matchmaking queue model.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class MatchmakingStrategy(str, enum.Enum):
    """Matchmaking strategy enumeration."""
    RANDOM = "random"
    RANK_BASED = "rank_based"


class MatchmakingStatus(str, enum.Enum):
    """Matchmaking queue status enumeration."""
    WAITING = "waiting"
    MATCHED = "matched"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class MatchmakingQueue(Base):
    """Matchmaking queue model."""
    __tablename__ = "matchmaking_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    matchmaking_strategy = Column(Enum(MatchmakingStrategy), default=MatchmakingStrategy.RANDOM, nullable=False, index=True)
    status = Column(Enum(MatchmakingStatus), default=MatchmakingStatus.WAITING, nullable=False, index=True)
    entered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="matchmaking_queues")
    
    __table_args__ = (
        Index("idx_matchmaking_user", "user_id"),
        Index("idx_matchmaking_strategy", "matchmaking_strategy"),
        Index("idx_matchmaking_status", "status"),
        Index("idx_matchmaking_entered_at", "entered_at"),
        Index("idx_matchmaking_user_strategy_status", "user_id", "matchmaking_strategy", "status"),
    )
