"""
Answer submission endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.models.user import User
from app.schemas.gameplay import AnswerSubmission, AnswerResponse
from app.services.gameplay_service import gameplay_service

router = APIRouter(prefix="/api/competitions", tags=["answers"])


@router.post("/{competition_id}/questions/{question_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    competition_id: int,
    question_id: int,
    answer_data: AnswerSubmission,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit an answer for a question in a competition.
    """
    try:
        answer, is_valid = await gameplay_service.submit_answer(
            db,
            competition_id,
            question_id,
            current_user.id,
            answer_data.answer_text,
            answer_data.client_timestamp
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer submission failed"
            )
        
        return AnswerResponse(
            answer_id=answer.id,
            question_id=answer.question_id,
            is_correct=bool(answer.is_correct),
            correct_answer="",  # Don't reveal answer until question is complete
            response_time=answer.response_time,
            submitted_at=answer.submitted_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
