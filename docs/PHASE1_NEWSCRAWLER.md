# Phase 1 — Chi tiết triển khai NewsCrawler / RSS

> Tài liệu này mô tả chi tiết cách triển khai **module thu thập dữ liệu sự kiện** từ các nguồn tin tức và RSS phục vụ Cognitive Traffic Analytics Platform. Module này chịu trách nhiệm phát hiện và đưa vào hệ thống các sự kiện có khả năng ảnh hưởng tới giao thông như **tai nạn, ngập lụt, sửa đường, lễ hội, sự kiện đông người** tại Hà Nội và TP.HCM.

---

## 1. Mục tiêu

- Thu thập tin tức và RSS từ các nguồn công khai về giao thông Việt Nam.
- Trích xuất sự kiện ảnh hưởng giao thông (loại, vị trí, thời gian, mức độ).
- **Geocoding địa danh tiếng Việt** → toạ độ (latitude, longitude) → ánh xạ với đoạn đường OSM gần nhất.
- Đẩy sự kiện vào Kafka topic `events.news` để xử lý downstream.
- Lưu dữ liệu thô vào tầng **Bronze** của lakehouse phục vụ replay và audit.

---

## 2. Phạm vi nguồn dữ liệu

Module chia nguồn dữ liệu thành ba nhóm theo thứ tự ưu tiên:

| Nhóm | Mô tả | Ví dụ nguồn |
|------|-------|-------------|
| **A. RSS feed** | Ưu tiên cao nhất — có schema rõ ràng, hợp pháp, ổn định | VnExpress mục Giao thông, Tuổi Trẻ, Dân Trí, Thanh Niên, VietnamNet |
| **B. HTML page** | Site không có RSS hoặc cần nội dung chi tiết hơn snippet RSS | Báo Giao thông, ANTĐ, Zing/Znews, 24h.com.vn |
| **C. API công khai** | Khi có (hiếm) — ưu tiên cao nhất về độ tin cậy | VOV Giao thông API (nếu có), OpenData portal |

> **Lưu ý:** Không scrape các mạng xã hội (Facebook, Zalo, Twitter) trong phạm vi đề tài vì vướng ToS và xác thực phức tạp.

---

## 3. Kiến trúc tổng quan của module

```
[Source list (YAML)]
        │
        ▼
┌──────────────────┐     ┌──────────────────┐
│  RSS Fetcher     │ ──► │  HTML Scraper    │  (fallback / detail fetch)
└──────────────────┘     └──────────────────┘
        │                          │
        └────────────┬─────────────┘
                     ▼
            ┌────────────────────┐
            │  Article Parser    │  (trafilatura / readability)
            └────────────────────┘
                     │
                     ▼
            ┌────────────────────┐
            │  Deduplicator      │  (URL hash + content fingerprint)
            └────────────────────┘
                     │
                     ▼
            ┌────────────────────┐
            │  NLP Pipeline      │  (event classification + NER tiếng Việt)
            └────────────────────┘
                     │
                     ▼
            ┌────────────────────┐
            │  Geocoder          │  (Nominatim/OSM + cache)
            └────────────────────┘
                     │
            ┌────────┴─────────┐
            ▼                  ▼
   ┌────────────────┐  ┌────────────────────┐
   │ Kafka Producer │  │ Bronze Iceberg     │
   │ events.news    │  │ bronze_events_raw  │
   └────────────────┘  └────────────────────┘
```

Toàn bộ pipeline được đóng gói thành Docker container và lập lịch bằng **Airflow DAG** chạy định kỳ (ví dụ mỗi 10–15 phút cho RSS, mỗi 30–60 phút cho HTML).

---

## 4. Các bước implement chi tiết

### 4.1 Khảo sát và quản lý danh sách nguồn

**Mục tiêu:** Có một file cấu hình duy nhất, dễ cập nhật khi thêm/bớt nguồn.

**Cách làm:**

