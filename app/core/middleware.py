"""
Middleware for authentication and rate limiting.
"""
from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, Token
from datetime import datetime, timezone
from app.config import settings


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token exists in database and is not expired
    result = await db.execute(
        select(Token).where(
            Token.token == token,
            Token.user_id == user_id,
            Token.expires_at > datetime.now(timezone.utc)
        )
    )
    token_obj = result.scalar_one_or_none()
    
    if not token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def check_rate_limit(
    request: Request,
    key_prefix: str = "rate_limit",
    limit: int = None
) -> bool:
    """
    Check if request is within rate limit.
    Returns True if allowed, False if rate limited.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return True
    
    if limit is None:
        limit = settings.RATE_LIMIT_PER_MINUTE
    
    try:
        from app.redis_managers import get_redis_manager
        redis_manager = await get_redis_manager()
        client_ip = request.client.host
        key = f"{key_prefix}:{client_ip}"
        
        current = await redis_manager.get(key)
        if current is None:
            await redis_manager.setex(key, 60, "1")
            return True
        
        current_count = int(current)
        if current_count >= limit:
            return False
        
        await redis_manager.incr(key)
        return True
    except Exception:
        # If Redis is unavailable, allow the request (fail open)
        return True
