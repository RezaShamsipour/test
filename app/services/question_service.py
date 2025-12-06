"""
Service for question bank and question selection operations.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from app.models.question_bank import QuestionBank, QuestionDifficulty, QuestionCategory
from app.models.competition import Question, Competition
from app.config import settings
import random
import logging

logger = logging.getLogger(__name__)


class QuestionService:
    """Service for question operations."""
    
    @staticmethod
    async def create_question(
        db: AsyncSession,
        question_data: dict
    ) -> QuestionBank:
        """Create a new question in the bank."""
        question = QuestionBank(**question_data)
        db.add(question)
        await db.commit()
        await db.refresh(question)
        return question
    
    @staticmethod
    async def get_question(
        db: AsyncSession,
        question_id: int
    ) -> Optional[QuestionBank]:
        """Get a question by ID."""
        result = await db.execute(
            select(QuestionBank).where(QuestionBank.id == question_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_questions(
        db: AsyncSession,
        category: Optional[QuestionCategory] = None,
        difficulty: Optional[QuestionDifficulty] = None,
        is_active: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[QuestionBank]:
        """Get questions with filters."""
        query = select(QuestionBank)
        
        conditions = []
        if category:
            conditions.append(QuestionBank.category == category)
        if difficulty:
            conditions.append(QuestionBank.difficulty == difficulty)
        if is_active is not None:
            conditions.append(QuestionBank.is_active == is_active)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(QuestionBank.created_at.desc()).limit(limit).offset(offset)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def select_questions_for_competition(
        db: AsyncSession,
        competition_id: int,
        count: int = None,
        category: Optional[QuestionCategory] = None,
        difficulty: Optional[QuestionDifficulty] = None,
        strategy: str = "random"
    ) -> List[Question]:
        """
        Select questions for a competition based on strategy.
        
        Args:
            db: Database session
            competition_id: Competition ID
            count: Number of questions to select (default: settings.DEFAULT_QUESTIONS_PER_COMPETITION)
            category: Optional category filter
            difficulty: Optional difficulty filter
            strategy: Selection strategy ("random", "difficulty", "category")
        
        Returns:
            List of Question objects
        """
        if count is None:
            count = settings.DEFAULT_QUESTIONS_PER_COMPETITION
        
        # Ensure odd number
        if count % 2 == 0:
            count += 1
        
        # Get available questions from bank
        query = select(QuestionBank).where(QuestionBank.is_active == 1)
        
        conditions = []
        if category:
            conditions.append(QuestionBank.category == category)
        if difficulty:
            conditions.append(QuestionBank.difficulty == difficulty)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await db.execute(query)
        available_questions = list(result.scalars().all())
        
        if len(available_questions) < count:
            logger.warning(f"Only {len(available_questions)} questions available, requested {count}")
            count = len(available_questions)
            if count % 2 == 0 and count > 0:
                count -= 1
        
        # Select questions based on strategy
        selected_questions = []
        
        if strategy == "random":
            selected_questions = random.sample(available_questions, min(count, len(available_questions)))
        elif strategy == "difficulty":
            # Group by difficulty and select evenly
            easy = [q for q in available_questions if q.difficulty == QuestionDifficulty.EASY]
            medium = [q for q in available_questions if q.difficulty == QuestionDifficulty.MEDIUM]
            hard = [q for q in available_questions if q.difficulty == QuestionDifficulty.HARD]
            
            per_difficulty = count // 3
            remainder = count % 3
            
            selected_questions.extend(random.sample(easy, min(per_difficulty + (1 if remainder > 0 else 0), len(easy))))
            selected_questions.extend(random.sample(medium, min(per_difficulty + (1 if remainder > 1 else 0), len(medium))))
            selected_questions.extend(random.sample(hard, min(per_difficulty, len(hard))))
            
            # Fill remaining slots randomly
            remaining = count - len(selected_questions)
            if remaining > 0:
                all_questions = [q for q in available_questions if q not in selected_questions]
                selected_questions.extend(random.sample(all_questions, min(remaining, len(all_questions))))
        elif strategy == "category":
            # Group by category and select evenly
            categories = {}
            for q in available_questions:
                if q.category not in categories:
                    categories[q.category] = []
                categories[q.category].append(q)
            
            per_category = count // len(categories) if categories else 0
            remainder = count % len(categories) if categories else 0
            
            for i, (cat, questions) in enumerate(categories.items()):
                take = per_category + (1 if i < remainder else 0)
                selected_questions.extend(random.sample(questions, min(take, len(questions))))
        
        # Shuffle to randomize order
        random.shuffle(selected_questions)
        
        # Create Question objects for competition
        competition_questions = []
        for idx, bank_question in enumerate(selected_questions[:count], start=1):
            # Generate random time limit between min and max
            time_limit = random.randint(
                settings.MIN_QUESTION_TIME_LIMIT,
                settings.MAX_QUESTION_TIME_LIMIT
            )
            
            question = Question(
                competition_id=competition_id,
                question_text=bank_question.question_text,
                correct_answer=bank_question.correct_answer,
                time_limit=time_limit,
                question_order=idx
            )
            db.add(question)
            competition_questions.append(question)
            
            # Update usage count
            bank_question.usage_count += 1
            db.add(bank_question)
        
        await db.commit()
        
        # Refresh all questions
        for q in competition_questions:
            await db.refresh(q)
        
        logger.info(f"Selected {len(competition_questions)} questions for competition {competition_id}")
        
        return competition_questions
    
    @staticmethod
    async def validate_question(question_data: dict) -> tuple[bool, Optional[str]]:
        """
        Validate question data.
        Returns (is_valid, error_message).
        """
        if not question_data.get("question_text") or len(question_data["question_text"].strip()) < 10:
            return False, "Question text must be at least 10 characters"
        
        if not question_data.get("correct_answer") or len(question_data["correct_answer"].strip()) < 1:
            return False, "Correct answer is required"
        
        if len(question_data.get("question_text", "")) > 1000:
            return False, "Question text must be less than 1000 characters"
        
        if len(question_data.get("correct_answer", "")) > 500:
            return False, "Correct answer must be less than 500 characters"
        
        return True, None
    
    @staticmethod
    async def bulk_create_questions(
        db: AsyncSession,
        questions_data: List[dict]
    ) -> List[QuestionBank]:
        """Bulk create questions."""
        created_questions = []
        
        for q_data in questions_data:
            is_valid, error = await QuestionService.validate_question(q_data)
            if not is_valid:
                logger.warning(f"Skipping invalid question: {error}")
                continue
            
            question = QuestionBank(**q_data)
            db.add(question)
            created_questions.append(question)
        
        await db.commit()
        
        for q in created_questions:
            await db.refresh(q)
        
        logger.info(f"Created {len(created_questions)} questions in bulk")
        
        return created_questions


# Global service instance
question_service = QuestionService()
