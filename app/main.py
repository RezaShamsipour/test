"""
Main FastAPI application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.core.logging import setup_logging
from app.core.database import init_db, close_db
from app.workers.matchmaking_worker import start_matchmaking_worker
from app.workers.competition_worker import start_competition_worker
from app.api.websocket import start_timer_broadcast
from app.api import auth, users, matchmaking, competitions, questions, answers, websocket, scoring

# Setup logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    # Start background workers
    await start_matchmaking_worker()
    await start_competition_worker()
    # Start WebSocket timer broadcast
    start_timer_broadcast()
    yield
    # Shutdown
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(matchmaking.router)
app.include_router(competitions.router)
app.include_router(questions.router)
app.include_router(answers.router)
app.include_router(websocket.router)
app.include_router(scoring.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Quiz Game API",
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
