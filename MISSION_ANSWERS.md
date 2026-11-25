# Day 14 Lab — Mission Answers

**Họ tên:** Bùi Thế Anh  
**MSSV:** 2A20603546  
**Ngày thực hiện:** 25/11/2026

> Ghi chú: Part 1 được chạy thực tế trên WSL2 Ubuntu (Python 3.14, UTF-8). Khi kiểm tra, cổng 8000 đang được bản `production` sử dụng, nên bản `develop` được chạy ở cổng 8010 bằng `python -m uvicorn app:app --host 127.0.0.1 --port 8010`. Khi chạy lại từ đầu, có thể dừng bản production rồi dùng đúng cổng 8000 như hướng dẫn.

---

## Part 1 — Localhost vs Production

### Exercise 1.1 — Các anti-pattern trong `01-localhost-vs-production/develop/app.py`

Dưới đây là 12 vấn đề tìm được (yêu cầu tối thiểu là 5):

| # | Anti-pattern | Dòng | Giải thích |
|---|---|---:|---|
| 1 | Hardcode API key: `OPENAI_API_KEY = "sk-hardcoded-..."` | 17 | Push code lên GitHub là lộ key ngay; không thể rotate theo môi trường. Key thật phải đọc từ biến môi trường/secret manager. |
| 2 | Hardcode chuỗi kết nối database có mật khẩu: `DATABASE_URL = "postgresql://admin:...@localhost:5432/mydb"` | 18 | Lộ thông tin đăng nhập DB; mật khẩu nằm trong lịch sử git, xoá file cũng không đủ. |
| 3 | Config cứng: `DEBUG = True`, `MAX_TOKENS = 500` | 21–22 | Không đổi được giữa dev/staging/production nếu không sửa code; debug bật trong production rất nguy hiểm. |
| 4 | Dùng `print()` thay vì logging có cấu trúc | 33, 34, 38 | Log không parse được bằng máy, không có level/timestamp/request_id; khó tìm khi có sự cố. |
| 5 | In cả API key ra log: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` | 34 | Secret bị ghi vào log/terminal, dễ lộ khi chia sẻ log hoặc đẩy lên log aggregator. |
| 6 | Không có health check (`/health`) và readiness (`/ready`) | — | Platform không biết container còn sống hay đã sẵn sàng nhận traffic; không tự restart/ngừng route được. |
| 7 | Bind `localhost` và port cứng: `host="localhost"`, `port=8000` | 51–52 | Trong container/cloud, app phải bind `0.0.0.0` và lắng nghe theo biến `PORT` do platform cấp. |
| 8 | Bật `reload=True` | 53 | Reload dành cho development; trong production gây tốn tài nguyên, không ổn định, có thể restart ngoài ý muốn. |
| 9 | Không có authentication cho `/ask` | 30–39 | Ai cũng gọi được endpoint tốn tiền LLM; không kiểm soát được người dùng. |
| 10 | Không validate input và không xử lý lỗi | 31 | `question` chỉ là `str`, không giới hạn độ dài/rỗng; lỗi có thể trả stack trace thay vì mã lỗi rõ ràng. |
| 11 | Không xử lý graceful shutdown/SIGTERM | — | Khi `docker stop` hoặc platform scale down, request đang chạy có thể bị cắt ngang. |
| 12 | Không có config tập trung | 17–22 | Không theo 12-Factor; cùng một image không thể chạy ở nhiều môi trường. |

**Bằng chứng thực tế:** Khi chạy bản develop bằng Python Windows (console cp1252), chính dòng `print()` tiếng Việt ở dòng 38 đã gây `UnicodeEncodeError` và trả HTTP 500. Trong WSL/UTF-8 thì request trả 200. Đây là minh chứng rằng `print()` không đáng tin cậy bằng logging có cấu trúc.

### Exercise 1.2 — Chạy bản develop và gọi thử

Cài đặt và chạy:

```bash
cd 01-localhost-vs-production/develop
pip install -r requirements.txt
python app.py
```

Do cổng 8000 đang được bản production dùng khi kiểm tra, bản develop được chạy bằng:

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8010
```

Kết quả gọi thật:

```text
GET http://127.0.0.1:8010/
HTTP 200
{"message":"Hello! Agent is running on my machine :)"}
```

```text
POST http://127.0.0.1:8010/ask?question=Hello
HTTP 200
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Thử gửi JSON thay vì query (đúng như lưu ý K5: bản develop nhận `question` qua query):

```text
POST http://127.0.0.1:8010/ask
Body: {"question": "Hello"}

