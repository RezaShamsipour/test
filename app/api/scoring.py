"""
Scoring and leaderboard endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from typing import Optional, List
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.models.user import User
from app.models.competition import Competition, CompetitionStatus
from app.schemas.scoring import (
    CompetitionScoreResponse,
    LeaderboardEntry,
    CompetitionDetailResponse,
    UserStatisticsResponse,
)
from app.services.scoring_service import scoring_service

router = APIRouter(prefix="/api", tags=["scoring"])


@router.get("/competitions/{competition_id}/scores", response_model=CompetitionScoreResponse)
async def get_competition_scores(
    competition_id: int,
    use_time_bonus: bool = Query(False, description="Include time-based bonus scoring"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed scores for a competition.
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
        scores = await scoring_service.calculate_competition_scores(
            db, competition_id, use_time_bonus
        )
        scores["winner_id"] = competition.winner_id
        return scores
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    limit: int = Query(100, ge=1, le=1000, description="Number of entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get leaderboard (top users by rank).
    """
    result = await db.execute(
        select(User).where(
            User.total_competitions > 0  # Only users who have played
        )
        .order_by(desc(User.rank))
        .limit(limit)
        .offset(offset)
    )
    users = list(result.scalars().all())
    
    leaderboard = []
    for user in users:
        win_rate = (user.wins / user.total_competitions * 100) if user.total_competitions > 0 else 0.0
        leaderboard.append(LeaderboardEntry(
            user_id=user.id,
            username=user.username,
            rank=user.rank,
            wins=user.wins,
            losses=user.losses,
            total_competitions=user.total_competitions,
            win_rate=round(win_rate, 2)
        ))
    
    return leaderboard


@router.get("/competitions/{competition_id}/details", response_model=CompetitionDetailResponse)
async def get_competition_details(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed competition results including all questions and answers.
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
    
    # Get player usernames
    player1_result = await db.execute(select(User).where(User.id == competition.player1_id))
    player1 = player1_result.scalar_one_or_none()
    
    player2_result = await db.execute(select(User).where(User.id == competition.player2_id))
    player2 = player2_result.scalar_one_or_none()
    
    winner_result = None
    if competition.winner_id:
        winner_result = await db.execute(select(User).where(User.id == competition.winner_id))
    
    winner = winner_result.scalar_one_or_none() if winner_result else None
    
    # Get scores
    scores = await scoring_service.calculate_competition_scores(db, competition_id)
    
    # Get questions with answers
    from app.models.competition import Question, Answer
    from app.services.gameplay_service import gameplay_service
    
    questions_result = await db.execute(
        select(Question).where(Question.competition_id == competition_id)
        .order_by(Question.question_order)
    )
    questions = list(questions_result.scalars().all())
    
    question_details = []
    for question in questions:
        answers_result = await db.execute(
            select(Answer).where(Answer.question_id == question.id)
        )
        answers = list(answers_result.scalars().all())
        
        player1_answer = next((a for a in answers if a.user_id == competition.player1_id), None)
        player2_answer = next((a for a in answers if a.user_id == competition.player2_id), None)
        
        question_result = await gameplay_service.calculate_question_result(db, question.id)
        
        question_details.append({
            "question_id": question.id,
            "question_order": question.question_order,
            "question_text": question.question_text,
            "correct_answer": question.correct_answer,
            "player1_answer": player1_answer.answer_text if player1_answer else None,
            "player1_correct": bool(player1_answer.is_correct) if player1_answer else None,
            "player1_response_time": player1_answer.response_time if player1_answer else None,
            "player2_answer": player2_answer.answer_text if player2_answer else None,
            "player2_correct": bool(player2_answer.is_correct) if player2_answer else None,
            "player2_response_time": player2_answer.response_time if player2_answer else None,
            "winner": question_result["winner"]
        })
    
    return CompetitionDetailResponse(
        competition_id=competition.id,
        player1_id=competition.player1_id,
        player1_username=player1.username if player1 else "Unknown",
        player2_id=competition.player2_id,
        player2_username=player2.username if player2 else "Unknown",
        player1_score=scores["player1_total_score"],
        player2_score=scores["player2_total_score"],
        winner_id=competition.winner_id,
        winner_username=winner.username if winner else None,
        status=competition.status.value,
        created_at=competition.created_at,
        started_at=competition.started_at,
        completed_at=competition.completed_at,
        questions=question_details
    )


@router.get("/users/{user_id}/statistics", response_model=UserStatisticsResponse)
async def get_user_statistics(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed statistics for a user.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Calculate additional statistics
    win_rate = (user.wins / user.total_competitions * 100) if user.total_competitions > 0 else 0.0
    
    # Calculate ties
    from app.models.competition import CompetitionStatus
    ties_result = await db.execute(
        select(func.count(Competition.id)).where(
            and_(
                or_(
                    Competition.player1_id == user_id,
                    Competition.player2_id == user_id
                ),
                Competition.status == CompetitionStatus.COMPLETED,
                Competition.winner_id.is_(None)  # Tie
            )
        )
    )
    ties = ties_result.scalar() or 0
    
    # Calculate average score (simplified - could be enhanced)
    # Get all completed competitions where user participated
    competitions_result = await db.execute(
        select(Competition).where(
            and_(
                or_(
                    Competition.player1_id == user_id,
                    Competition.player2_id == user_id
                ),
                Competition.status == CompetitionStatus.COMPLETED
            )
        )
    )
    competitions = list(competitions_result.scalars().all())
    
    total_score = 0.0
    score_count = 0
    
    for comp in competitions:
        try:
            scores = await scoring_service.calculate_competition_scores(db, comp.id)
            if comp.player1_id == user_id:
                total_score += scores["player1_total_score"]
                score_count += 1
            elif comp.player2_id == user_id:
                total_score += scores["player2_total_score"]
                score_count += 1
        except:
            pass
    
    average_score = (total_score / score_count) if score_count > 0 else None
    
    return UserStatisticsResponse(
        user_id=user.id,
        username=user.username,
        rank=user.rank,
        total_competitions=user.total_competitions,
        wins=user.wins,
        losses=user.losses,
        ties=ties,
        win_rate=round(win_rate, 2),
        average_score=round(average_score, 2) if average_score else None,
        best_rank=None,  # Could be tracked separately
        current_streak=None  # Could be calculated from recent competitions
    )
