"""
Business logic services for the Quiz Game application.
"""
from app.services.matchmaking_service import MatchmakingService, matchmaking_service
from app.services.matchmaking_strategies import (
    MatchmakingStrategyInterface,
    RandomMatchmakingStrategy,
    RankBasedMatchmakingStrategy,
    MatchmakingStrategyFactory,
)
from app.services.ranking_service import RankingService
from app.services.question_service import QuestionService, question_service
from app.services.competition_service import CompetitionService, competition_service
from app.services.gameplay_service import GameplayService, gameplay_service
from app.services.scoring_service import ScoringService, scoring_service

__all__ = [
    "MatchmakingService",
    "matchmaking_service",
    "MatchmakingStrategyInterface",
    "RandomMatchmakingStrategy",
    "RankBasedMatchmakingStrategy",
    "MatchmakingStrategyFactory",
    "RankingService",
    "QuestionService",
    "question_service",
    "CompetitionService",
    "competition_service",
    "GameplayService",
    "gameplay_service",
    "ScoringService",
    "scoring_service",
]
