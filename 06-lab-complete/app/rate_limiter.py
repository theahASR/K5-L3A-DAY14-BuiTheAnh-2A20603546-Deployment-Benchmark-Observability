"""
Rate limiting (tiêu chí 7).

Sliding window 60 giây bằng Redis sorted set:
  ZREMRANGEBYSCORE (xoá request cũ) → ZCARD (đếm)
  → vượt RATE_LIMIT_PER_MINUTE: 429 + Retry-After
  → ZADD + EXPIRE

State nằm trong Redis nên mọi worker/instance dùng chung và vẫn còn sau restart.
"""
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r


def check_rate_limit(key: str) -> None:
    now = time.time()
    redis_key = f"ratelimit:{key}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(redis_key, 0, now - 60)
    pipe.zcard(redis_key)
    _, count = pipe.execute()

    if count >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

    # Member phải unique để nhiều request trong cùng giây không ghi đè nhau.
    r.zadd(redis_key, {f"{now}:{uuid.uuid4().hex}": now})
    r.expire(redis_key, 60)