1. Khảo sát thủ công từng site: tìm trang RSS (thường ở `/rss`, `/feed`, hoặc footer), kiểm tra tần suất cập nhật, cấu trúc HTML, sự tồn tại của `robots.txt`.
2. Tạo file `sources.yaml`:

```yaml
sources:
  - name: vnexpress_giaothong
    type: rss
    url: https://vnexpress.net/rss/giao-thong.rss
    poll_interval_sec: 600
    enabled: true
  - name: baogiaothong_hanoi
    type: html
    url: https://www.baogiaothong.vn/ha-noi/
    article_selector: "article.story"
    title_selector: "h2.story__title"
    link_selector: "a"
    poll_interval_sec: 1800
    enabled: true
```

3. Validate file YAML bằng schema khi khởi động (dùng `pydantic` hoặc `cerberus`).

---

### 4.2 RSS Fetcher

**Mục tiêu:** Lấy danh sách bài viết mới từ các RSS feed một cách hiệu quả.

**Cách làm:**

1. Dùng thư viện **`feedparser`** để parse RSS/Atom.
2. Lưu trạng thái phiên lấy gần nhất (`last_etag`, `last_modified`) trong Redis hoặc bảng metadata để gửi header `If-None-Match` / `If-Modified-Since` → tiết kiệm băng thông và tránh trùng.
3. Với mỗi entry, trích xuất:
   - `guid` hoặc `link` (làm `external_id`).
   - `title`, `summary`, `published_at` (chuẩn hoá về UTC).
   - `categories`/`tags` nếu có.
4. Filter sơ bộ bằng từ khoá (`tai nạn`, `ùn tắc`, `ngập`, `sửa đường`, `cấm đường`, `phân luồng`, `hội chợ`, `lễ hội`, ...) để loại bớt bài không liên quan trước khi tốn công xử lý sâu hơn.

```python
import feedparser, hashlib

def fetch_rss(url, last_etag=None, last_modified=None):
    fp = feedparser.parse(url, etag=last_etag, modified=last_modified)
    if fp.status == 304:
        return [], fp.etag, fp.modified
    entries = []
    for e in fp.entries:
        eid = e.get("id") or e.get("link")
        entries.append({
            "external_id": hashlib.sha1(eid.encode()).hexdigest(),
            "title": e.title,
            "summary": e.get("summary", ""),
            "link": e.link,
            "published_at": e.get("published_parsed"),
        })
    return entries, fp.etag, fp.modified
```

---

### 4.3 HTML Scraper (fallback / lấy nội dung chi tiết)

**Mục tiêu:** Lấy nội dung đầy đủ của bài viết (RSS thường chỉ có summary).

**Cách làm:**

1. Dùng **`httpx`** (async) hoặc **`requests`** với:
   - **User-Agent** mô tả crawler (kèm email liên hệ).
   - **Rate limit per domain** (1–2 req/s) bằng `asyncio.Semaphore` hoặc `aiolimiter`.
   - **Retry với exponential backoff** (dùng `tenacity`).
   - Kiểm tra `robots.txt` bằng `urllib.robotparser` trước khi crawl.
2. Trích nội dung sạch bằng **`trafilatura`** (hoặc `readability-lxml`) — xử lý tốt báo Việt Nam, loại bỏ menu/quảng cáo/comment.
3. Khi cần extract có cấu trúc (vd. ngày đăng nằm trong meta tag riêng), dùng selector trong `sources.yaml` thay vì viết hard-code.

```python
import trafilatura
html = httpx.get(url, headers=HEADERS, timeout=15).text
content = trafilatura.extract(html, include_comments=False, favor_recall=False)
```

---

### 4.4 Deduplication

**Mục tiêu:** Một sự kiện thường được nhiều báo đăng lại — chỉ giữ một bản ghi đại diện.

**Cách làm theo 3 lớp:**

