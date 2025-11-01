"""
Rate Limiting Middleware

Protects the system from abuse and DoS attacks using Redis-based rate limiting.

Features:
- Per-user rate limiting for orders
- Per-user rate limiting for payment checks
- Configurable limits via environment variables
- Automatic expiry using Redis TTL
- User-friendly error messages

Configuration:
- MAX_ORDERS_PER_USER_PER_HOUR: Maximum orders per user per hour
- MAX_PAYMENT_CHECKS_PER_MINUTE: Maximum payment status checks per minute
"""

import logging
from datetime import datetime
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from redis.asyncio import Redis

import config


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware for rate limiting user actions.

    Uses Redis for distributed rate limiting (works across multiple bot instances).
    """

    def __init__(self, redis: Redis):
        """
        Initialize rate limiting middleware.

        Args:
            redis: Redis client for storing rate limit counters
        """
        super().__init__()
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Process event with rate limiting checks.

        Args:
            handler: Next handler in chain
            event: Telegram event (Message or CallbackQuery)
            data: Handler data

        Returns:
            Handler result or None if rate limited
        """
        # Extract user ID
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if not user_id:
            # No user ID - allow (system events, etc.)
            return await handler(event, data)

        # Check rate limits based on event type
        # This is a simple implementation - extend based on your needs
        # For now, we'll implement this in specific services (order creation, payment checks)

        # Continue to next handler
        return await handler(event, data)


class RateLimiter:
    """
    Redis-based rate limiter for specific operations.

    Usage:
        limiter = RateLimiter(redis)
        if await limiter.is_rate_limited("order", user_id, max_count=5, window_seconds=3600):
            # User exceeded rate limit
            pass
    """

    def __init__(self, redis: Redis):
        """
        Initialize rate limiter.

        Args:
            redis: Redis client
        """
        self.redis = redis

    async def is_rate_limited(
        self,
        operation: str,
        user_id: int,
        max_count: int,
        window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Check if user has exceeded rate limit for an operation.

        Args:
            operation: Operation name (e.g., "order_create", "payment_check")
            user_id: User's Telegram ID
            max_count: Maximum allowed operations in time window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_limited, current_count, remaining_count)
            - is_limited: True if user has exceeded the limit
            - current_count: Current number of operations in window
            - remaining_count: Number of operations remaining (0 if limited)

        Example:
            >>> is_limited, current, remaining = await limiter.is_rate_limited(
            ...     "order_create", 12345, max_count=5, window_seconds=3600
            ... )
            >>> if is_limited:
            ...     print(f"Rate limited! {current}/{max_count} orders in last hour")
        """
        # Redis key: rate_limit:{operation}:{user_id}
        key = f"rate_limit:{operation}:{user_id}"

        try:
            # Increment counter (creates key if doesn't exist)
            current_count = await self.redis.incr(key)

            # Set expiry on first increment
            if current_count == 1:
                await self.redis.expire(key, window_seconds)

            # Check if limit exceeded
            is_limited = current_count > max_count
            remaining = max(0, max_count - current_count)

            if is_limited:
                # Get TTL for reset time
                ttl = await self.redis.ttl(key)
                logging.warning(
                    f"Rate limit exceeded: user={user_id}, operation={operation}, "
                    f"count={current_count}/{max_count}, resets_in={ttl}s"
                )

            return is_limited, current_count, remaining

        except Exception as e:
            # If Redis fails, don't block the operation (fail open)
            logging.error(f"Rate limiter error: {e}")
            return False, 0, max_count

    async def reset_limit(self, operation: str, user_id: int):
        """
        Reset rate limit counter for a user.

        Args:
            operation: Operation name
            user_id: User's Telegram ID

        Usage:
            # Admin manually resets a user's rate limit
            await limiter.reset_limit("order_create", 12345)
        """
        key = f"rate_limit:{operation}:{user_id}"
        await self.redis.delete(key)
        logging.info(f"Rate limit reset: user={user_id}, operation={operation}")

    async def get_remaining_time(self, operation: str, user_id: int) -> int:
        """
        Get remaining time until rate limit resets.

        Args:
            operation: Operation name
            user_id: User's Telegram ID

        Returns:
            Remaining seconds until reset (0 if not rate limited)
        """
        key = f"rate_limit:{operation}:{user_id}"
        ttl = await self.redis.ttl(key)
        return max(0, ttl) if ttl > 0 else 0


# Example usage in services:
"""
from middleware.rate_limit import RateLimiter

class OrderService:
    @staticmethod
    async def create_order(...):
        limiter = RateLimiter(redis)

        # Check rate limit
        is_limited, current, remaining = await limiter.is_rate_limited(
            "order_create",
            user_id,
            max_count=config.MAX_ORDERS_PER_USER_PER_HOUR,
            window_seconds=3600
        )

        if is_limited:
            reset_time = await limiter.get_remaining_time("order_create", user_id)
            raise ValueError(f"Rate limit exceeded. Try again in {reset_time // 60} minutes.")

        # Continue with order creation...
"""
