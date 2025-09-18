"""Rate limiting service using Redis."""

import time
from typing import Optional
import redis.asyncio as redis
import structlog

from app.config import settings
from app.exceptions import RateLimitError

logger = structlog.get_logger()


class RateLimiter:
    """Redis-based rate limiter."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = settings.enable_rate_limiting
        self.requests_per_minute = settings.rate_limit_requests_per_minute
        
        if self.enabled:
            try:
                self.redis_client = redis.from_url(settings.redis_url)
            except Exception as e:
                logger.warning("Failed to connect to Redis, rate limiting disabled", error=str(e))
                self.enabled = False
    
    async def check_rate_limit(self, client_id: str, endpoint: str) -> None:
        """Check if client has exceeded rate limit for endpoint."""
        if not self.enabled or not self.redis_client:
            return
        
        try:
            # Create key for this client and endpoint
            key = f"rate_limit:{client_id}:{endpoint}"
            current_time = int(time.time())
            window_start = current_time - 60  # 1 minute window
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in the window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, 60)
            
            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]  # Count result
            
            if current_count >= self.requests_per_minute:
                logger.warning(
                    "Rate limit exceeded",
                    client_id=client_id,
                    endpoint=endpoint,
                    current_count=current_count,
                    limit=self.requests_per_minute
                )
                raise RateLimitError(f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute allowed.")
            
            logger.debug(
                "Rate limit check passed",
                client_id=client_id,
                endpoint=endpoint,
                current_count=current_count + 1,  # +1 because we just added the current request
                limit=self.requests_per_minute
            )
            
        except RateLimitError:
            raise
        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            # Fail open - don't block requests if rate limiter fails
            pass
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()


# Global rate limiter instance
rate_limiter = RateLimiter()
