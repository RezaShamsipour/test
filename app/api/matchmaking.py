"""
Matchmaking endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.services.matchmaking_service import matchmaking_service
from app.schemas.matchmaking import (
    MatchmakingJoinRequest,
    MatchmakingStatusResponse,
    MatchFoundResponse,
)
from app.models.user import User
from app.models.matchmaking import MatchmakingQueue, MatchmakingStatus
from app.models.competition import Competition
from app.models.matchmaking import MatchmakingStrategy
from datetime import datetime, timezone

router = APIRouter(prefix="/api/matchmaking", tags=["matchmaking"])


@router.post("/join", response_model=MatchmakingStatusResponse)
async def join_matchmaking_queue(
    request: MatchmakingJoinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    Join the matchmaking queue.
    """
    # Check if user is already in an active competition
    from app.models.competition import CompetitionStatus
    from sqlalchemy import select, or_, and_
    
    active_competition = await db.execute(
        select(Competition).where(
            and_(
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                ),
                Competition.status.in_([CompetitionStatus.PENDING, CompetitionStatus.ACTIVE])
            )
        )
    )
    if active_competition.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already in an active competition"
        )
    
    # Join queue
    queue_entry = await matchmaking_service.join_queue(
        db, current_user.id, request.strategy
    )
    
    # Process queue in background
    if background_tasks:
        background_tasks.add_task(matchmaking_service.process_queue, db)
    
    # Calculate wait time
    wait_time = None
    if queue_entry.entered_at:
        wait_time = int((datetime.now(timezone.utc) - queue_entry.entered_at).total_seconds())
    
    return MatchmakingStatusResponse(
        user_id=queue_entry.user_id,
        status=queue_entry.status,
        strategy=queue_entry.matchmaking_strategy,
        entered_at=queue_entry.entered_at,
        wait_time_seconds=wait_time
    )


@router.post("/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_matchmaking_queue(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Leave the matchmaking queue.
    """
    success = await matchmaking_service.leave_queue(db, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not in the matchmaking queue"
        )
    
    return None


@router.get("/status", response_model=MatchmakingStatusResponse)
async def get_matchmaking_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current matchmaking queue status for the user.
    """
    queue_entry = await matchmaking_service.get_queue_status(db, current_user.id)
    
    if not queue_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not in the matchmaking queue"
        )
    
    # Calculate wait time
    wait_time = None
    if queue_entry.entered_at:
        wait_time = int((datetime.now(timezone.utc) - queue_entry.entered_at).total_seconds())
    
    return MatchmakingStatusResponse(
        user_id=queue_entry.user_id,
        status=queue_entry.status,
        strategy=queue_entry.matchmaking_strategy,
        entered_at=queue_entry.entered_at,
        wait_time_seconds=wait_time
    )


@router.get("/check-match")
async def check_for_match(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if a match has been found for the user.
    Returns competition ID if match found, None otherwise.
    """
    # Check if user has a matched queue entry
    from sqlalchemy import select, and_
    from app.models.matchmaking import MatchmakingStatus
    
    queue_entry = await db.execute(
        select(MatchmakingQueue).where(
            and_(
                MatchmakingQueue.user_id == current_user.id,
                MatchmakingQueue.status == MatchmakingStatus.MATCHED
            )
        )
        .order_by(MatchmakingQueue.entered_at.desc())
        .limit(1)
    )
    queue_entry = queue_entry.scalar_one_or_none()
    
    if not queue_entry:
        return {"match_found": False, "competition_id": None}
    
    # Find the competition
    from app.models.competition import Competition, CompetitionStatus
    from sqlalchemy import or_
    
    competition = await db.execute(
        select(Competition).where(
            and_(
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                ),
                Competition.status == CompetitionStatus.PENDING
            )
        )
        .order_by(Competition.created_at.desc())
        .limit(1)
    )
    competition = competition.scalar_one_or_none()
    
    if competition:
        return {
            "match_found": True,
            "competition_id": competition.id,
            "player1_id": competition.player1_id,
            "player2_id": competition.player2_id
        }
    
    return {"match_found": False, "competition_id": None}
