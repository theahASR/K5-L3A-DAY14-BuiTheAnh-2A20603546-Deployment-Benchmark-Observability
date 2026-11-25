"""
API Key authentication (tiêu chí 6).

Client gửi header X-API-Key: <key>. Key phải trùng AGENT_API_KEY.
Thiếu hoặc sai → HTTP 401 (không phải 403 hay 422).
"""
import secrets

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Dependency cho FastAPI — dùng trong /ask: Depends(verify_api_key)."""
    if not api_key or not settings.agent_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    if not secrets.compare_digest(api_key, settings.agent_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key