HTTP 422
{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

Kết luận: bản develop chạy được nhưng chỉ ở mức "works on my machine"; nó nhận query, không nhận JSON, không có health check, và lộ secret qua log.

### Exercise 1.3 — So sánh bản develop và production

| Feature | Basic (`develop/app.py`) | Advanced (`production/app.py`) | Tại sao quan trọng? |
|---|---|---|---|
| Config | Hardcode `DEBUG`, `MAX_TOKENS`, key, DB URL | Đọc từ biến môi trường qua `config.py` (`os.getenv`), có `.env.example` | Cùng một image chạy được ở dev/staging/production; không sửa code khi đổi môi trường |
| Secrets | Nằm trực tiếp trong code | Lấy từ env, `.env` nằm trong `.gitignore` | Không lộ khi push GitHub; dễ rotate |
| Health check | Không có | `GET /health` (liveness) và `GET /ready` (readiness) | Platform biết khi nào restart container và khi nào route traffic |
| Logging | `print()` text tự do | JSON structured qua `logging` + `json.dumps` | Dễ parse, lọc, gắn request_id; không log secret |
| Shutdown | Không xử lý, tắt đột ngột | `lifespan` + xử lý SIGTERM, chờ request in-flight | `docker stop`/scale down không làm mất request |
| Host/Port | `localhost:8000` cố định | `0.0.0.0`, port từ `PORT` env | Chạy được trong container và trên cloud (Railway/Render cấp `PORT`) |
| Debug/reload | `DEBUG=True`, `reload=True` | `reload` chỉ bật khi `DEBUG=true`; production tắt | Ổn định, không tự restart, không lộ debug |
| Input validation | `question: str` không kiểm tra | Đọc JSON, kiểm tra `question` rỗng, trả `422` rõ ràng | Tránh crash và trả lỗi có kiểm soát |
| Error handling | Không có | `HTTPException` với mã lỗi rõ ràng | Client biết lỗi gì; không lộ stack trace |
| CORS | Không cấu hình | `CORSMiddleware` với origins từ env | Kiểm soát frontend nào được gọi API |
| Observability | Không có | `/metrics` cơ bản, log JSON, uptime | Có dữ liệu để giám sát khi chạy thật |
| Deployment readiness | Chỉ chạy local | 12-Factor: config env, stateless, health, graceful shutdown | Sẵn sàng đóng gói container và deploy cloud |

### Kết quả chạy bản production (đối chiếu)

```text
GET http://127.0.0.1:8000/health
HTTP 200
{"status":"ok","uptime_seconds":303.6,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T11:39:40.671276+00:00"}
```

```text
GET http://127.0.0.1:8000/ready
HTTP 200
{"ready":true}
```

```text
POST http://127.0.0.1:8000/ask
Body: {"question": "Hello"}

HTTP 200
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}
```

### Tự kiểm tra CP1 — một anti-pattern đã được sửa

- `develop/app.py` dòng 17: `OPENAI_API_KEY = "sk-hardcoded-..."`
- `production/config.py` dòng 32: `api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))`

Tương tự, `develop/app.py` dòng 51–52 bind `localhost:8000` cố định, còn `production/app.py` dòng 196–197 dùng `host=settings.host` (`0.0.0.0`) và `port=settings.port` (đọc từ `PORT`).

### Kết luận Part 1

Bản develop chứng minh agent chạy được trên laptop, nhưng chưa production-ready vì hardcode secret, không có health/readiness, log bằng `print()`, port/host cố định và không xử lý shutdown. Bản production áp dụng 12-Factor: config từ environment, secret tách khỏi code, log JSON, health/readiness, graceful shutdown và bind `0.0.0.0` theo `PORT`. Đây là những yêu cầu tối thiểu trước khi đóng gói Docker và deploy cloud.

---

## Part 2 — Docker

### Exercise 2.1 — Dockerfile cơ bản

Đọc `02-docker/develop/Dockerfile` và trả lời:

1. **Base image là gì?**  
   `python:3.11` — bản Python đầy đủ (không phải slim/alpine), nên image khá lớn.

2. **Working directory là gì?**  
   `/app` (dòng 11: `WORKDIR /app`).

3. **Tại sao `COPY requirements.txt` phải đứng trước `COPY . .`?**  
   Docker build theo từng layer và dùng cache. Khi `requirements.txt` không đổi, layer `pip install` được lấy từ cache; chỉ khi requirements thay đổi mới phải cài lại. Nếu copy toàn bộ source trước, mỗi lần sửa một dòng code sẽ làm mất cache dependencies và build lại từ đầu.

4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?**  
   - `ENTRYPOINT` là lệnh chính, luôn chạy khi container start; khó bị override hơn.
   - `CMD` là lệnh/đối số mặc định, có thể bị thay thế bằng lệnh truyền vào `docker run`.
   - Có thể kết hợp: `ENTRYPOINT ["python"]` + `CMD ["app.py"]`.
   - Nên dùng **exec form** (`["python", "app.py"]`) thay vì shell form để tín hiệu (SIGTERM) đến đúng process. Dockerfile này dùng `CMD ["python", "app.py"]`.

### Exercise 2.2 — Build và chạy bản develop

Build từ **gốc repo** (Dockerfile dùng đường dẫn tính từ root):

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name agent-develop -p 8000:8000 my-agent:develop
```

Kết quả gọi container:

```text
GET http://127.0.0.1:8000/
HTTP 200
{"message":"Agent is running in a Docker container!"}
```

```text
POST http://127.0.0.1:8000/ask?question=Hello
HTTP 200
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Gửi JSON thay vì query vẫn trả 422 — bản develop nhận `question` qua query:

```text
POST http://127.0.0.1:8000/ask
Body: {"question": "Hello"}
HTTP 422
{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

Log container cho thấy uvicorn chạy trong container:

```text
INFO:     Started server process [1]
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
"GET / HTTP/1.1" 200 OK
"POST /ask?question=Hello HTTP/1.1" 200 OK
```

Kích thước image (đo thực tế):

```text
my-agent:develop   1.67GB     # docker images
docker image inspect .Size: 426,319,997 bytes ≈ 406.6 MB
```

### Exercise 2.3 — Multi-stage build

Đọc `02-docker/production/Dockerfile`:

- **Stage 1 — builder:** `python:3.11-slim`, cài `gcc` + `libpq-dev`, copy `requirements.txt` và chạy `pip install --no-cache-dir --user -r requirements.txt` → dependencies nằm trong `/root/.local`. Stage này có build tools nhưng **không được dùng để deploy**.
- **Stage 2 — runtime:** `python:3.11-slim` sạch, tạo user `appuser`, copy `/root/.local` từ builder sang `/home/appuser/.local`, copy `main.py` + `utils/mock_llm.py`, chown, chuyển sang `USER appuser`, đặt `PATH`/`PYTHONPATH`, thêm `HEALTHCHECK` và `CMD` chạy uvicorn với 2 worker.

**Vì sao image nhỏ hơn?** Stage runtime không mang theo compiler, apt packages, pip cache hay source trung gian; chỉ có Python runtime + site-packages + code cần chạy.

Build và chạy:

```bash
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker run -d --name agent-advanced -p 8000:8000 my-agent:advanced
```

Kết quả:

```text
GET /health  → HTTP 200
{"status":"ok","uptime_seconds":0.4,"version":"2.0.0","timestamp":"..."}

GET /ready   → HTTP 200
{"ready":true}

POST /ask (JSON) → HTTP 200
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Log cho thấy uvicorn chạy 2 worker và log JSON:

```text
INFO:     Started parent process [1]
INFO:     Started server process [8]
INFO:     Started server process [9]
{"time":"...","level":"INFO","msg":"Starting agent..."}
{"time":"...","level":"INFO","msg":"Agent ready"}
```

So sánh kích thước:

| Image | `docker images` | `docker image inspect .Size` |
|---|---:|---:|
| `my-agent:develop` | 1.67 GB | 406.6 MB |
| `my-agent:advanced` | 240 MB | 54.7 MB |
| **Giảm** | **~85.6%** | **86.5%** |

Công thức: `(size_develop - size_advanced) / size_develop × 100`.

> Ghi chú: Docker Desktop hiển thị `docker images` lớn hơn `docker image inspect .Size` (có thể do manifest/attestation của BuildKit). Mình ghi cả hai số đo thực tế; tỉ lệ giảm nhất quán (~86%), và script chấm dùng `.Size` của inspect.

### Exercise 2.4 — Docker Compose stack

Các service trong `02-docker/production/docker-compose.yml`:

| Service | Image / Build | Vai trò | Port ra host |
|---|---|---|---|
| `nginx` | `nginx:alpine` | Reverse proxy + load balancer, chặn/giới hạn request | `80`, `443` |
| `agent` | build từ `02-docker/production/Dockerfile` (target `runtime`) | FastAPI agent, chạy 2 instance | Không publish trực tiếp |
| `redis` | `redis:7-alpine` | Cache/session + rate limiting | Không publish |
| `qdrant` | `qdrant/qdrant:v1.9.0` | Vector database cho RAG | Không publish |

**Sơ đồ:**

```text
Client
  │ :80/:443
  ▼
Nginx (reverse proxy + LB)
  │ round-robin tới agent:8000
  ├──────────────┐
  ▼              ▼
agent-1        agent-2
  │              │
  ├──────┬───────┘
  ▼      ▼
Redis   Qdrant
(session/cache) (vector DB)
```

- Các service nói chuyện qua **DNS nội bộ Docker** trên network `internal`: `agent` gọi `redis:6379`, `qdrant:6333`; Nginx gọi `agent:8000`.
- Chỉ Nginx publish port ra ngoài; agent/redis/qdrant không lộ trực tiếp.
- `agent` có `depends_on` redis/qdrant với `condition: service_healthy`; `env_file: .env.local` (file này không có sẵn trong repo, phải `touch`).

Khởi động:

```bash
cd 02-docker/production
touch .env.local
docker compose -p k5-day14-docker up -d --build --scale agent=2
docker compose -p k5-day14-docker ps
```

Kết quả:

```text
NAME                       SERVICE   STATUS                   PORTS
k5-day14-docker-agent-1    agent     Up (healthy)             8000/tcp
k5-day14-docker-agent-2    agent     Up (healthy)             8000/tcp
k5-day14-docker-nginx-1    nginx     Up                       0.0.0.0:80->80/tcp
k5-day14-docker-qdrant-1   qdrant    Up (healthy)             6333-6334/tcp
k5-day14-docker-redis-1    redis     Up (healthy)             6379/tcp
```

Test qua Nginx (cổng 80):

```text
GET http://localhost/health
HTTP 200
{"status":"ok","uptime_seconds":38.8,"version":"2.0.0","timestamp":"..."}

GET http://localhost/ready
HTTP 200
{"ready":true}

POST http://localhost/ask
Body: {"question":"Explain microservices"}
HTTP 200
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Gửi thêm 10 request `/ask` qua Nginx, sau đó đếm log của từng agent:

```text
agent-1 served: 5/10
agent-2 served: 5/10
```

→ Nginx phân tải round-robin đều giữa 2 instance. Log của agent có JSON request:

```text
{"time":"...","level":"INFO","msg":"{"event": "request", "q_len": 33}"}
INFO:     172.22.0.6:39986 - "POST /ask HTTP/1.1" 200 OK
```

Dọn stack (đã chạy):

```bash
docker compose -p k5-day14-docker down -v
```

Sau khi dọn, không còn container/network/volume của bài.

### Cách debug container

```bash
docker logs <container>                 # xem log app/uvicorn
docker logs -f <container>              # theo dõi log realtime
docker exec -it <container> sh          # vào shell trong container
docker inspect <container>              # xem IP, env, mounts, health
docker compose -p k5-day14-docker logs agent   # log tất cả agent instances
```

### Kết luận Part 2

- `COPY requirements.txt` trước `COPY . .` giúp tận dụng Docker layer cache: chỉ cài lại dependencies khi `requirements.txt` thay đổi.
- Multi-stage tách **builder** (có compiler/build tools) khỏi **runtime** (chỉ Python + site-packages + code), nên image advanced nhỏ hơn khoảng 86% và ít bề mặt tấn công hơn.
- Docker Compose dựng cả stack bằng một lệnh; Nginx là cổng vào duy nhất, agent/redis/qdrant chỉ nói chuyện trong network nội bộ; scale 2 agent và quan sát Nginx chia đều 5/5 request.

---

## Part 3 — Cloud Deployment

<!-- Điền sau khi hoàn thành CP6: URL public, so sánh railway.toml/render.yaml, mô tả pipeline Cloud Run. -->

---

## Part 4 — API Security

### Exercise 4.1 — API Key authentication (develop)

Đọc `04-api-gateway/develop/app.py`:

- Key đọc từ `AGENT_API_KEY`, mặc định `demo-key-change-in-production`.
- Header kiểm tra: `X-API-Key` qua `APIKeyHeader(name="X-API-Key", auto_error=False)`.
- Thiếu key → **401**; sai key → **403** (bản develop); đúng key → **200**.
- Rotate key: đổi biến `AGENT_API_KEY` trên môi trường và restart app; không sửa code.

Chạy đúng như README K5:

```bash
cd 04-api-gateway/develop
pip install -r requirements.txt
AGENT_API_KEY=secret-key-123 python app.py
```

Kết quả thực tế:

```text
POST /ask   (không có X-API-Key)
HTTP 401
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

```text
POST /ask   (X-API-Key: secret-key-123)
HTTP 200
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

```text
POST /ask   (X-API-Key: wrong-key)
HTTP 403
{"detail":"Invalid API key."}
```

### Exercise 4.2 — JWT authentication (production)

Chạy:

```bash
cd ../production
pip install -r requirements.txt
python app.py
```

Lấy token đúng tài khoản K5:

```bash
curl -i -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"demo123"}'
```

Kết quả: HTTP 200, trả `access_token` (JWT HS256, hết hạn sau 60 phút). Token thật đã được che:

```text
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5...<đã cắt>",
  "token_type": "bearer",
  "expires_in_minutes": 60
}
```

Gọi `/ask` không có token → **401**:

```text
POST /ask
HTTP 401
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

