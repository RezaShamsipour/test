"""
Service for gameplay operations including timing, answer submission, and question flow.
"""
from typing import Optional, Tuple, Dict
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.models.competition import Competition, Question, Answer, CompetitionStatus, QuestionState
from app.models.user import User
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class GameplayService:
    """Service for gameplay operations."""
    
    @staticmethod
    async def activate_question(
        db: AsyncSession,
        competition_id: int,
        question_order: int
    ) -> Question:
        """
        Activate a question (start timer).
        """
        result = await db.execute(
            select(Question).where(
                and_(
                    Question.competition_id == competition_id,
                    Question.question_order == question_order
                )
            )
        )
        question = result.scalar_one_or_none()
        
        if not question:
            raise ValueError(f"Question {question_order} not found for competition {competition_id}")
        
        if question.state != QuestionState.PENDING:
            raise ValueError(f"Question is already {question.state}")
        
        # Set question as active
        question.state = QuestionState.ACTIVE
        question.started_at = datetime.now(timezone.utc)
        question.expires_at = question.started_at + timedelta(seconds=question.time_limit)
        
        # Update competition current question
        comp_result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = comp_result.scalar_one_or_none()
        if competition:
            competition.current_question_order = question_order
            db.add(competition)
        
        db.add(question)
        await db.commit()
        await db.refresh(question)
        
        logger.info(f"Activated question {question.id} (order {question_order}) for competition {competition_id}")
        
        return question
    
    @staticmethod
    async def submit_answer(
        db: AsyncSession,
        competition_id: int,
        question_id: int,
        user_id: int,
        answer_text: str,
        client_timestamp: Optional[float] = None
    ) -> Tuple[Answer, bool]:
        """
        Submit an answer for a question.
        Returns (answer_object, is_valid).
        """
        # Get question
        result = await db.execute(
            select(Question).where(
                and_(
                    Question.id == question_id,
                    Question.competition_id == competition_id
                )
            )
        )
        question = result.scalar_one_or_none()
        
        if not question:
            raise ValueError("Question not found")
        
        # Check if question is active
        if question.state != QuestionState.ACTIVE:
            raise ValueError(f"Question is not active (state: {question.state})")
        
        # Check if already answered
        existing_result = await db.execute(
            select(Answer).where(
                and_(
                    Answer.question_id == question_id,
                    Answer.user_id == user_id
                )
            )
        )
        existing_answer = existing_result.scalar_one_or_none()
        
        if existing_answer:
            raise ValueError("Answer already submitted for this question")
        
        # Validate time limit (server-side)
        now = datetime.now(timezone.utc)
        if question.expires_at and now > question.expires_at:
            # Question expired, mark as expired
            question.state = QuestionState.EXPIRED
            db.add(question)
            await db.commit()
            raise ValueError("Question time limit expired")
        
        # Calculate response time
        if question.started_at:
            response_time = (now - question.started_at).total_seconds()
        else:
            response_time = None
        
        # Check correctness
        is_correct = answer_text.strip().lower() == question.correct_answer.strip().lower()
        
        # Create answer
        answer = Answer(
            question_id=question_id,
            user_id=user_id,
            answer_text=answer_text,
            is_correct=1 if is_correct else 0,
            response_time=response_time
        )
        
        db.add(answer)
        
        # Check if both players have answered
        answers_result = await db.execute(
            select(Answer).where(Answer.question_id == question_id)
        )
        answers = list(answers_result.scalars().all())
        
        if len(answers) >= 2:  # Both players answered
            question.state = QuestionState.ANSWERED
        # If only one answered, keep it active until timeout or second answer
        
        db.add(question)
        await db.commit()
        await db.refresh(answer)
        
        logger.info(f"Answer submitted for question {question_id} by user {user_id}, correct: {is_correct}")
        
        return answer, True
    
    @staticmethod
    async def expire_question(
        db: AsyncSession,
        question_id: int
    ) -> Question:
        """
        Mark a question as expired.
        """
        result = await db.execute(select(Question).where(Question.id == question_id))
        question = result.scalar_one_or_none()
        
        if not question:
            raise ValueError("Question not found")
        
        if question.state == QuestionState.ACTIVE:
            question.state = QuestionState.EXPIRED
            db.add(question)
            await db.commit()
            await db.refresh(question)
        
        return question
    
    @staticmethod
    async def get_current_question(
        db: AsyncSession,
        competition_id: int
    ) -> Optional[Question]:
        """
        Get the current active question for a competition.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            return None
        
        if competition.current_question_order == 0:
            return None
        
        question_result = await db.execute(
            select(Question).where(
                and_(
                    Question.competition_id == competition_id,
                    Question.question_order == competition.current_question_order
                )
            )
        )
        return question_result.scalar_one_or_none()
    
    @staticmethod
    async def get_question_timer(
        db: AsyncSession,
        question_id: int
    ) -> Optional[Dict]:
        """
        Get timer information for a question.
        """
        result = await db.execute(select(Question).where(Question.id == question_id))
        question = result.scalar_one_or_none()
        
        if not question or not question.started_at or not question.expires_at:
            return None
        
        now = datetime.now(timezone.utc)
        remaining = (question.expires_at - now).total_seconds()
        remaining = max(0, int(remaining))
        
        return {
            "question_id": question.id,
            "time_limit": question.time_limit,
            "started_at": question.started_at,
            "expires_at": question.expires_at,
            "remaining_seconds": remaining
        }
    
    @staticmethod
    async def calculate_question_result(
        db: AsyncSession,
        question_id: int
    ) -> Dict:
        """
        Calculate result for a question (who won, scores, etc.).
        """
        result = await db.execute(
            select(Question).where(Question.id == question_id)
        )
        question = result.scalar_one_or_none()
        
        if not question:
            raise ValueError("Question not found")
        
        # Get competition
        comp_result = await db.execute(
            select(Competition).where(Competition.id == question.competition_id)
        )
        competition = comp_result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        # Get answers
        answers_result = await db.execute(
            select(Answer).where(Answer.question_id == question_id)
        )
        answers = list(answers_result.scalars().all())
        
        player1_answer = None
        player1_correct = None
        player2_answer = None
        player2_correct = None
        
        for answer in answers:
            if answer.user_id == competition.player1_id:
                player1_answer = answer.answer_text
                player1_correct = bool(answer.is_correct)
            elif answer.user_id == competition.player2_id:
                player2_answer = answer.answer_text
                player2_correct = bool(answer.is_correct)
        
        # Determine winner (first correct answer wins, or faster if both correct)
        winner = None
        if player1_correct and not player2_correct:
            winner = competition.player1_id
        elif player2_correct and not player1_correct:
            winner = competition.player2_id
        elif player1_correct and player2_correct:
            # Both correct, faster answer wins
            player1_answer_obj = next((a for a in answers if a.user_id == competition.player1_id), None)
            player2_answer_obj = next((a for a in answers if a.user_id == competition.player2_id), None)
            
            if player1_answer_obj and player2_answer_obj:
                if player1_answer_obj.response_time and player2_answer_obj.response_time:
                    if player1_answer_obj.response_time < player2_answer_obj.response_time:
                        winner = competition.player1_id
                    elif player2_answer_obj.response_time < player1_answer_obj.response_time:
                        winner = competition.player2_id
                    # If equal, it's a tie (winner = None)
        
        return {
            "question_id": question.id,
            "question_order": question.question_order,
            "player1_answer": player1_answer,
            "player1_correct": player1_correct,
            "player2_answer": player2_answer,
            "player2_correct": player2_correct,
            "winner": winner,
            "correct_answer": question.correct_answer
        }
    
    @staticmethod
    async def get_competition_progress(
        db: AsyncSession,
        competition_id: int
    ) -> Dict:
        """
        Get current progress of a competition.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        # Get total questions
        questions_result = await db.execute(
            select(func.count(Question.id)).where(Question.competition_id == competition_id)
        )
        total_questions = questions_result.scalar() or 0
        
        # Calculate scores
        player1_score = 0
        player2_score = 0
        
        questions_result = await db.execute(
            select(Question).where(Question.competition_id == competition_id)
        )
        questions = list(questions_result.scalars().all())
        
        for question in questions:
            if question.state == QuestionState.ANSWERED:
                result_data = await GameplayService.calculate_question_result(db, question.id)
                if result_data["winner"] == competition.player1_id:
                    player1_score += 1
                elif result_data["winner"] == competition.player2_id:
                    player2_score += 1
        
        return {
            "competition_id": competition.id,
            "current_question_order": competition.current_question_order,
            "total_questions": total_questions,
            "player1_score": player1_score,
            "player2_score": player2_score,
            "status": competition.status.value
        }
    
    @staticmethod
    async def move_to_next_question(
        db: AsyncSession,
        competition_id: int
    ) -> Optional[Question]:
        """
        Move to the next question in the competition.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        next_order = competition.current_question_order + 1
        
        # Check if there's a next question
        next_question_result = await db.execute(
            select(Question).where(
                and_(
                    Question.competition_id == competition_id,
                    Question.question_order == next_order
                )
            )
        )
        next_question = next_question_result.scalar_one_or_none()
        
        if next_question:
            return await GameplayService.activate_question(db, competition_id, next_order)
        
        # No more questions, complete competition
        await gameplay_service.complete_competition(db, competition_id)
        return None
    
    @staticmethod
    async def complete_competition(
        db: AsyncSession,
        competition_id: int
    ) -> Competition:
        """
        Complete a competition and determine winner.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        # Calculate final scores
        progress = await GameplayService.get_competition_progress(db, competition_id)
        
        # Determine winner
        winner_id = None
        if progress["player1_score"] > progress["player2_score"]:
            winner_id = competition.player1_id
        elif progress["player2_score"] > progress["player1_score"]:
            winner_id = competition.player2_id
        # If equal, winner_id remains None (tie)
        
        # Use scoring service to determine winner properly
        from app.services.scoring_service import scoring_service
        
        winner_id = await scoring_service.determine_winner(db, competition_id, use_time_bonus=False)
        
        competition.status = CompetitionStatus.COMPLETED
        competition.completed_at = datetime.now(timezone.utc)
        competition.winner_id = winner_id
        
        db.add(competition)
        await db.commit()
        await db.refresh(competition)
        
        # Update ratings and statistics
        try:
            await scoring_service.update_ratings_after_competition(db, competition_id)
            await scoring_service.update_user_statistics(db, competition_id)
        except Exception as e:
            logger.error(f"Error updating ratings/statistics: {e}")
        
        logger.info(f"Completed competition {competition_id}, winner: {winner_id}")
        
        return competition


# Global service instance
gameplay_service = GameplayService()
