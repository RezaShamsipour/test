"""
User management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.schemas.user import UserResponse, UserUpdate, UserStatistics
from app.models.user import User
from app.models.competition import Competition, CompetitionStatus

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's profile information.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's profile (username and/or email).
    """
    # Check if username is being updated and if it's already taken
    if user_update.username and user_update.username != current_user.username:
        result = await db.execute(
            select(User).where(User.username == user_update.username)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken"
            )
        current_user.username = user_update.username
    
    # Check if email is being updated and if it's already taken
    if user_update.email and user_update.email != current_user.email:
        result = await db.execute(
            select(User).where(User.email == user_update.email)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already taken"
            )
        current_user.email = user_update.email
    
    # Update user
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.get("/me/statistics", response_model=UserStatistics)
async def get_user_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's detailed statistics.
    """
    # Calculate statistics from competitions
    # Count total completed competitions
    total_result = await db.execute(
        select(func.count(Competition.id)).where(
            and_(
                Competition.status == CompetitionStatus.COMPLETED,
                or_(
                    Competition.player1_id == current_user.id,
                    Competition.player2_id == current_user.id
                )
            )
        )
    )
    total_competitions = total_result.scalar() or 0
    
    # Count wins (where user is the winner)
    wins_result = await db.execute(
        select(func.count(Competition.id)).where(
            and_(
                Competition.status == CompetitionStatus.COMPLETED,
                Competition.winner_id == current_user.id
            )
        )
    )
    wins = wins_result.scalar() or 0
    
    # Calculate losses
    losses = total_competitions - wins
    
    # Calculate win rate
    win_rate = (wins / total_competitions * 100) if total_competitions > 0 else 0.0
    
    # Update user statistics in database (for quick access)
    current_user.total_competitions = total_competitions
    current_user.wins = wins
    current_user.losses = losses
    db.add(current_user)
    await db.commit()
    
    return UserStatistics(
        total_competitions=total_competitions,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 2),
        rank=current_user.rank,
        current_streak=None  # Can be implemented later with streak calculation
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_profile(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a user's public profile by ID.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.get("/{user_id}/competitions")
async def get_user_competitions(
    user_id: int,
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get competition history for a user.
    """
    from app.models.competition import CompetitionStatus
    from app.services.competition_service import competition_service
    
    status_enum = None
    if status_filter:
        try:
            status_enum = CompetitionStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    
    competitions = await competition_service.get_competition_history(
        db, user_id, limit=limit, offset=offset, status=status_enum
    )
    
    return competitions
