"""
Ranking and rating system service.
"""
from typing import Tuple
from app.config import settings


# ELO-like rating system constants
INITIAL_RATING = 1000.0
K_FACTOR = 32  # Standard K-factor for ELO rating system


class RankingService:
    """Service for ranking and rating calculations."""
    
    @staticmethod
    def calculate_expected_score(rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score for player A against player B.
        Returns a value between 0 and 1.
        """
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    @staticmethod
    def update_ratings(
        rating_a: float,
        rating_b: float,
        score_a: float,  # 1.0 for win, 0.5 for draw, 0.0 for loss
        score_b: float = None
    ) -> Tuple[float, float]:
        """
        Update ELO ratings for two players based on match result.
        
        Args:
            rating_a: Current rating of player A
            rating_b: Current rating of player B
            score_a: Score for player A (1.0 = win, 0.5 = draw, 0.0 = loss)
            score_b: Score for player B (optional, calculated if not provided)
        
        Returns:
            Tuple of (new_rating_a, new_rating_b)
        """
        if score_b is None:
            score_b = 1.0 - score_a
        
        expected_a = RankingService.calculate_expected_score(rating_a, rating_b)
        expected_b = RankingService.calculate_expected_score(rating_b, rating_a)
        
        new_rating_a = rating_a + K_FACTOR * (score_a - expected_a)
        new_rating_b = rating_b + K_FACTOR * (score_b - expected_b)
        
        return new_rating_a, new_rating_b
    
    @staticmethod
    def initialize_user_rating() -> float:
        """
        Initialize a new user's rating.
        """
        return INITIAL_RATING
    
    @staticmethod
    def update_user_rating_after_competition(
        winner_rating: float,
        loser_rating: float
    ) -> Tuple[float, float]:
        """
        Update ratings after a competition where there's a clear winner.
        """
        return RankingService.update_ratings(winner_rating, loser_rating, 1.0, 0.0)
    
    @staticmethod
    def update_user_rating_after_draw(
        rating_a: float,
        rating_b: float
    ) -> Tuple[float, float]:
        """
        Update ratings after a draw (tie).
        """
        return RankingService.update_ratings(rating_a, rating_b, 0.5, 0.5)
