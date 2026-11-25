# Benchmark & Observability Report — Day 14

> Báo cáo Benchmark & Observability — mọi số liệu lấy từ report JSON/CSV/screenshot thật, không ước lượng.

**Họ tên:** Bùi Thế Anh  
**MSSV:** 2A20603546  
**Ngày chạy:** 25/11/2026  
**Môi trường:** Windows 11 + WSL2 Ubuntu, Python 3.14, Docker Desktop 28.5.1; agent chạy local (không Docker) cho Part 7 Bước 1

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

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
