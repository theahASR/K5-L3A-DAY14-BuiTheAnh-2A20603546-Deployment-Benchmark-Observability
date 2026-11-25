"""
Production AI Agent — Part 6 Final Project.

Endpoints:
  GET  /health  — liveness, luôn 200 khi process còn chạy
  GET  /ready   — readiness, 503 khi Redis không kết nối được
  POST /ask     — API key → rate limit → cost guard → LLM → record cost

Chạy local:
    AGENT_API_KEY=dev-key uvicorn app.main:app --reload
"""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask

# ── Structured logging: mỗi dòng do app ghi là một JSON object ──
logger = logging.getLogger("agent")
logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
logger.propagate = False


def log_event(event: str, **fields) -> None:
    logger.info(
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "event": event,
                **fields,
            },
            ensure_ascii=False,
        )
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_event("startup", environment=settings.environment)
    yield
    log_event("shutdown")
    try:
        r.close()
    except Exception:
        pass


app = FastAPI(title="Production AI Agent", version="1.0.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health():
    """Liveness: chỉ kiểm tra process, KHÔNG phụ thuộc Redis."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: Redis không kết nối được → 503."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis not ready")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    # Sync endpoint → FastAPI chạy trong threadpool, không block event loop
    # vì mock LLM dùng time.sleep().
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)

    input_tokens = max(1, len(body.question) // 4)
    output_tokens = max(1, len(answer) // 4)
    cost = record_cost(input_tokens, output_tokens)

    log_event(
        "ask",
        question_len=len(body.question),
        status=200,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 8),
    )
    return {"question": body.question, "answer": answer}
