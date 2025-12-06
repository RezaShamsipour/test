"""
Competition endpoints for match confirmation and management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Optional, List
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.models.user import User
from app.models.competition import Competition, CompetitionStatus, Question
from app.models.matchmaking import MatchmakingStatus
from app.services.competition_service import competition_service
from app.services.gameplay_service import gameplay_service
from app.schemas.question import CompetitionQuestionResponse
from app.schemas.gameplay import QuestionTimerResponse, CompetitionProgressResponse, QuestionResultResponse
from datetime import datetime, timezone
from pydantic import BaseModel

router = APIRouter(prefix="/api/competitions", tags=["competitions"])


class CompetitionResponse(BaseModel):
    """Schema for competition response."""
    id: int
    player1_id: int
    player2_id: int
    status: str
    winner_id: int | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    class Config:
        from_attributes = True


@router.post("/{competition_id}/confirm", response_model=CompetitionResponse)
async def confirm_match(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm a match and start the competition.
    This will select questions and start the competition.
    """
    # Get competition
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                ),
                Competition.status == CompetitionStatus.PENDING
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    # Start competition (selects questions and changes status to ACTIVE)
    try:
        competition = await competition_service.start_competition(db, competition_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return competition


@router.post("/{competition_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_match(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Reject a match (cancel the competition).
    """
    # Get competition
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                ),
                Competition.status == CompetitionStatus.PENDING
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    # Cancel competition
    competition.status = CompetitionStatus.CANCELLED
    
    # Update matchmaking queue entries back to waiting
    from app.models.matchmaking import MatchmakingQueue
    await db.execute(
        select(MatchmakingQueue).where(
            and_(
                or_(
                    MatchmakingQueue.user_id == competition.player1_id,
                    MatchmakingQueue.user_id == competition.player2_id
                ),
                MatchmakingQueue.status == MatchmakingStatus.MATCHED
            )
        )
    )
    
    db.add(competition)
    await db.commit()
    
    return None


@router.get("/{competition_id}", response_model=CompetitionResponse)
async def get_competition(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get competition details.
    """
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                )
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    return competition


@router.get("/{competition_id}/questions", response_model=List[CompetitionQuestionResponse])
async def get_competition_questions(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all questions for a competition.
    """
    # Verify user is a participant
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                )
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    questions = await competition_service.get_competition_questions(db, competition_id)
    return questions


@router.get("/{competition_id}/current-question")
async def get_current_question(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current active question for a competition.
    """
    # Verify user is a participant
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                )
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    question = await gameplay_service.get_current_question(db, competition_id)
    
    if not question:
        return {"question": None, "message": "No active question"}
    
    timer_info = await gameplay_service.get_question_timer(db, question.id)
    
    return {
        "question_id": question.id,
        "question_text": question.question_text,
        "question_order": question.question_order,
        "time_limit": question.time_limit,
        "state": question.state.value,
        "timer": timer_info
    }


@router.get("/{competition_id}/progress", response_model=CompetitionProgressResponse)
async def get_competition_progress(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current progress of a competition.
    """
    # Verify user is a participant
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                )
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    progress = await gameplay_service.get_competition_progress(db, competition_id)
    return progress


@router.post("/{competition_id}/questions/{question_id}/start")
async def start_question(
    competition_id: int,
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a question (activate timer).
    """
    # Verify user is a participant
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                )
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    try:
        question = await gameplay_service.activate_question(
            db, competition_id, competition.current_question_order + 1
        )
        timer_info = await gameplay_service.get_question_timer(db, question.id)
        return {
            "question_id": question.id,
            "question_text": question.question_text,
            "question_order": question.question_order,
            "time_limit": question.time_limit,
            "timer": timer_info
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{competition_id}/questions/{question_id}/result", response_model=QuestionResultResponse)
async def get_question_result(
    competition_id: int,
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get result for a completed question.
    """
    # Verify user is a participant
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                )
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    try:
        result_data = await gameplay_service.calculate_question_result(db, question_id)
        return result_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/history", response_model=List[CompetitionResponse])
async def get_competition_history(
    status_filter: Optional[CompetitionStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Number of competitions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get competition history for the current user.
    """
    competitions = await competition_service.get_competition_history(
        db, current_user.id, limit=limit, offset=offset, status=status_filter
    )
    return competitions


@router.post("/{competition_id}/cancel", response_model=CompetitionResponse)
async def cancel_competition(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a competition (only if pending or active).
    """
    # Verify user is a participant
    result = await db.execute(
        select(Competition).where(
            and_(
                Competition.id == competition_id,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                )
            )
        )
    )
    competition = result.scalar_one_or_none()
    
    if not competition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competition not found or you are not a participant"
        )
    
    if competition.status in [CompetitionStatus.COMPLETED, CompetitionStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel competition with status {competition.status}"
        )
    
    try:
        competition = await competition_service.cancel_competition(db, competition_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return competition