1. **Lớp URL:** chuẩn hoá URL (bỏ tracking params `utm_*`, `fbclid`, slash cuối) → hash SHA-1 → kiểm tra trong Redis set `seen_urls` (TTL 30 ngày).
2. **Lớp tiêu đề:** sau khi normalize (lowercase, bỏ dấu, bỏ stopword), so sánh similarity bằng **MinHash + LSH** (`datasketch`) với ngưỡng ~0.8.
3. **Lớp nội dung:** SimHash trên 1000 ký tự đầu tiên của bài để bắt trường hợp tiêu đề khác nhưng nội dung gần giống nhau.

Khi phát hiện trùng, **giữ bản đầu tiên** và ghi nhận thêm nguồn vào field `mirrored_sources` để tăng `event_confidence`.

---

### 4.5 NLP Pipeline cho tiếng Việt

**Mục tiêu:** Phân loại loại sự kiện và trích xuất thực thể (địa điểm, thời gian).

#### 4.5.1 Tiền xử lý

- Tokenize bằng **`underthesea`** hoặc **`pyvi`** (xử lý từ ghép tiếng Việt: `Hà_Nội`, `quận_Hoàn_Kiếm`).
- Loại bỏ HTML entity, ký tự lạ, normalize Unicode về NFC.

#### 4.5.2 Event Classification

Hai cách kết hợp, ưu tiên rule-based vì rẻ và đủ chính xác cho phạm vi đề tài:

**(a) Rule-based (mức nền):** từ điển từ khoá theo loại:

| event_type | Từ khoá đại diện |
|------------|------------------|
| `accident` | tai nạn, va chạm, lật xe, đâm vào, đụng nhau |
| `flood` | ngập, ngập sâu, ngập lụt, mưa lớn gây ngập |
| `road_work` | sửa đường, thi công, rào chắn, cấm đường, phân luồng |
| `event` | lễ hội, hội chợ, sự kiện, biểu diễn, countdown |
| `weather` | bão, gió mạnh, sương mù dày |
| `other` | (mặc định) |

**(b) ML classifier (tuỳ chọn):** fine-tune **PhoBERT-base** trên ~1.000 bài đã gán nhãn thủ công nếu thời gian cho phép. Lưu vào MLflow như một model độc lập (`news-event-classifier`).

#### 4.5.3 Named Entity Recognition

- Dùng **`VnCoreNLP`** hoặc **`underthesea.ner`** để trích xuất các thực thể loại `LOC` (location).
- Bổ sung **dictionary-based matcher** với danh sách quận/huyện/phường, tên đường lớn của Hà Nội và TP.HCM (lấy từ OpenStreetMap đã import ở module OSM) để tăng recall.
- Trích thời gian bằng `dateparser` (hỗ trợ tiếng Việt: "sáng nay", "chiều qua", "lúc 7h30 ngày 12/3").

#### 4.5.4 Severity scoring

Sinh điểm `severity` 0–3 dựa trên keyword:

- `severity=3`: "chết người", "tử vong", "tắc nghiêm trọng", "kẹt nhiều giờ".
- `severity=2`: "ùn tắc kéo dài", "phương tiện dồn ứ", "ngập sâu".
- `severity=1`: "ùn ứ cục bộ", "lưu thông chậm".
- `severity=0`: chỉ là tin sự kiện, chưa có dấu hiệu ảnh hưởng giao thông rõ.

---

### 4.6 Geocoding địa danh tiếng Việt

**Mục tiêu:** Chuyển chuỗi vị trí (vd. `"ngã tư Khuất Duy Tiến – Nguyễn Trãi, Thanh Xuân, Hà Nội"`) thành `(lat, lon)` và ánh xạ tới `segment_id` gần nhất.

**Cách làm:**