Gọi `/ask` với token → **200**:

```text
POST /ask
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5...<đã cắt>
{"question":"Explain JWT"}

HTTP 200
{
  "question": "Explain JWT",
  "answer": "Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.",
  "usage": {"requests_remaining": 9, "budget_remaining_usd": 0.000016}
}
```

Đọc `auth.py`:
- `create_token()` tạo JWT với `sub`, `role`, `iat`, `exp`; ký bằng `SECRET_KEY` + HS256.
- `verify_token()` dùng `HTTPBearer(auto_error=False)`; thiếu token → 401; token hết hạn → 401; token sai → 403.
- Demo users: `student/demo123` (user, 10 req/min) và `teacher/teach456` (admin, 100 req/min).

### Exercise 4.3 — Rate limiting

Đọc `rate_limiter.py`:
- Algorithm: **sliding window counter** bằng `deque` timestamp trong memory.
- `student`: **10 request/phút**; `teacher`: 100 request/phút.
- Vượt giới hạn → `HTTPException(429)` kèm `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
- Bản mẫu lưu trong memory nên reset khi restart và **không dùng chung giữa nhiều instance**; production thật nên thay bằng Redis.

Chạy vòng lặp 20 request với token `student` (bash/WSL):

```bash
TOKEN="<token_lấy_từ_auth/token>"
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/ask \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"question\":\"Rate test $i\"}"
done
```

```text
Kết quả 20 request:
200 × 10
429 × 10

