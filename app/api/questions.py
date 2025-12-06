"""
Question bank management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.schemas.question import (
    QuestionBankCreate,
    QuestionBankUpdate,
    QuestionBankResponse,
    QuestionBankBulkCreate,
)
from app.models.user import User
from app.models.question_bank import QuestionBank, QuestionDifficulty, QuestionCategory
from app.services.question_service import question_service

router = APIRouter(prefix="/api/questions", tags=["questions"])


@router.post("", response_model=QuestionBankResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    question_data: QuestionBankCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new question in the bank.
    Note: In production, this should be admin-only.
    """
    # Validate question
    is_valid, error = await question_service.validate_question(question_data.dict())
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error
        )
    
    question = await question_service.create_question(db, question_data.dict())
    return question


@router.get("", response_model=List[QuestionBankResponse])
async def get_questions(
    category: Optional[QuestionCategory] = Query(None, description="Filter by category"),
    difficulty: Optional[QuestionDifficulty] = Query(None, description="Filter by difficulty"),
    is_active: Optional[int] = Query(None, description="Filter by active status (0 or 1)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of questions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get questions from the bank with optional filters.
    """
    questions = await question_service.get_questions(
        db, category=category, difficulty=difficulty, is_active=is_active, limit=limit, offset=offset
    )
    return questions


@router.get("/{question_id}", response_model=QuestionBankResponse)
async def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific question by ID.
    """
    question = await question_service.get_question(db, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    return question


@router.put("/{question_id}", response_model=QuestionBankResponse)
async def update_question(
    question_id: int,
    question_update: QuestionBankUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a question in the bank.
    Note: In production, this should be admin-only.
    """
    question = await question_service.get_question(db, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    update_data = question_update.dict(exclude_unset=True)
    
    # Validate if question_text or correct_answer is being updated
    if "question_text" in update_data or "correct_answer" in update_data:
        validation_data = {
            "question_text": update_data.get("question_text", question.question_text),
            "correct_answer": update_data.get("correct_answer", question.correct_answer)
        }
        is_valid, error = await question_service.validate_question(validation_data)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error
            )
    
    for key, value in update_data.items():
        setattr(question, key, value)
    
    db.add(question)
    await db.commit()
    await db.refresh(question)
    
    return question


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete (deactivate) a question from the bank.
    Note: In production, this should be admin-only.
    """
    question = await question_service.get_question(db, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Soft delete by setting is_active to 0
    question.is_active = 0
    db.add(question)
    await db.commit()
    
    return None


@router.post("/bulk", response_model=List[QuestionBankResponse], status_code=status.HTTP_201_CREATED)
async def bulk_create_questions(
    bulk_data: QuestionBankBulkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk create questions in the bank.
    Note: In production, this should be admin-only.
    """
    questions_data = [q.dict() for q in bulk_data.questions]
    created_questions = await question_service.bulk_create_questions(db, questions_data)
    
    if not created_questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No valid questions to create"
        )
    
    return created_questions