1. **Chuẩn hoá location string:** ghép các entity LOC tìm được, thêm hậu tố thành phố nếu thiếu (vd. `"... , Hà Nội"`).
2. **Cache trước, gọi sau:** kiểm tra Redis (`geocode:<normalized_string>`) — TTL 30 ngày.
3. **Geocoder chính:** **Nominatim self-host** (chạy Docker container `mediagis/nominatim`) trỏ tới file OSM Việt Nam đã import ở module OSM. Self-host quan trọng vì:
   - Tránh rate limit của Nominatim public (1 req/s).
   - Hỗ trợ tiếng Việt tốt hơn nếu import đúng file OSM khu vực.
4. **Fallback geocoder:** `geopy` với public Nominatim (rate-limited 1 req/s), chỉ dùng khi self-host miss.
5. **Snap to road:** với toạ độ thu được, tìm `way_id` / `segment_id` gần nhất trong bảng OSM đã import (dùng PostGIS `ST_Distance` hoặc thư viện `shapely` + Rtree index).
6. Sinh `event_confidence` dựa trên:
   - Mức cụ thể của địa danh (ngã tư > tên đường > tên quận > tên thành phố).
   - Khoảng cách snap (< 50m: 1.0; 50–200m: 0.7; > 200m: 0.4).
   - Số nguồn đưa cùng một sự kiện (bonus).

```python
def geocode(location_str):
    cached = redis.get(f"geocode:{location_str}")
    if cached: return json.loads(cached)
    res = requests.get(NOMINATIM_URL, params={
        "q": location_str, "format": "json", "limit": 1,
        "countrycodes": "vn", "accept-language": "vi"
    }).json()
    if not res: return None
    out = {"lat": float(res[0]["lat"]), "lon": float(res[0]["lon"])}
    redis.setex(f"geocode:{location_str}", 30*86400, json.dumps(out))
    return out
```

---

### 4.7 Cấu trúc message gửi vào Kafka topic `events.news`

```json
{
  "event_id": "ev_2026052914_a1b2c3",
  "source": "vnexpress_giaothong",
  "source_url": "https://vnexpress.net/...",
  "crawled_at": "2026-05-29T07:42:11Z",
  "published_at": "2026-05-29T07:30:00Z",
  "title": "Ùn tắc kéo dài trên cầu Nhật Tân do va chạm hai ôtô",
  "content": "...",
  "event_type": "accident",
  "severity": 2,
  "location_entity": "cầu Nhật Tân, Hà Nội",
  "lat": 21.0833,
  "lon": 105.8167,
  "snapped_segment_id": "osm_way_27543891",
  "snap_distance_m": 18.4,
  "event_confidence": 0.86,
  "city": "Ha Noi",
  "mirrored_sources": ["tuoitre", "dantri"],
  "raw_html_path": "s3://warehouse/bronze/events_raw/2026/05/29/ev_2026052914_a1b2c3.html.gz"
}
```

**Schema Registry:** đăng ký schema này (Avro hoặc JSON Schema) trước khi producer publish — đảm bảo downstream luôn parse được.

---

### 4.8 Ghi xuống tầng Bronze

- Spark Structured Streaming consume topic `events.news` → ghi vào bảng Iceberg `bronze_events_raw`.
- Partition theo `city`, `date`.
- Lưu thêm **HTML gốc** dưới dạng file gzipped trong MinIO bucket `warehouse/bronze/events_raw/...` để có thể re-parse nếu rule NLP thay đổi mà không cần crawl lại.

---

### 4.9 Lập lịch bằng Airflow

Tạo DAG `dag_newscrawler` với cấu trúc:

```
load_sources_yaml
        │
        ▼
   ┌────────────────────────────────────────┐
   │  TaskGroup: fetch_per_source           │
   │  (dynamic mapping theo sources.yaml)   │
   │   - fetch_rss / fetch_html             │
   │   - parse_articles                     │
   │   - dedup                              │
   │   - nlp_extract                        │
   │   - geocode                            │
   │   - produce_to_kafka                   │
   └────────────────────────────────────────┘
        │
        ▼
  emit_metrics_to_prometheus
```

