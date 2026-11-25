# Deployment Information — Day 14

## Public URL

https://agent-production-deb67b49.up.railway.app

## Platform

Railway (Dockerfile builder)

- Project: `k5-day14-agent`
- Project dashboard: https://railway.com/project/3c44c286-0c7c-4f85-b592-ae951582aa91
- Service: `agent`
- Redis service: `Redis` (Railway Redis template)
- Region: `iad`
- Domain: `agent-production-deb67b49.up.railway.app`
- Deploy config: `06-lab-complete/railway.toml` (`builder = "DOCKERFILE"`, `healthcheckPath = "/health"`)

## Test Commands

### 1. Health check

```bash
curl -i https://agent-production-deb67b49.up.railway.app/health
# HTTP 200
# {"status":"ok"}
```

### 2. Readiness (Redis)

```bash
curl -i https://agent-production-deb67b49.up.railway.app/ready
# HTTP 200
# {"status":"ready"}
```

### 3. API key required

```bash
curl -i -X POST https://agent-production-deb67b49.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
# HTTP 401
# {"detail":"Invalid or missing API key"}
```

### 4. API key đúng

```bash
curl -i -X POST https://agent-production-deb67b49.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -d '{"question":"Hello"}'
# HTTP 200
# {"question":"Hello","answer":"..."}
```

Kết quả kiểm tra thực tế:

```text
200  GET  /health
200  GET  /ready
401  POST /ask   (không có key)
200  POST /ask   (có key)
```

## Environment Variables Set

Các biến được đặt trên Railway Dashboard / CLI cho service `agent`:

- `AGENT_API_KEY` — secret, không ghi giá trị vào repo
- `REDIS_URL` — tham chiếu tới service Redis (`${{Redis.REDIS_URL}}`)
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`
- `PORT` — Railway tự inject, không set thủ công

Không commit `.env`, API key hay Redis URL vào repo.

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png) — tổng hợp từ `railway status` / `railway service status`
- [Service running / deployment logs](screenshots/running.png) — tổng hợp từ `railway logs --service agent`
- [Test results](screenshots/test.png) — kết quả thật từ public URL

> Có thể thay `dashboard.png` và `running.png` bằng ảnh chụp trực tiếp từ Railway Dashboard nếu Lab Coach yêu cầu ảnh UI gốc; nội dung số liệu trong ảnh hiện tại lấy từ CLI thật.

## Ghi chú

- Image build từ `06-lab-complete/Dockerfile` (multi-stage, `python:3.11-slim`).
- Railway chạy container với `PORT=8080`; Dockerfile dùng `${PORT:-8000}` nên app lắng nghe đúng cổng.
- `/health` không phụ thuộc Redis; `/ready` kiểm tra Redis và trả 503 nếu mất kết nối.
- `AGENT_API_KEY` chỉ đặt trên Railway, không nằm trong code hoặc file được commit.
