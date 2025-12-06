"""
WebSocket endpoints for real-time gameplay.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Dict, Set, Optional
import json
import asyncio
import logging
from datetime import datetime, timezone
from app.core.database import get_db, AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User
from app.models.competition import Competition, CompetitionStatus, Question, QuestionState
from app.services.gameplay_service import gameplay_service
from app.services.competition_service import competition_service

logger = logging.getLogger(__name__)

router = APIRouter()

# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        # Map of user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        # Map of competition_id -> Set[user_id]
        self.competition_connections: Dict[int, Set[int]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Connect a user."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected via WebSocket")
    
    def disconnect(self, user_id: int):
        """Disconnect a user."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        # Remove from competition connections
        for comp_id, users in self.competition_connections.items():
            users.discard(user_id)
        
        logger.info(f"User {user_id} disconnected from WebSocket")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send message to a specific user."""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
    
    async def send_to_competition(self, message: dict, competition_id: int):
        """Send message to all users in a competition."""
        if competition_id in self.competition_connections:
            for user_id in self.competition_connections[competition_id].copy():
                await self.send_personal_message(message, user_id)
    
    def add_to_competition(self, user_id: int, competition_id: int):
        """Add user to competition connections."""
        if competition_id not in self.competition_connections:
            self.competition_connections[competition_id] = set()
        self.competition_connections[competition_id].add(user_id)


manager = ConnectionManager()


async def get_user_from_token(token: str) -> Optional[User]:
    """Get user from JWT token."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


@router.websocket("/ws/gameplay/{competition_id}")
async def gameplay_websocket(websocket: WebSocket, competition_id: int):
    """
    WebSocket endpoint for real-time gameplay.
    """
    # Get token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Authenticate user
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Verify user is part of competition
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Competition).where(
                and_(
                    Competition.id == competition_id,
                    or_(
                        Competition.player1_id == user.id,
                        Competition.player2_id == user.id
                    )
                )
            )
        )
        competition = result.scalar_one_or_none()
        
        if not competition:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    
    # Connect
    await manager.connect(websocket, user.id)
    manager.add_to_competition(user.id, competition_id)
    
    # Send initial state
    try:
        progress = await gameplay_service.get_competition_progress(
            AsyncSessionLocal(), competition_id
        )
        await manager.send_personal_message({
            "type": "competition_progress",
            "data": progress
        }, user.id)
        
        # Send current question if active
        current_question = await gameplay_service.get_current_question(
            AsyncSessionLocal(), competition_id
        )
        if current_question and current_question.state == QuestionState.ACTIVE:
            timer_info = await gameplay_service.get_question_timer(
                AsyncSessionLocal(), current_question.id
            )
            await manager.send_personal_message({
                "type": "question_active",
                "data": {
                    "question_id": current_question.id,
                    "question_text": current_question.question_text,
                    "question_order": current_question.question_order,
                    "time_limit": current_question.time_limit,
                    "timer": timer_info
                }
            }, user.id)
    
    except Exception as e:
        logger.error(f"Error sending initial state: {e}")
    
    # Heartbeat task
    async def heartbeat():
        while True:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                await manager.send_personal_message({
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, user.id)
            except Exception:
                break
    
    heartbeat_task = asyncio.create_task(heartbeat())
    
    try:
        while True:
            # Receive messages
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            if message_type == "ping":
                await manager.send_personal_message({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, user.id)
            
            elif message_type == "get_timer":
                question_id = data.get("question_id")
                if question_id:
                    async with AsyncSessionLocal() as db:
                        timer_info = await gameplay_service.get_question_timer(db, question_id)
                        if timer_info:
                            await manager.send_personal_message({
                                "type": "timer_update",
                                "data": timer_info
                            }, user.id)
            
            elif message_type == "get_progress":
                async with AsyncSessionLocal() as db:
                    progress = await gameplay_service.get_competition_progress(db, competition_id)
                    await manager.send_personal_message({
                        "type": "competition_progress",
                        "data": progress
                    }, user.id)
    
    except WebSocketDisconnect:
        manager.disconnect(user.id)
        heartbeat_task.cancel()
        logger.info(f"User {user.id} disconnected from competition {competition_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user.id}: {e}")
        manager.disconnect(user.id)
        heartbeat_task.cancel()


# Background task to send timer updates
async def broadcast_timer_updates():
    """Periodically broadcast timer updates for active questions."""
    while True:
        try:
            await asyncio.sleep(1)  # Update every second
            
            async with AsyncSessionLocal() as db:
                # Find all active questions
                result = await db.execute(
                    select(Question).where(Question.state == QuestionState.ACTIVE)
                )
                active_questions = result.scalars().all()
                
                for question in active_questions:
                    timer_info = await gameplay_service.get_question_timer(db, question.id)
                    
                    if timer_info:
                        # Send to all users in the competition
                        await manager.send_to_competition({
                            "type": "timer_update",
                            "data": timer_info
                        }, question.competition_id)
                        
                        # Check if expired
                        if timer_info["remaining_seconds"] <= 0:
                            await gameplay_service.expire_question(db, question.id)
                            
                            # Notify users
                            await manager.send_to_competition({
                                "type": "question_expired",
                                "data": {"question_id": question.id}
                            }, question.competition_id)
                            
                            # Calculate result and move to next question
                            result_data = await gameplay_service.calculate_question_result(
                                db, question.id
                            )
                            await manager.send_to_competition({
                                "type": "question_result",
                                "data": result_data
                            }, question.competition_id)
                            
                            # Move to next question
                            next_question = await gameplay_service.move_to_next_question(
                                db, question.competition_id
                            )
                            
                            if next_question:
                                timer_info = await gameplay_service.get_question_timer(
                                    db, next_question.id
                                )
                                await manager.send_to_competition({
                                    "type": "question_active",
                                    "data": {
                                        "question_id": next_question.id,
                                        "question_text": next_question.question_text,
                                        "question_order": next_question.question_order,
                                        "time_limit": next_question.time_limit,
                                        "timer": timer_info
                                    }
                                }, question.competition_id)
                            else:
                                # Competition completed - send final scores and winner
                                from app.services.scoring_service import scoring_service
                                scores = await scoring_service.calculate_competition_scores(
                                    db, question.competition_id
                                )
                                
                                comp_result = await db.execute(
                                    select(Competition).where(Competition.id == question.competition_id)
                                )
                                comp = comp_result.scalar_one_or_none()
                                
                                await manager.send_to_competition({
                                    "type": "competition_completed",
                                    "data": {
                                        "competition_id": question.competition_id,
                                        "player1_score": scores["player1_total_score"],
                                        "player2_score": scores["player2_total_score"],
                                        "winner_id": comp.winner_id if comp else None
                                    }
                                }, question.competition_id)
        
        except Exception as e:
            logger.error(f"Error in timer update broadcast: {e}")
            await asyncio.sleep(5)


# Timer broadcast task will be started when module is imported
_timer_task: Optional[asyncio.Task] = None

def start_timer_broadcast():
    """Start the timer broadcast task."""
    global _timer_task
    if _timer_task is None or _timer_task.done():
        _timer_task = asyncio.create_task(broadcast_timer_updates())
        logger.info("Timer broadcast task started")
