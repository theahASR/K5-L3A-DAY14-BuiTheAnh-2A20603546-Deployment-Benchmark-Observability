"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Quan trọng: KHÔNG ping Redis lúc import — app phải khởi động được khi Redis
chưa sẵn sàng. Chỉ /ready kiểm tra Redis và trả 503 khi không kết nối được.
"""
import redis

from app.config import settings

r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def redis_healthy() -> bool:
    """True nếu ping Redis thành công; mọi lỗi kết nối → False."""
    try:
        return bool(r.ping())
    except Exception:
        return False
