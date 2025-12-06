"""
Background worker for competition timeout handling.
"""
import asyncio
import logging
from typing import Optional
from app.core.database import AsyncSessionLocal
from app.services.competition_service import competition_service
from app.models.competition import Competition, CompetitionStatus
from sqlalchemy import select
from app.config import settings

logger = logging.getLogger(__name__)


class CompetitionWorker:
    """Worker for handling competition timeouts."""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def process_timeouts(self):
        """
        Background task to periodically check for competition timeouts.
        """
        while self._running:
            try:
                async with AsyncSessionLocal() as db:
                    # Find pending or active competitions
                    result = await db.execute(
                        select(Competition).where(
                            Competition.status.in_([
                                CompetitionStatus.PENDING,
                                CompetitionStatus.ACTIVE
                            ])
                        )
                    )
                    competitions = result.scalars().all()
                    
                    # Check each competition for timeout
                    for competition in competitions:
                        try:
                            await competition_service.check_competition_timeout(
                                db, competition.id, timeout_minutes=30
                            )
                        except Exception as e:
                            logger.error(f"Error checking timeout for competition {competition.id}: {e}")
                    
            except Exception as e:
                logger.error(f"Error processing competition timeouts: {e}")
            
            # Wait before next iteration (check every minute)
            await asyncio.sleep(60)
    
    async def start(self):
        """Start the worker."""
        if self._running:
            logger.warning("Competition worker is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self.process_timeouts())
        logger.info("Competition worker started")
    
    async def stop(self):
        """Stop the worker."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Competition worker stopped")


# Global worker instance
_competition_worker: Optional[CompetitionWorker] = None


async def start_competition_worker():
    """Start the competition worker."""
    global _competition_worker
    if _competition_worker is None:
        _competition_worker = CompetitionWorker()
    await _competition_worker.start()
    return _competition_worker