- **Schedule:** `*/10 * * * *` cho RSS, riêng task HTML scraper chạy `*/30 * * * *`.
- **Concurrency:** giới hạn `max_active_runs=1` để tránh chồng lấn.
- **SLA:** mỗi run < 5 phút; nếu vượt, gửi cảnh báo qua Grafana/Alertmanager.

---

## 5. Xử lý lỗi và tuân thủ

| Vấn đề | Cách xử lý |
|--------|-----------|
| Site đổi cấu trúc HTML | Selector trong `sources.yaml`; khi parser trả về rỗng quá ngưỡng → ghi cảnh báo và tự `disable` nguồn đó. |
| Bị chặn IP | Đặt User-Agent rõ ràng, có email liên hệ; tôn trọng `robots.txt`; giữ rate thấp; thêm jitter giữa các request. |
| Bài lỗi encoding | Force UTF-8, fallback `chardet`; normalize Unicode NFC. |
| Bản tin trùng nhiều giờ sau | Dedup TTL 30 ngày; khi trùng, chỉ append `mirrored_sources` thay vì tạo bản ghi mới. |
| Geocoding sai địa danh trùng tên | Luôn ép `countrycodes=vn`, ưu tiên thêm tên thành phố vào query; sinh `event_confidence` thấp khi snap distance lớn. |
| Lỗi API Nominatim | Retry 3 lần với backoff; nếu vẫn lỗi → ghi nhận `geocode_status="failed"` và vẫn lưu bản ghi (Silver layer sẽ filter sau). |

---

## 6. Kiểm thử

1. **Unit test:**
   - Parser RSS với fixture file `.xml` của từng nguồn.
   - Rule-based classifier với 50–100 câu mẫu mỗi loại.
   - Geocoder với cache mock.
2. **Integration test:**
   - Crawl thử 1 giờ, đếm số bài unique vs duplicate.
   - Kiểm tra producer ghi đúng schema bằng Schema Registry compatibility test.
3. **Manual evaluation:** chọn ngẫu nhiên 100 sự kiện, đánh giá thủ công độ chính xác `event_type` và `lat/lon`. Đặt mục tiêu: precision ≥ 0.85 cho `accident` và `road_work`.

---

## 7. Definition of Done

- [ ] File `sources.yaml` có tối thiểu 6 nguồn RSS đã verify hoạt động.
- [ ] DAG `dag_newscrawler` chạy ổn định 24h, không lỗi quá 1% task.
- [ ] Kafka topic `events.news` nhận trung bình ≥ 20 sự kiện/ngày cho mỗi thành phố (Hà Nội, TP.HCM).
- [ ] Bảng Iceberg `bronze_events_raw` truy vấn được từ Trino, partition đúng.
- [ ] Tỉ lệ dedup hợp lý: > 95% URL unique sau lớp 1; tỉ lệ phát hiện trùng tiêu đề/nội dung > 10% (chứng tỏ lớp 2–3 hữu ích).
- [ ] Geocoding thành công ≥ 80% sự kiện có `location_entity` không rỗng.
- [ ] Precision phân loại sự kiện ≥ 0.85 trên tập đánh giá thủ công.
- [ ] Có dashboard Grafana hiển thị: số sự kiện/giờ theo nguồn, tỉ lệ lỗi, latency crawl trung bình.

---

## 8. Định hướng mở rộng

- Bổ sung **NER fine-tune trên domain giao thông Việt Nam** (gán nhãn tên cầu, hầm, nút giao đặc thù) để tăng recall geocoding.
- Tích hợp **PhoBERT classifier** thay rule-based khi có đủ dữ liệu gán nhãn.
- Thêm **image OCR** cho ảnh tin tức (biển báo, biển cấm đường) bằng VietOCR — phục vụ phát hiện sửa đường có thông báo bằng hình ảnh.
- Tự động sinh **alert mầm** từ tin tức có `severity ≥ 2` và confidence cao, đẩy thẳng sang topic `traffic.alerts`.
