"""Rate limiting service using in-memory storage."""

import time
from typing import Dict, List
from collections import defaultdict
import asyncio
import structlog

from app.config import settings
from app.exceptions import RateLimitError

logger = structlog.get_logger()


class RateLimiter:
    """In-memory IP-based rate limiter."""
    
    def __init__(self):
        self.enabled = settings.enable_rate_limiting
        self.requests_per_window = settings.rate_limit_requests_per_window
        self.window_size_seconds = settings.rate_limit_window_size_seconds
        
        # In-memory storage: {ip_address: {endpoint: [timestamp1, timestamp2, ...]}}
        self._rate_limit_data: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        # Background task to clean up old entries
        self._cleanup_task = None
        
        if self.enabled:
            logger.info(
                "Rate limiting enabled",
                requests_per_window=self.requests_per_window,
                window_size_seconds=self.window_size_seconds
            )
    
    async def _cleanup_old_entries(self):
        """Background task to periodically clean up old rate limit entries."""
        while True:
            try:
                await asyncio.sleep(self.window_size_seconds)  # Clean up every window period
                await self._cleanup_expired_entries()
            except Exception as e:
                logger.error("Error in rate limit cleanup task", error=str(e))
    
    async def _cleanup_expired_entries(self):
        """Remove expired entries from rate limit data."""
        async with self._lock:
            current_time = time.time()
            cutoff_time = current_time - self.window_size_seconds
            
            # Clean up expired entries
            ips_to_remove = []
            for ip_address, endpoints in self._rate_limit_data.items():
                endpoints_to_remove = []
                for endpoint, timestamps in endpoints.items():
                    # Filter out expired timestamps
                    valid_timestamps = [ts for ts in timestamps if ts > cutoff_time]
                    if valid_timestamps:
                        endpoints[endpoint] = valid_timestamps
                    else:
                        endpoints_to_remove.append(endpoint)
                
                # Remove empty endpoints
                for endpoint in endpoints_to_remove:
                    del endpoints[endpoint]
                
                # Remove IP if no endpoints left
                if not endpoints:
                    ips_to_remove.append(ip_address)
            
            # Remove IPs with no active endpoints
            for ip_address in ips_to_remove:
                del self._rate_limit_data[ip_address]
    
    async def check_rate_limit(self, client_id: str, endpoint: str) -> None:
        """Check if client IP has exceeded rate limit for endpoint.
        
        Args:
            client_id: IP address of the client
            endpoint: API endpoint name
        """
        if not self.enabled:
            return
        
        async with self._lock:
            try:
                current_time = time.time()
                cutoff_time = current_time - self.window_size_seconds
                
                # Get timestamps for this IP and endpoint
                timestamps = self._rate_limit_data[client_id][endpoint]
                
                # Remove expired timestamps
                valid_timestamps = [ts for ts in timestamps if ts > cutoff_time]
                
                # Check if rate limit exceeded
                if len(valid_timestamps) >= self.requests_per_window:
                    logger.warning(
                        "Rate limit exceeded",
                        client_id=client_id,
                        endpoint=endpoint,
                        current_count=len(valid_timestamps),
                        limit=self.requests_per_window,
                        window_size_seconds=self.window_size_seconds
                    )
                    raise RateLimitError(
                        f"Rate limit exceeded. Maximum {self.requests_per_window} requests per {self.window_size_seconds} seconds allowed."
                    )
                
                # Add current request timestamp
                valid_timestamps.append(current_time)
                self._rate_limit_data[client_id][endpoint] = valid_timestamps
                
                logger.debug(
                    "Rate limit check passed",
                    client_id=client_id,
                    endpoint=endpoint,
                    current_count=len(valid_timestamps),
                    limit=self.requests_per_window
                )
                
            except RateLimitError:
                raise
            except Exception as e:
                logger.error("Rate limit check failed", error=str(e), client_id=client_id, endpoint=endpoint)
                # Fail open - don't block requests if rate limiter fails
                pass
    
    async def start_cleanup_task(self):
        """Start the background cleanup task."""
        if self.enabled and self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_old_entries())
            logger.info("Started rate limit cleanup task")
    
    async def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped rate limit cleanup task")
    
    async def close(self):
        """Clean up resources."""
        await self.stop_cleanup_task()
        async with self._lock:
            self._rate_limit_data.clear()
            logger.info("Rate limiter closed")


# Global rate limiter instance
rate_limiter = RateLimiter()
