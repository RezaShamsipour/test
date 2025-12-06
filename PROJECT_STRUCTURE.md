# Project Structure

This document describes the organization of the Quiz Game application codebase.

## Directory Structure

```
app/
├── api/              # API routes and endpoints
│   ├── __init__.py
│   ├── auth.py       # Authentication endpoints
│   ├── users.py      # User management endpoints
│   ├── matchmaking.py # Matchmaking endpoints
│   └── competitions.py # Competition endpoints
│
├── core/             # Core utilities and infrastructure
│   ├── __init__.py
│   ├── database.py   # Database configuration and session management
│   ├── security.py   # Password hashing, JWT tokens
│   ├── middleware.py # Authentication middleware, rate limiting
│   ├── logging.py    # Logging configuration
│   └── exceptions.py # Custom exception classes
│
├── models/           # Database models (SQLAlchemy)
│   ├── __init__.py
│   ├── user.py      # User and Token models
│   ├── competition.py # Competition, Question, Answer models
│   └── matchmaking.py # MatchmakingQueue model
│
├── redis_managers/   # Redis connection and operations
│   ├── __init__.py
│   └── redis_manager.py # Redis client management
│
├── schemas/          # Pydantic schemas for validation
│   ├── auth.py       # Authentication schemas
│   ├── user.py       # User schemas
│   └── matchmaking.py # Matchmaking schemas
│
├── services/         # Business logic services
│   ├── __init__.py
│   ├── matchmaking_service.py # Matchmaking queue operations
│   ├── matchmaking_strategies.py # Matchmaking algorithms
│   └── ranking_service.py # Ranking/rating calculations
│
├── tests/            # Test files
│   ├── __init__.py
│   └── conftest.py   # Pytest configuration and fixtures
│
├── workers/          # Background workers and tasks
│   ├── __init__.py
│   └── matchmaking_worker.py # Matchmaking queue processor
│
├── config.py         # Application configuration
├── main.py           # FastAPI application entry point
└── __init__.py

alembic/              # Database migrations
├── env.py
├── script.py.mako
└── versions/         # Migration files
```

## Directory Responsibilities

### `api/`
Contains all FastAPI route handlers and endpoints. Each file represents a domain area:
- **auth.py**: User registration, login, logout, token refresh
- **users.py**: User profile management, statistics
- **matchmaking.py**: Queue join/leave, status checking
- **competitions.py**: Competition management, confirmation, rejection

### `core/`
Core infrastructure and utilities used across the application:
- **database.py**: SQLAlchemy setup, session management
- **security.py**: Password hashing, JWT token operations
- **middleware.py**: Authentication dependencies, rate limiting
- **logging.py**: Logging configuration
- **exceptions.py**: Custom exception classes

### `models/`
SQLAlchemy database models representing database tables:
- **user.py**: User and Token models
- **competition.py**: Competition, Question, Answer models
- **matchmaking.py**: MatchmakingQueue model

### `redis_managers/`
Redis connection and operation management:
- **redis_manager.py**: Redis client singleton, connection management, basic operations

### `schemas/`
Pydantic schemas for request/response validation:
- **auth.py**: Authentication request/response schemas
- **user.py**: User-related schemas
- **matchmaking.py**: Matchmaking request/response schemas

### `services/`
Business logic services that contain the core application logic:
- **matchmaking_service.py**: Matchmaking queue operations, match creation
- **matchmaking_strategies.py**: Matchmaking algorithm implementations (random, rank-based)
- **ranking_service.py**: ELO rating calculations

### `tests/`
Test files and test configuration:
- **conftest.py**: Pytest fixtures and configuration

### `workers/`
Background workers for asynchronous tasks:
- **matchmaking_worker.py**: Periodic matchmaking queue processing

## Import Patterns

### From API to Services
```python
from app.services.matchmaking_service import matchmaking_service
from app.services.ranking_service import RankingService
```

### From API to Core
```python
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.core.security import hash_password
```

### From Services to Models
```python
from app.models.user import User
from app.models.competition import Competition
```

### From Services to Redis
```python
from app.redis_managers import get_redis_manager
```

### From Workers to Services
```python
from app.services.matchmaking_service import matchmaking_service
```

## Best Practices

1. **API Layer**: Should only handle HTTP requests/responses and delegate to services
2. **Services Layer**: Contains all business logic, should not depend on FastAPI
3. **Models Layer**: Pure SQLAlchemy models, no business logic
4. **Core Layer**: Infrastructure utilities, reusable across the application
5. **Workers**: Background tasks that run independently of HTTP requests
