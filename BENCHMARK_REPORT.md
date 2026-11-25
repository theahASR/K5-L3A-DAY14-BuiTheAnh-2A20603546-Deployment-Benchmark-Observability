# Benchmark & Observability Report — Day 14

> Báo cáo Benchmark & Observability — mọi số liệu lấy từ report JSON/CSV/screenshot thật, không ước lượng.

**Họ tên:** Bùi Thế Anh  
**MSSV:** 2A20603546  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Windows 11 + WSL2 Ubuntu, Python 3.14, Docker Desktop 28.5.1; Part 7 Bước 1 chạy agent local (không Docker), Bước 2 chạy stack Docker Compose (Prometheus/Grafana/Jaeger/Locust)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Người dùng cảm nhận được độ trễ; p95 đại diện cho phần lớn request, không bị average che giấu tail latency |
| Error rate `/ask` | < 2 % | Giữ error budget cho lỗi upstream LLM/mock (khoảng 1%) và sự cố ngắn; vượt 2% là bất thường |
| Accuracy trên golden dataset | ≥ 80 % | Mức tối thiểu để agent hữu ích; quality gate mặc định của `run_eval.py`; sau khi sửa KB đạt 100% |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.96 | 193.9 | 226.8 | 1713.5 | 0.33% | ✅ PASS |
| 10 | 35.01 | 196.5 | 236.5 | 1704.6 | 1.00% | ✅ PASS |
| 50 | 89.64 | 229.4 | 763.2 | 1723.8 | 1.67% | ❌ FAIL (p95) |
| 100 | 51.78 | 801.8 | 5043.1 | 5357.2 | 1.67% | ❌ FAIL (p95) |

**Nhận xét:** RPS **không tăng tuyến tính** mãi. Từ 1 → 10 → 50, RPS tăng mạnh (3,96 → 35,0 → 89,6 req/s) nhờ các request async được xử lý song song. Nhưng ở concurrency 100, RPS **giảm còn 51,8 req/s** và p95 tăng lên **5.043 ms**: server một process bị quá tải, hàng đợi tăng, tail latency bùng nổ. Đây là dấu hiệu cần scale thêm instance/worker hoặc giảm tải; không thể chỉ tăng concurrency.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 200.7 | 244.5 | 265.7 |
| 0.03 (mặc định) | 229.5 | 237.8 | 1685.0 |
| 0.1 | 381.9 | 1700.8 | 1727.9 |

**Nhận xét:** **p99 là chỉ số nhạy nhất** với request chậm. Ở mức 0.03 (3% request bị chậm thêm 1,5 giây), average chỉ tăng từ 200,7 → 229,5 ms và p95 gần như không đổi (237,8 ms), nhưng **p99 nhảy lên 1.685 ms**. Ở mức 0.1, p95 mới bắt đầu nhảy (1.700,8 ms). Vì vậy SLO không nên đặt theo average: average che giấu tail latency — đúng lúc một nhóm nhỏ người dùng chờ rất lâu.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | **100.0% (23/23)** |
| Avg tokens / câu | 56.8 | 108.7 | 114.5 |
| Tổng cost (USD) | 0.000400 | 0.000756 | 0.000798 |
| Cost / câu đúng (USD) | 0.00039975 | 0.00003599 | **0.00003469** |
| Quality gate | ❌ FAIL (accuracy < 80%) | ✅ PASS | ✅ PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `["jwt"]` vào `KNOWLEDGE_BASE` với nội dung: JWT là token có chữ ký (signature) và thời hạn hết hạn; server verify chữ ký. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `["kubernetes", "hpa", "horizontal pod autoscaler"]` với nội dung: HPA scale dựa trên CPU, memory và custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- v2 có retrieval (RAG) nên prompt dài hơn: **108,7 token/câu** so với 56,8 của v1, tổng cost tăng từ $0,000400 → $0,000756.
- Nhưng accuracy tăng từ **4,3% → 91,3%** (+87 điểm %), và **cost / câu trả lời đúng giảm ~11 lần** (0,00039975 → 0,00003599 USD). Đây là lý do nên so sánh bằng “cost / câu đúng”, không chỉ “cost / câu”.
- Latency p95 tăng nhẹ (191,9 → 221,9 ms) do thêm bước retrieval; đổi lại chất lượng cao hơn nhiều.
- Sau khi bổ sung KB cho 2 câu thiếu, v2 đạt **23/23 (100%)**, không regression; cost/câu đúng tiếp tục giảm nhẹ xuống 0,00003469 USD.

