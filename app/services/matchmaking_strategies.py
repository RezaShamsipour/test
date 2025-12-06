"""
Matchmaking strategy implementations.
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.models.user import User
from app.models.matchmaking import MatchmakingQueue, MatchmakingStrategy, MatchmakingStatus
from app.config import settings
from datetime import datetime, timezone, timedelta


class MatchmakingStrategyInterface(ABC):
    """Abstract base class for matchmaking strategies."""
    
    @abstractmethod
    async def find_match(
        self,
        db: AsyncSession,
        user_id: int,
        strategy: MatchmakingStrategy
    ) -> Optional[int]:
        """
        Find a match for the given user.
        
        Args:
            db: Database session
            user_id: ID of the user looking for a match
            strategy: Matchmaking strategy to use
        
        Returns:
            ID of matched user if found, None otherwise
        """
        pass


class RandomMatchmakingStrategy(MatchmakingStrategyInterface):
    """Random matchmaking strategy - matches users randomly."""
    
    async def find_match(
        self,
        db: AsyncSession,
        user_id: int,
        strategy: MatchmakingStrategy
    ) -> Optional[int]:
        """
        Find a random match for the user.
        """
        # Find another user waiting in the queue with the same strategy
        result = await db.execute(
            select(MatchmakingQueue.user_id)
            .where(
                and_(
                    MatchmakingQueue.user_id != user_id,
                    MatchmakingQueue.matchmaking_strategy == strategy,
                    MatchmakingQueue.status == MatchmakingStatus.WAITING
                )
            )
            .order_by(func.random())  # Random order
            .limit(1)
        )
        
        matched_user_id = result.scalar_one_or_none()
        return matched_user_id


class RankBasedMatchmakingStrategy(MatchmakingStrategyInterface):
    """Rank-based matchmaking strategy - matches users with similar ranks."""
    
    def __init__(self, rank_range: int = 200):
        self.RANK_RANGE = rank_range
    
    async def find_match(
        self,
        db: AsyncSession,
        user_id: int,
        strategy: MatchmakingStrategy
    ) -> Optional[int]:
        """
        Find a match based on user rank similarity.
        """
        # Get current user's rank
        user_result = await db.execute(
            select(User.rank).where(User.id == user_id)
        )
        user_rank = user_result.scalar_one_or_none()
        
        if user_rank is None:
            return None
        
        # Find users within rank range
        min_rank = user_rank - self.RANK_RANGE
        max_rank = user_rank + self.RANK_RANGE
        
        # Find a waiting user with similar rank
        result = await db.execute(
            select(MatchmakingQueue.user_id, User.rank)
            .join(User, MatchmakingQueue.user_id == User.id)
            .where(
                and_(
                    MatchmakingQueue.user_id != user_id,
                    MatchmakingQueue.matchmaking_strategy == strategy,
                    MatchmakingQueue.status == MatchmakingStatus.WAITING,
                    User.rank >= min_rank,
                    User.rank <= max_rank
                )
            )
            .order_by(func.abs(User.rank - user_rank))  # Closest rank first
            .limit(1)
        )
        
        match = result.first()
        if match:
            return match[0]  # Return user_id
        
        return None


class MatchmakingStrategyFactory:
    """Factory for creating matchmaking strategy instances."""
    
    _strategies: dict[MatchmakingStrategy, MatchmakingStrategyInterface] = {}
    _initialized = False
    
    @classmethod
    def _initialize_strategies(cls):
        """Initialize strategies with configuration."""
        from app.config import settings
        if not cls._initialized:
            cls._strategies = {
                MatchmakingStrategy.RANDOM: RandomMatchmakingStrategy(),
                MatchmakingStrategy.RANK_BASED: RankBasedMatchmakingStrategy(
                    rank_range=settings.RANK_BASED_MATCHMAKING_RANGE
                ),
            }
            cls._initialized = True
    
    @classmethod
    def get_strategy(cls, strategy: MatchmakingStrategy) -> MatchmakingStrategyInterface:
        """Get a matchmaking strategy instance."""
        cls._initialize_strategies()
        return cls._strategies.get(strategy, cls._strategies[MatchmakingStrategy.RANDOM])
    
    @classmethod
    def register_strategy(
        cls,
        strategy: MatchmakingStrategy,
        strategy_instance: MatchmakingStrategyInterface
    ):
        """Register a new matchmaking strategy."""
        cls._initialize_strategies()
        cls._strategies[strategy] = strategy_instance
