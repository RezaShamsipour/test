"""
Service for competition lifecycle management.
"""
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.models.competition import Competition, CompetitionStatus, Question
from app.models.user import User
from app.services.question_service import question_service
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class CompetitionService:
    """Service for competition operations."""
    
    @staticmethod
    async def start_competition(
        db: AsyncSession,
        competition_id: int
    ) -> Competition:
        """
        Start a competition by selecting questions and changing status to ACTIVE.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        if competition.status != CompetitionStatus.PENDING:
            raise ValueError(f"Cannot start competition with status {competition.status}")
        
        # Select questions for competition
        questions = await question_service.select_questions_for_competition(
            db,
            competition_id,
            count=settings.DEFAULT_QUESTIONS_PER_COMPETITION,
            strategy="random"
        )
        
        if not questions:
            raise ValueError("Failed to select questions for competition")
        
        # Update competition status
        competition.status = CompetitionStatus.ACTIVE
        competition.started_at = datetime.now(timezone.utc)
        competition.current_question_order = 0  # Will be set when first question starts
        
        db.add(competition)
        await db.commit()
        await db.refresh(competition)
        
        logger.info(f"Started competition {competition_id} with {len(questions)} questions")
        
        return competition
    
    @staticmethod
    async def complete_competition(
        db: AsyncSession,
        competition_id: int,
        winner_id: Optional[int] = None
    ) -> Competition:
        """
        Mark a competition as completed.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        competition.status = CompetitionStatus.COMPLETED
        competition.completed_at = datetime.now(timezone.utc)
        
        if winner_id:
            competition.winner_id = winner_id
        
        db.add(competition)
        await db.commit()
        await db.refresh(competition)
        
        logger.info(f"Completed competition {competition_id}, winner: {winner_id}")
        
        return competition
    
    @staticmethod
    async def cancel_competition(
        db: AsyncSession,
        competition_id: int
    ) -> Competition:
        """
        Cancel a competition.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        competition.status = CompetitionStatus.CANCELLED
        
        db.add(competition)
        await db.commit()
        await db.refresh(competition)
        
        logger.info(f"Cancelled competition {competition_id}")
        
        return competition
    
    @staticmethod
    async def get_competition_history(
        db: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        status: Optional[CompetitionStatus] = None
    ) -> List[Competition]:
        """
        Get competition history for a user.
        """
        query = select(Competition).where(
            or_(
                Competition.player1_id == user_id,
                Competition.player2_id == user_id
            )
        )
        
        if status:
            query = query.where(Competition.status == status)
        
        query = query.order_by(Competition.created_at.desc()).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def check_competition_timeout(
        db: AsyncSession,
        competition_id: int,
        timeout_minutes: int = 30
    ) -> bool:
        """
        Check if a competition has timed out and should be cancelled.
        Returns True if timed out.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            return False
        
        if competition.status not in [CompetitionStatus.PENDING, CompetitionStatus.ACTIVE]:
            return False
        
        # Check if competition started and has been active too long
        if competition.started_at:
            timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            if competition.started_at < timeout_threshold:
                await CompetitionService.cancel_competition(db, competition_id)
                return True
        
        # Check if competition has been pending too long
        if competition.status == CompetitionStatus.PENDING:
            timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
            if competition.created_at < timeout_threshold:
                await CompetitionService.cancel_competition(db, competition_id)
                return True
        
        return False
    
    @staticmethod
    async def get_competition_questions(
        db: AsyncSession,
        competition_id: int
    ) -> List[Question]:
        """
        Get all questions for a competition.
        """
        result = await db.execute(
            select(Question).where(
                Question.competition_id == competition_id
            ).order_by(Question.question_order)
        )
        return list(result.scalars().all())


# Global service instance
competition_service = CompetitionService()