**CI quality gate:** workflow `.github/workflows/quality-gate.yml` chạy `eval/run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json`. `run_eval.py` trả exit code 1 khi accuracy dưới ngưỡng hoặc có regression, làm step GitHub Actions fail và chặn merge.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải — `screenshots/grafana-dashboard.png` (52.7 req/s, p95 1.60s)
- [x] Một trace chậm trong Jaeger — `screenshots/jaeger-slow-trace.png` (trace `ad331b8b...`, chat span 1665ms)
- [x] Một trace lỗi trong Jaeger — `screenshots/jaeger-error-trace.png` (HTTP 503, span `chat` có error + exception)
- [x] Trang Alerts của Prometheus với 2 alert đang **firing** — `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` (chạy cùng B) | `AgentHighErrorRate` | ~1m49s (109s; pending ~49s + for 1m) | Error rate (%) |
| B | `MOCK_SLOW_RATE=0.3` (chạy cùng A) | `AgentHighLatencyP95` | ~2m54s (174s; pending ~54s + for 2m) | Latency p95 / p99 |
| C | `LLM_MODEL=mock-llm-large` | Không chạy trong buổi lab | — | Cost burn rate (dự kiến) |
| D | `docker pause` 1 instance | Không chạy trong buổi lab | — | Instances up (dự kiến) |
| E | `AGENT_VERSION=v1` | **Không có alert** | — | Version/retrieval hit ratio; chất lượng không làm metric hạ tầng đỏ |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Dùng **eval chất lượng** trên golden dataset và quality gate trong CI: v1 chỉ đạt 4.3% (1/23) so với v2 91.3% (21/23), chênh lệch rất lớn dù error rate/latency hạ tầng vẫn xanh. Ngoài ra có thể dùng synthetic check theo bộ câu hỏi cố định, canary + so sánh accuracy giữa hai phiên bản, user feedback, hoặc LLM-as-judge. Đây là lý do phải benchmark **chất lượng** tách khỏi benchmark **hiệu năng**.

**Thí nghiệm A+B (đã chạy):** đổi `.env` lúc `16:22:03Z`, chạy Locust 30 user trong 3 phút. Prometheus ghi nhận:
- `AgentHighErrorRate` active lúc `16:22:52Z`, firing sau `for: 1m` → ~1m49s từ lúc đổi.
- `AgentHighLatencyP95` active lúc `16:22:57Z`, firing sau `for: 2m` → ~2m54s từ lúc đổi.
- Ảnh `prometheus-alert-firing.png` chụp cả 2 alert ở trạng thái **FIRING**.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được:

- `trace_id`: `ad331b8b340ab69947158d5a07066be7`
- Tổng thời gian: **1968.9 ms**
- Span chiếm nhiều thời gian nhất: **`chat mock-llm-small` — 1665.2 ms (~84.6% tổng trace)**
- Các span còn lại: `agent.run` 1753.7 ms, `agent.retrieve_context` 88.3 ms, `POST /ask` 1968.9 ms.

Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T16:15:09.132437+00:00", "level": "INFO", "service": "observable-agent", "instance": "33e32e24cce0", "event": "llm_call", "trace_id": "ad331b8b340ab69947158d5a07066be7", "span_id": "c2d36d32daa62594", "request_id": "098b06729180", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 72, "output_tokens": 40, "cost_usd": 3.5e-05, "llm_ms": 1663.9}
```

**Trace lỗi:** `91931bdbc2b3a91e792e71612a4b8a85` — tổng 235.3 ms, span `chat mock-llm-small` 96.5 ms có `status.code=ERROR` và event `exception`:

```json
{"ts": "2026-11-25T16:15:12.096741+00:00", "level": "INFO", "service": "observable-agent", "instance": "216c8a44e8ea", "event": "llm_error", "trace_id": "91931bdbc2b3a91e792e71612a4b8a85", "span_id": "72fd8e33c9caa85f", "request_id": "089a6c3f51e5", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 45.04 | 250 | 2500 | 3700 | 57 (1.07%) |
| 3 | 52.17 | 220 | 1700 | 2200 | 75 (1.22%) |

**Giải thích kết quả:** Scale từ 1 → 3 instance cải thiện rõ p95 (**2500 → 1700 ms, giảm ~32%**), p99 (**3700 → 2200 ms, giảm ~41%**) và p50 (250 → 220 ms); RPS tăng từ 45,0 → 52,2 req/s (~16%), không tuyến tính. Nút thắt chính nằm ở **LLM upstream**: trace chậm nhất cho thấy `chat mock-llm-small` chiếm 1665/1969 ms (~85%); scale thêm agent không làm LLM nhanh hơn. Ngoài ra mock LLM cố tình trả ~1% lỗi 503 nên failures vẫn còn. Muốn cải thiện tiếp cần cache/async, tăng capacity hoặc giảm độ dài prompt/model.

---

## 6. Kết luận

- 3 điều học được về benchmark & observability:
  1. **Không nhìn average**: p95/p99 mới phản ánh tail latency; `MOCK_SLOW_RATE=0.03` làm p99 nhảy lên 1.685 ms trong khi average chỉ 229,5 ms. SLO phải đặt theo percentile.
  2. **Hiệu năng và chất lượng là hai bài toán khác nhau**: v2 có p95/latency/error rate đẹp nhưng nếu không eval thì không biết accuracy chỉ 91,3%; quality gate + golden dataset bắt được regression mà dashboard hạ tầng không thấy.
  3. **Observability phải có cả 3 trụ cột**: metrics chỉ ra “có vấn đề”, trace chỉ ra “chậm ở span nào” (`chat` 1665 ms), log JSON có `trace_id` nối trace với sự kiện cụ thể; alert cần `for` để tránh báo động giả.
- Nếu đưa agent này lên production thật, mình sẽ thêm:
  - Alert theo **error rate / p95 của Nginx** (bao gồm 502/504 từ LB) vì metric của agent không thấy lỗi xảy ra ở tầng proxy.
  - Alert **cost/token theo user** và **retrieval hit ratio**; quality gate eval trong CI trước mỗi deploy.
  - **Synthetic check** định kỳ bằng bộ câu hỏi golden; **canary** so sánh accuracy/latency giữa hai phiên bản.
  - Metric **queue depth / in-flight requests** và **LLM provider error rate** để phân biệt quá tải agent với lỗi upstream.
  - Alert **error budget burn rate** theo SLO thay vì chỉ ngưỡng tức thời.