Request thứ 11:
HTTP 429
retry-after: 59
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
body: {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Tổng hợp output `curl -i` (token đã che)

```text
# 401 — không gửi token
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
content-type: application/json
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

# 200 — token hợp lệ
HTTP/1.1 200 OK
content-type: application/json
{"question":"Explain JWT","answer":"Agent đang hoạt động tốt! ...","usage":{...}}

# 429 — vượt 10 request/phút
HTTP/1.1 429 Too Many Requests
retry-after: 59
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
content-type: application/json
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4 — Cost guard

Đọc `cost_guard.py`:
- `check_budget(user_id)` gọi **trước** LLM.
- Per-user budget `$1/ngày`: vượt → **402 Payment Required**.
- Global budget `$10/ngày`: vượt → **503 Service Unavailable**.
- `record_usage(user_id, input_tokens, output_tokens)` gọi **sau** LLM, cộng token và tính cost.
- Cảnh báo khi dùng 80% budget.
- Bản mẫu lưu in-memory; production nên lưu Redis/DB, dùng phép tính atomic và reset theo ngày/tháng.

Mình kiểm tra logic bằng unit test nhỏ (không sửa file mẫu):

```text
budget $1.00: OK (còn budget, không có 402)
budget $0.000001: HTTP 402 - {'error': 'Daily budget exceeded', 'used_usd': 7.5e-05, 'budget_usd': 1e-06, 'resets_at': 'midnight UTC'}
global cap $0.000001: HTTP 503 - Service temporarily unavailable due to budget limits. Try again tomorrow.
```

**Rate limit vs cost guard:** rate limit bảo vệ **tốc độ** (chống spam, bảo vệ hạ tầng); cost guard bảo vệ **tiền** (một request có thể rất đắt dù số lượng ít). Cần cả hai vì chúng chặn hai loại rủi ro khác nhau.

### Kết luận Part 4

- API key phù hợp MVP/internal API; JWT phù hợp khi cần danh tính, role và token hết hạn.
- Rate limit phải lưu state dùng chung (Redis) khi scale; bản mẫu in-memory chỉ để học.
- Cost guard nên kiểm tra trước khi gọi LLM và ghi nhận sau khi gọi; nếu chỉ ghi nhận mà không chặn, bill vẫn có thể vượt budget.
- Không bao giờ trả stack trace hay log token/secret; các response trên đều trả JSON lỗi rõ ràng.

---

## Part 5 — Scaling & Reliability

### Exercise 5.1 — Health checks

Chạy `05-scaling-reliability/develop`:

```bash
cd 05-scaling-reliability/develop
pip install -r requirements.txt
python app.py
```

Kết quả thực tế:

```text
GET /health
HTTP 200
{
  "status": "ok",
  "uptime_seconds": 2.0,
  "version": "1.0.0",
  "environment": "development",
  "timestamp": "...",
  "checks": {"memory": {"status": "ok", "note": "psutil not installed"}}
}
```

```text
GET /ready
HTTP 200
{"ready": true, "in_flight_requests": 1}
```

```text
POST /ask?question=hello
HTTP 200
{"answer": "Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

- `/health` là **liveness**: process còn sống thì trả 200; platform dùng để quyết định restart container.
- `/ready` là **readiness**: chỉ trả 200 khi đã sẵn sàng nhận traffic; đang startup/shutdown hoặc thiếu dependency thì trả **503** để load balancer ngừng route traffic (không restart).
- Trong Part 6: `/health` phải **luôn 200 kể cả khi Redis chết**; `/ready` phải **503 khi Redis không kết nối được**.

### Exercise 5.2 — Graceful shutdown

Cơ chế trong `05-scaling-reliability/develop/app.py`:
- `lifespan` startup đặt `_is_ready = True`; shutdown đặt `_is_ready = False`.
- Middleware `track_requests` tăng/giảm `_in_flight_requests`.
- Khi shutdown, app chờ các request in-flight hoàn thành (tối đa 30 giây) rồi mới thoát.
- `uvicorn.run(..., timeout_graceful_shutdown=30)`.

Test gửi SIGTERM khi đang có 1 request `/ask` (mock delay 3 giây):

```text
server pid=8948
sending SIGTERM while one request is in flight...
request_status=200
request_body={"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
server_exit_code=0

--- server log ---
INFO:     Shutting down
INFO:     127.0.0.1:53500 - "POST /ask?question=hello HTTP/1.1" 200 OK
INFO:     Waiting for application shutdown.
INFO:     🔄 Graceful shutdown initiated...
INFO:     ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [8948]
```

→ Request đang chạy vẫn trả **200**, process tự thoát với **exit code 0**, không bị cắt ngang.

**Hai phát hiện thực tế quan trọng:**

1. **Event loop bị block:** `/ask` là `async def` nhưng gọi mock `ask()` có `time.sleep(3)` trực tiếp. Khi gửi 2 request song song, chỉ request đầu được xử lý; request thứ hai không chạy song song. Trong production nên dùng async LLM client (httpx/AsyncOpenAI), hoặc để endpoint là `def` (FastAPI chạy trong threadpool), hoặc `run_in_threadpool`.
2. **Custom SIGTERM handler:** app tự gọi `signal.signal(SIGTERM, handle_sigterm)` chỉ để log. Khi chạy bằng `uvicorn app:app`, handler này thay handler của uvicorn và server **không thoát** sau SIGTERM. Khi chạy đúng `python app.py`, uvicorn cài handler của nó và shutdown hoạt động. Bài học cho Part 6: nếu tự đăng ký handler, phải gọi lại handler cũ của uvicorn; tốt nhất để uvicorn tự xử lý.

### Exercise 5.3 — Stateless design

- **Anti-pattern:** lưu `conversation_history` trong dict/RAM. Mỗi instance có memory riêng:
  ```text
  Instance 1: user A request 1 → lưu session trong RAM ✅
  Instance 2: user A request 2 → không thấy session ❌
  ```
- **Correct:** lưu session/history trong Redis với TTL:
  ```python
  _redis.setex(f"session:{session_id}", ttl_seconds, json.dumps(data))
  data = _redis.get(f"session:{session_id}")
  ```
- Trong `05-scaling-reliability/production/app.py`:
  - `save_session()` / `load_session()` dùng Redis, TTL 1 giờ.
  - `append_to_history()` giữ tối đa 20 messages.
  - `served_by` cho biết instance nào phục vụ request.
  - Nếu Redis không kết nối được, app fallback sang in-memory — chỉ để demo; production thật nên fail-fast/alert thay vì âm thầm mất state.

### Exercise 5.4 — Load balancing

```bash
cd 05-scaling-reliability/production
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
docker compose -p k5-day14-scaling ps
```

Kết quả:

```text
NAME                       STATUS                   PORTS
k5-day14-scaling-agent-1   Up (healthy)             8000/tcp
k5-day14-scaling-agent-2   Up (healthy)             8000/tcp
k5-day14-scaling-agent-3   Up (healthy)             8000/tcp
k5-day14-scaling-nginx-1   Up                       0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1   Up (healthy)             6379/tcp
```

- 3 agent instance không publish port trực tiếp; chỉ Nginx mở **8080**.
- Nginx dùng Docker DNS `agent:8000` để round-robin; request được chia cho các instance.

### Exercise 5.5 — Test stateless

Chạy (trong WSL để tránh lỗi encoding tiếng Việt trên Windows):

```bash
python test_stateless.py
```

Kết quả thực tế:

```text
Session ID: ccd4fc18-f12b-4bbf-b302-dce50f2d9ee1

Request 1: [instance-43a97f]
Request 2: [instance-71a145]
Request 3: [instance-958d08]
Request 4: [instance-43a97f]
Request 5: [instance-71a145]

Total requests: 5
Instances used: {'instance-43a97f', 'instance-71a145', 'instance-958d08'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

- 5 request đi qua **3 instance khác nhau**, nhưng history vẫn đủ **10 messages** (5 user + 5 assistant).
- Log agent cho thấy `Storage: Redis ✅`, `POST /chat 200`, `GET /chat/.../history 200`.
- Script **không kill instance nào** (đúng README K5); nó chứng minh state dùng chung qua Redis.

Dọn stack:

```bash
docker compose -p k5-day14-scaling down -v
```

### Kết luận Part 5

- Liveness (`/health`) và readiness (`/ready`) phục vụ hai mục đích khác nhau: restart process vs ngừng route traffic.
- Graceful shutdown cần uvicorn nhận SIGTERM và chờ request in-flight; đừng tự chặn handler của uvicorn.
- State trong RAM không thể scale ngang; Redis là nơi dùng chung cho session/history.
- `test_stateless.py` chứng minh: 3 instance khác nhau vẫn phục vụ cùng một session, history không mất.
- Khi scale, cần chú ý cả điểm nghẽn bên trong app (event loop bị block bởi sync call) chứ không chỉ số instance.

---

## Part 6 — Final Project

### Những gì đã sửa trong `06-lab-complete/`

| Tiêu chí | File | Cách làm |
|---|---|---|
| 1. Dockerfile multi-stage, < 500 MB | `Dockerfile` | Builder cài deps bằng `pip --user`; runtime `python:3.11-slim`, non-root `appuser`, `HEALTHCHECK`, `exec uvicorn` với `${PORT}` |
| 2. Compose agent + redis | `docker-compose.yml` | agent build từ Dockerfile + redis:7-alpine; `REDIS_URL=redis://redis:6379/0`, `depends_on` healthcheck |
| 3. `.dockerignore` | `.dockerignore` | Loại `.env`, `__pycache__`, `venv`, `.git`, `benchmark-observability/` |
| 4. `/health` | `app/main.py` | Luôn 200 khi process còn chạy, không phụ thuộc Redis |
| 5. `/ready` | `app/main.py`, `app/redis_client.py` | Ping Redis; lỗi kết nối → 503 |
| 6. API key | `app/auth.py` | `X-API-Key` qua `APIKeyHeader(auto_error=False)`; thiếu/sai → 401 |
| 7. Rate limit | `app/rate_limiter.py` | Sliding window 60s bằng Redis sorted set; vượt → 429 + `Retry-After` |
| 8. Cost guard | `app/cost_guard.py` | `check_budget()` trước LLM → 402; `record_cost()` sau LLM cộng Redis |
| 9. Config từ env | `app/config.py`, `.env.example` | `os.getenv` cho PORT, ENVIRONMENT, AGENT_API_KEY, REDIS_URL, RATE_LIMIT_PER_MINUTE, DAILY_BUDGET_USD |
| 10. JSON logging | `app/main.py` | `json.dumps` từng dòng, logger riêng `propagate=False` |
| 11. Graceful shutdown | `app/main.py`, `Dockerfile` | `lifespan` đóng Redis; CMD dùng `exec` để uvicorn là PID 1 |
| 12. Deploy config | `railway.toml`, `render.yaml` | Railway builder DOCKERFILE + healthcheck `/health`; Render web + healthCheckPath + secret `generateValue`/`sync: false` |

### Kết quả `check_production_ready.py`

Chạy trong WSL2 Ubuntu (Python 3.14, Docker 28.5.1):

```bash
cd 06-lab-complete
python check_production_ready.py
```

```text
✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Docker: build image thành công — 79s
     ✅ Docker: image < 500 MB — 69 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
✅ 3. .dockerignore

✅ 4. Health check endpoint (GET /health)
✅ 5. Readiness endpoint (GET /ready)
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
✅ 7. Rate limiting
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Khi chạy: hết budget → 402

✅ 9. Config từ environment variables
✅ 10. Structured logging
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 7 dòng JSON

✅ 11. Graceful shutdown
     ✅ Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — exit code 0
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 1.2s

✅ 12. Public URL ready (Railway / Render config)

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

### Ghi chú kỹ thuật

- Image cuối chỉ **69 MB** nhờ multi-stage + `python:3.11-slim`, không mang compiler/cache.
- `docker stop` mất **1.2s**, exit code 0 → uvicorn nhận SIGTERM đúng (PID 1 nhờ `exec`).
- Rate limit dùng Redis sorted set nên restart agent vẫn còn 429; không dùng dict trong RAM.
- `/health` không gọi Redis; `/ready` ping Redis và trả 503 khi mất kết nối.
- Log app là JSON thuần; log của uvicorn không tính.
- Khi chạy local trong WSL, venv dùng pydantic 2.14.4 (Python 3.14 không có wheel cho pin 2.9.0); Docker image dùng đúng `requirements.txt` với Python 3.11 và vẫn PASS.

---

## AI log

| Lần | Ngày | Hỏi gì | Nhận gì | Tự sửa và tự kiểm tra thế nào |
|---:|---|---|---|---|
| 1 | 25/11/2026 | Nhờ AI thực hiện CP1: đọc anti-pattern, chạy bản develop/production, viết Part 1 | AI chạy develop ở cổng 8010 và production ở 8000, thu output thật; gợi ý 12 anti-pattern và bảng so sánh 12 dòng | Đọc lại `develop/app.py` và `production/app.py` để đối chiếu số dòng; kiểm tra output `curl` khớp với file JSON ghi nhận; tự chạy lại lệnh khi cần |
| 2 | 25/11/2026 | Nhờ AI thực hiện CP2: build/run 2 image Docker, đo size, dựng Compose stack và test Nginx | AI build `my-agent:develop` và `my-agent:advanced`, chạy container, đo size thật, dựng stack 2 agent + nginx + redis + qdrant, test `/health` `/ready` `/ask` và đếm phân tải 5/5 | Đọc lại 2 Dockerfile và `docker-compose.yml`; đối chiếu số MB với `docker images`; kiểm tra log từng agent; tự chạy lại `docker compose ps` trước khi dọn |
| 3 | 25/11/2026 | Nhờ AI thực hiện CP3: chạy API key, JWT, rate limit và cost guard | AI chạy develop với `AGENT_API_KEY=secret-key-123`, lấy token `student/demo123` từ `/auth/token`, gửi 20 request `/ask` (10×200, 10×429), và test logic `CostGuard` cho 402/503 | Đọc lại `app.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`; đối chiếu status/header; token đã được che trước khi ghi vào bài |
| 4 | 25/11/2026 | Nhờ AI thực hiện CP4: health/ready, graceful shutdown, stack 3 agent + Redis + Nginx, test stateless | AI test `/health` `/ready` `/ask`, gửi SIGTERM khi có request in-flight (200, exit 0), dựng stack 3 agent và chạy `test_stateless.py` (3 instance, history 10 messages) | Đọc lại `app.py`, `lifespan`, middleware, `test_stateless.py`; đối chiếu log uvicorn; phát hiện event loop bị block bởi `time.sleep()` và custom SIGTERM handler; đã dọn stack |
| 5 | 25/11/2026 | Nhờ AI làm CP5: sửa toàn bộ TODO trong `06-lab-complete/` để đạt PASS 12/12 | AI implement config/redis/auth/rate limiter/cost guard/main, Dockerfile multi-stage, compose, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`; chạy static → runtime → full check | Đọc lại từng file, đối chiếu 12 tiêu chí trong `06-lab-complete/README.md`; tự chạy `python check_production_ready.py` trong WSL; xác nhận 43/43 checks, image 69 MB, `docker stop` 1.2s |

> Ghi chú: sinh viên cần đọc lại toàn bộ câu trả lời, tự chạy lại ít nhất một lần và chỉnh AI log cho đúng với những gì mình thực sự kiểm tra trước khi nộp.
