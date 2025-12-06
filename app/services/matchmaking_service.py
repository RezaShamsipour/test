"""
Matchmaking service for handling queue operations and match creation.
"""
from typing import Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from app.models.user import User
from app.models.matchmaking import MatchmakingQueue, MatchmakingStrategy, MatchmakingStatus
from app.models.competition import Competition, CompetitionStatus
from app.services.matchmaking_strategies import MatchmakingStrategyFactory
from app.config import settings
import asyncio
import logging

logger = logging.getLogger(__name__)


class MatchmakingService:
    """Service for matchmaking operations."""
    
    def __init__(self):
        self._lock = asyncio.Lock()  # For thread-safe queue operations
    
    async def join_queue(
        self,
        db: AsyncSession,
        user_id: int,
        strategy: MatchmakingStrategy = MatchmakingStrategy.RANDOM
    ) -> MatchmakingQueue:
        """
        Add a user to the matchmaking queue.
        """
        async with self._lock:
            # Check if user is already in queue
            result = await db.execute(
                select(MatchmakingQueue).where(
                    and_(
                        MatchmakingQueue.user_id == user_id,
                        MatchmakingQueue.status == MatchmakingStatus.WAITING
                    )
                )
            )
            existing_entry = result.scalar_one_or_none()
            
            if existing_entry:
                # Update strategy if different
                if existing_entry.matchmaking_strategy != strategy:
                    existing_entry.matchmaking_strategy = strategy
                    db.add(existing_entry)
                    await db.commit()
                return existing_entry
            
            # Create new queue entry
            queue_entry = MatchmakingQueue(
                user_id=user_id,
                matchmaking_strategy=strategy,
                status=MatchmakingStatus.WAITING
            )
            
            db.add(queue_entry)
            await db.commit()
            await db.refresh(queue_entry)
            
            # Try to find a match immediately
            await self._try_find_match(db, user_id, strategy)
            
            return queue_entry
    
    async def leave_queue(
        self,
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """
        Remove a user from the matchmaking queue.
        """
        async with self._lock:
            result = await db.execute(
                select(MatchmakingQueue).where(
                    and_(
                        MatchmakingQueue.user_id == user_id,
                        MatchmakingQueue.status == MatchmakingStatus.WAITING
                    )
                )
            )
            queue_entry = result.scalar_one_or_none()
            
            if queue_entry:
                queue_entry.status = MatchmakingStatus.CANCELLED
                db.add(queue_entry)
                await db.commit()
                return True
            
            return False
    
    async def get_queue_status(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Optional[MatchmakingQueue]:
        """
        Get the current queue status for a user.
        """
        result = await db.execute(
            select(MatchmakingQueue).where(
                and_(
                    MatchmakingQueue.user_id == user_id,
                    MatchmakingQueue.status == MatchmakingStatus.WAITING
                )
            )
            .order_by(MatchmakingQueue.entered_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def _try_find_match(
        self,
        db: AsyncSession,
        user_id: int,
        strategy: MatchmakingStrategy
    ) -> Optional[Competition]:
        """
        Try to find a match for the user.
        """
        strategy_instance = MatchmakingStrategyFactory.get_strategy(strategy)
        matched_user_id = await strategy_instance.find_match(db, user_id, strategy)
        
        if matched_user_id:
            # Create competition
            competition = await self._create_competition(db, user_id, matched_user_id)
            
            # Update queue entries
            await self._update_queue_entries(db, user_id, matched_user_id, competition.id)
            
            return competition
        
        return None
    
    async def _create_competition(
        self,
        db: AsyncSession,
        player1_id: int,
        player2_id: int
    ) -> Competition:
        """
        Create a competition between two players.
        Questions will be selected when the competition starts.
        """
        competition = Competition(
            player1_id=player1_id,
            player2_id=player2_id,
            status=CompetitionStatus.PENDING
        )
        
        db.add(competition)
        await db.commit()
        await db.refresh(competition)
        
        logger.info(f"Created competition {competition.id} between users {player1_id} and {player2_id}")
        
        return competition
    
    async def _update_queue_entries(
        self,
        db: AsyncSession,
        user1_id: int,
        user2_id: int,
        competition_id: int
    ):
        """
        Update queue entries to mark users as matched.
        """
        # Update user1's queue entry
        result1 = await db.execute(
            select(MatchmakingQueue).where(
                and_(
                    MatchmakingQueue.user_id == user1_id,
                    MatchmakingQueue.status == MatchmakingStatus.WAITING
                )
            )
        )
        entry1 = result1.scalar_one_or_none()
        if entry1:
            entry1.status = MatchmakingStatus.MATCHED
            db.add(entry1)
        
        # Update user2's queue entry
        result2 = await db.execute(
            select(MatchmakingQueue).where(
                and_(
                    MatchmakingQueue.user_id == user2_id,
                    MatchmakingQueue.status == MatchmakingStatus.WAITING
                )
            )
        )
        entry2 = result2.scalar_one_or_none()
        if entry2:
            entry2.status = MatchmakingStatus.MATCHED
            db.add(entry2)
        
        await db.commit()
    
    async def cleanup_stale_entries(self, db: AsyncSession):
        """
        Remove stale queue entries (timeout).
        """
        timeout_threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.MATCHMAKING_TIMEOUT_MINUTES
        )
        
        async with self._lock:
            # Find stale entries
            result = await db.execute(
                select(MatchmakingQueue).where(
                    and_(
                        MatchmakingQueue.status == MatchmakingStatus.WAITING,
                        MatchmakingQueue.entered_at < timeout_threshold
                    )
                )
            )
            stale_entries = result.scalars().all()
            
            for entry in stale_entries:
                entry.status = MatchmakingStatus.TIMEOUT
                db.add(entry)
            
            if stale_entries:
                await db.commit()
                logger.info(f"Cleaned up {len(stale_entries)} stale matchmaking entries")
    
    async def process_queue(self, db: AsyncSession):
        """
        Process the matchmaking queue to find matches.
        This can be called periodically by a background task.
        """
        async with self._lock:
            # Get all waiting users grouped by strategy
            result = await db.execute(
                select(MatchmakingQueue).where(
                    MatchmakingQueue.status == MatchmakingStatus.WAITING
                )
                .order_by(MatchmakingQueue.entered_at)
            )
            waiting_entries = result.scalars().all()
            
            # Try to match users
            processed_users = set()
            
            for entry in waiting_entries:
                if entry.user_id in processed_users:
                    continue
                
                strategy_instance = MatchmakingStrategyFactory.get_strategy(entry.matchmaking_strategy)
                matched_user_id = await strategy_instance.find_match(
                    db, entry.user_id, entry.matchmaking_strategy
                )
                
                if matched_user_id and matched_user_id not in processed_users:
                    # Create competition
                    competition = await self._create_competition(
                        db, entry.user_id, matched_user_id
                    )
                    
                    # Update queue entries
                    await self._update_queue_entries(
                        db, entry.user_id, matched_user_id, competition.id
                    )
                    
                    processed_users.add(entry.user_id)
                    processed_users.add(matched_user_id)


# Global service instance
matchmaking_service = MatchmakingService()
