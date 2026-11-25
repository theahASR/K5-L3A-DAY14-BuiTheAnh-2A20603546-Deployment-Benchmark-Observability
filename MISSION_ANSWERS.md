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

<!-- Điền sau khi hoàn thành CP2: 4 câu hỏi Dockerfile, kết quả gọi container, size 2 image + %, sơ đồ stack, test Nginx. -->

---

## Part 3 — Cloud Deployment

<!-- Điền sau khi hoàn thành CP6: URL public, so sánh railway.toml/render.yaml, mô tả pipeline Cloud Run. -->

---

## Part 4 — API Security

<!-- Điền sau khi hoàn thành CP3: output curl 401/200/429 (che token), giải thích cost guard. -->

---

## Part 5 — Scaling & Reliability

<!-- Điền sau khi hoàn thành CP4: health/ready, graceful shutdown, test_stateless, giải thích stateless. -->

---

## Part 6 — Final Project

### Kết quả `check_production_ready.py`

<!-- Dán phần "📋 Checklist Deliverable" của output khi đạt PASS 12/12. -->

```text
(chưa chạy)
```

---

## AI log

| Lần | Ngày | Hỏi gì | Nhận gì | Tự sửa và tự kiểm tra thế nào |
|---:|---|---|---|---|
| 1 | 25/11/2026 | Nhờ AI thực hiện CP1: đọc anti-pattern, chạy bản develop/production, viết Part 1 | AI chạy develop ở cổng 8010 và production ở 8000, thu output thật; gợi ý 12 anti-pattern và bảng so sánh 12 dòng | Đọc lại `develop/app.py` và `production/app.py` để đối chiếu số dòng; kiểm tra output `curl` khớp với file JSON ghi nhận; tự chạy lại lệnh khi cần |

> Ghi chú: sinh viên cần đọc lại toàn bộ câu trả lời, tự chạy lại ít nhất một lần và chỉnh AI log cho đúng với những gì mình thực sự kiểm tra trước khi nộp.
