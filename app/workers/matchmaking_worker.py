"""
Background worker for processing matchmaking queue.
"""
import asyncio
import logging
from typing import Optional
from app.core.database import AsyncSessionLocal
from app.services.matchmaking_service import matchmaking_service
from app.config import settings

logger = logging.getLogger(__name__)


class MatchmakingWorker:
    """Worker for processing matchmaking queue."""
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def process_queue(self):
        """
        Background task to periodically process the matchmaking queue.
        """
        while self._running:
            try:
                async with AsyncSessionLocal() as db:
                    # Process queue to find matches
                    await matchmaking_service.process_queue(db)
                    
                    # Cleanup stale entries
                    await matchmaking_service.cleanup_stale_entries(db)
                    
            except Exception as e:
                logger.error(f"Error processing matchmaking queue: {e}")
            
            # Wait before next iteration
            await asyncio.sleep(settings.MATCHMAKING_PROCESS_INTERVAL_SECONDS)
    
    async def start(self):
        """Start the worker."""
        if self._running:
            logger.warning("Matchmaking worker is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self.process_queue())
        logger.info("Matchmaking worker started")
    
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
        logger.info("Matchmaking worker stopped")


# Global worker instance
_matchmaking_worker: Optional[MatchmakingWorker] = None


async def start_matchmaking_worker():
    """Start the matchmaking worker."""
    global _matchmaking_worker
    if _matchmaking_worker is None:
        _matchmaking_worker = MatchmakingWorker()
    await _matchmaking_worker.start()
    return _matchmaking_worker
