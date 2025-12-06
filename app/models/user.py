"""
User and authentication models.
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    rank = Column(Float, default=1000.0, nullable=False)  # ELO-like rating system
    # Statistics fields (can be calculated or stored)
    total_competitions = Column(Integer, default=0, nullable=False)
    wins = Column(Integer, default=0, nullable=False)
    losses = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    competitions_as_player1 = relationship("Competition", foreign_keys="Competition.player1_id", back_populates="player1")
    competitions_as_player2 = relationship("Competition", foreign_keys="Competition.player2_id", back_populates="player2")
    answers = relationship("Answer", back_populates="user")
    matchmaking_queues = relationship("MatchmakingQueue", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_user_rank", "rank"),
        Index("idx_user_username", "username"),
        Index("idx_user_email", "email"),
    )


class Token(Base):
    """Token/Session model for authentication."""
    __tablename__ = "tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="tokens")
    
    __table_args__ = (
        Index("idx_token_user_id", "user_id"),
        Index("idx_token_expires_at", "expires_at"),
        Index("idx_token_token", "token"),
    )
