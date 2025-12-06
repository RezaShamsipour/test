"""
Service for scoring and winner determination.
"""
from typing import Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.models.competition import Competition, Question, Answer, CompetitionStatus, QuestionState
from app.models.user import User
from app.models.user import User
from app.services.ranking_service import RankingService
import logging

logger = logging.getLogger(__name__)


class ScoringService:
    """Service for scoring operations."""
    
    @staticmethod
    async def calculate_question_score(
        db: AsyncSession,
        question_id: int,
        use_time_bonus: bool = False
    ) -> Dict:
        """
        Calculate score for a question.
        
        Args:
            db: Database session
            question_id: Question ID
            use_time_bonus: Whether to apply time-based bonus scoring
        
        Returns:
            Dict with scores for each player
        """
        result = await db.execute(select(Question).where(Question.id == question_id))
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
        
        player1_score = 0.0
        player2_score = 0.0
        player1_answer = None
        player2_answer = None
        
        for answer in answers:
            base_score = 1.0 if answer.is_correct else 0.0
            
            # Apply time bonus if enabled and answer is correct
            time_bonus = 0.0
            if use_time_bonus and answer.is_correct and answer.response_time:
                # Bonus: faster answers get more points (max 0.5 bonus)
                # Formula: bonus = 0.5 * (1 - response_time / time_limit)
                if answer.response_time < question.time_limit:
                    time_bonus = 0.5 * (1 - answer.response_time / question.time_limit)
            
            total_score = base_score + time_bonus
            
            if answer.user_id == competition.player1_id:
                player1_score = total_score
                player1_answer = answer
            elif answer.user_id == competition.player2_id:
                player2_score = total_score
                player2_answer = answer
        
        return {
            "question_id": question_id,
            "player1_score": player1_score,
            "player2_score": player2_score,
            "player1_answer": player1_answer,
            "player2_answer": player2_answer
        }
    
    @staticmethod
    async def calculate_competition_scores(
        db: AsyncSession,
        competition_id: int,
        use_time_bonus: bool = False
    ) -> Dict:
        """
        Calculate total scores for a competition.
        
        Returns:
            Dict with total scores and per-question breakdown
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        # Get all questions
        questions_result = await db.execute(
            select(Question).where(
                Question.competition_id == competition_id
            ).order_by(Question.question_order)
        )
        questions = list(questions_result.scalars().all())
        
        player1_total = 0.0
        player2_total = 0.0
        question_scores = []
        
        for question in questions:
            if question.state in [QuestionState.ANSWERED, QuestionState.EXPIRED]:
                score_data = await ScoringService.calculate_question_score(
                    db, question.id, use_time_bonus
                )
                player1_total += score_data["player1_score"]
                player2_total += score_data["player2_score"]
                
                question_scores.append({
                    "question_id": question.id,
                    "question_order": question.question_order,
                    "player1_score": score_data["player1_score"],
                    "player2_score": score_data["player2_score"]
                })
        
        return {
            "competition_id": competition_id,
            "player1_id": competition.player1_id,
            "player2_id": competition.player2_id,
            "player1_total_score": round(player1_total, 2),
            "player2_total_score": round(player2_total, 2),
            "question_scores": question_scores
        }
    
    @staticmethod
    async def determine_winner(
        db: AsyncSession,
        competition_id: int,
        use_time_bonus: bool = False
    ) -> Optional[int]:
        """
        Determine the winner of a competition.
        
        Returns:
            user_id of winner, or None if tie
        """
        scores = await ScoringService.calculate_competition_scores(
            db, competition_id, use_time_bonus
        )
        
        if scores["player1_total_score"] > scores["player2_total_score"]:
            return scores["player1_id"]
        elif scores["player2_total_score"] > scores["player1_total_score"]:
            return scores["player2_id"]
        else:
            # Tie - use tie-breaking logic
            return await ScoringService._break_tie(db, competition_id)
    
    @staticmethod
    async def _break_tie(
        db: AsyncSession,
        competition_id: int
    ) -> Optional[int]:
        """
        Break a tie using tie-breaking rules.
        Rules:
        1. Most correct answers
        2. Faster average response time
        3. First correct answer
        4. None (true tie)
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            return None
        
        # Get all questions
        questions_result = await db.execute(
            select(Question).where(Question.competition_id == competition_id)
        )
        questions = list(questions_result.scalars().all())
        
        player1_correct = 0
        player2_correct = 0
        player1_total_time = 0.0
        player2_total_time = 0.0
        player1_answer_count = 0
        player2_answer_count = 0
        player1_first_correct = None
        player2_first_correct = None
        
        for question in questions:
            answers_result = await db.execute(
                select(Answer).where(Answer.question_id == question.id)
            )
            answers = list(answers_result.scalars().all())
            
            for answer in answers:
                if answer.user_id == competition.player1_id:
                    player1_answer_count += 1
                    if answer.is_correct:
                        player1_correct += 1
                        if answer.response_time:
                            player1_total_time += answer.response_time
                        if player1_first_correct is None:
                            player1_first_correct = answer.submitted_at
                
                elif answer.user_id == competition.player2_id:
                    player2_answer_count += 1
                    if answer.is_correct:
                        player2_correct += 1
                        if answer.response_time:
                            player2_total_time += answer.response_time
                        if player2_first_correct is None:
                            player2_first_correct = answer.submitted_at
        
        # Rule 1: Most correct answers
        if player1_correct > player2_correct:
            return competition.player1_id
        elif player2_correct > player1_correct:
            return competition.player2_id
        
        # Rule 2: Faster average response time (only if both have answers)
        if player1_answer_count > 0 and player2_answer_count > 0:
            player1_avg_time = player1_total_time / player1_answer_count
            player2_avg_time = player2_total_time / player2_answer_count
            
            if player1_avg_time < player2_avg_time:
                return competition.player1_id
            elif player2_avg_time < player1_avg_time:
                return competition.player2_id
        
        # Rule 3: First correct answer
        if player1_first_correct and player2_first_correct:
            if player1_first_correct < player2_first_correct:
                return competition.player1_id
            elif player2_first_correct < player1_first_correct:
                return competition.player2_id
        
        # Rule 4: True tie
        return None
    
    @staticmethod
    async def update_ratings_after_competition(
        db: AsyncSession,
        competition_id: int
    ) -> Tuple[float, float]:
        """
        Update user ratings after competition completion.
        
        Returns:
            Tuple of (player1_new_rating, player2_new_rating)
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            raise ValueError("Competition not found")
        
        # Get user ratings
        player1_result = await db.execute(
            select(User).where(User.id == competition.player1_id)
        )
        player1 = player1_result.scalar_one_or_none()
        
        player2_result = await db.execute(
            select(User).where(User.id == competition.player2_id)
        )
        player2 = player2_result.scalar_one_or_none()
        
        if not player1 or not player2:
            raise ValueError("Users not found")
        
        # Determine score for rating calculation
        if competition.winner_id == competition.player1_id:
            # Player 1 wins
            score_a = 1.0
            score_b = 0.0
        elif competition.winner_id == competition.player2_id:
            # Player 2 wins
            score_a = 0.0
            score_b = 1.0
        else:
            # Tie
            score_a = 0.5
            score_b = 0.5
        
        # Update ratings
        new_rating1, new_rating2 = RankingService.update_ratings(
            player1.rank,
            player2.rank,
            score_a,
            score_b
        )
        
        # Update user ratings
        player1.rank = new_rating1
        player2.rank = new_rating2
        
        db.add(player1)
        db.add(player2)
        await db.commit()
        
        logger.info(
            f"Updated ratings for competition {competition_id}: "
            f"Player1: {player1.rank:.2f}, Player2: {player2.rank:.2f}"
        )
        
        return new_rating1, new_rating2
    
    @staticmethod
    async def update_user_statistics(
        db: AsyncSession,
        competition_id: int
    ):
        """
        Update user statistics (wins, losses, total competitions) after competition.
        """
        result = await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        
        if not competition or competition.status != CompetitionStatus.COMPLETED:
            return
        
        # Update player1 statistics
        player1_result = await db.execute(
            select(User).where(User.id == competition.player1_id)
        )
        player1 = player1_result.scalar_one_or_none()
        
        # Update player2 statistics
        player2_result = await db.execute(
            select(User).where(User.id == competition.player2_id)
        )
        player2 = player2_result.scalar_one_or_none()
        
        if player1:
            player1.total_competitions += 1
            if competition.winner_id == player1.id:
                player1.wins += 1
            elif competition.winner_id == player2.id if player2 else None:
                player1.losses += 1
            # If tie, neither wins nor loses
            db.add(player1)
        
        if player2:
            player2.total_competitions += 1
            if competition.winner_id == player2.id:
                player2.wins += 1
            elif competition.winner_id == player1.id:
                player2.losses += 1
            # If tie, neither wins nor loses
            db.add(player2)
        
        await db.commit()


# Global service instance
scoring_service = ScoringService()
