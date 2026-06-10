# Kế hoạch Implement — Cognitive Traffic Analytics Platform

**Nhóm 09** | Môn: Kỹ thuật và công nghệ dữ liệu lớn | Hà Nội, 2026

---

## Tech Stack

### Data Ingestion & Streaming

| Công nghệ | Version | Vai trò | Ghi chú |
|-----------|---------|---------|---------|
| **Apache Kafka** | 3.6+ | Message broker trung tâm | Nhận toàn bộ luồng real-time từ producers |
| **Confluent Schema Registry** | 7.5+ | Validate & version schema Avro/JSON | Đảm bảo message format nhất quán giữa producers và consumers |
| **Python Kafka Producer** (`confluent-kafka`) | 2.3+ | Viết producers polling TomTom, OWM, RSS | Có retry logic + dead letter queue |
| **Apache Airflow** | 2.8+ | Orchestrate batch ingestion + pipeline scheduling | Dùng cho TomTom Stats async, OSM import, retraining |

### Stream & Batch Processing

| Công nghệ | Version | Vai trò | Ghi chú |
|-----------|---------|---------|---------|
| **Apache Spark** | 3.5+ | Stream processing + batch ETL + feature engineering | Spark Structured Streaming đọc Kafka → ghi Iceberg |
| **PySpark** | 3.5+ | Python API cho Spark jobs | Viết cleaning jobs, feature engineering |
| **Apache Iceberg** | 1.5+ | Table format cho Lakehouse | Schema evolution, time travel, partitioning, snapshot |

### Storage

| Công nghệ | Version | Vai trò | Ghi chú |
|-----------|---------|---------|---------|
| **MinIO** | RELEASE.2024+ | Object storage tương thích S3 | Lưu toàn bộ Bronze/Silver/Gold Parquet files |
| **Hive Metastore** | 3.1+ | Iceberg catalog — quản lý metadata & schema | Backend là PostgreSQL |
| **PostgreSQL** | 15+ | Backend cho Hive Metastore + Airflow metadata DB | |
| **Redis** | 7.2+ | In-memory cache | Cache real-time traffic state (TTL 1 phút), prediction cache (TTL 5 phút) |
| **Neo4j** | 5.x | Graph database | Lưu road network từ OSM; graph analytics: centrality, congestion propagation |

### Query & Serving

| Công nghệ | Version | Vai trò | Ghi chú |
|-----------|---------|---------|---------|
| **Trino** | 435+ | Distributed SQL query engine | Truy vấn trực tiếp Iceberg tables → phục vụ Superset + ad-hoc |
| **FastAPI** | 0.111+ | REST API backend | Serve predictions, alerts, SHAP explanation, routing |
| **Uvicorn** | 0.29+ | ASGI server cho FastAPI | |

### AI & ML

| Công nghệ | Version | Vai trò | Ghi chú |
|-----------|---------|---------|---------|
| **LightGBM** | 4.3+ | Dự báo tốc độ giao thông (horizon 15/60/240 phút) | Nhanh, interpretable, phù hợp tabular data |
| **scikit-learn** | 1.4+ | DBSCAN hotspot clustering, preprocessing, evaluation | |
| **SHAP** | 0.45+ | Explainability — giải thích top features ảnh hưởng dự báo | |
| **MLflow** | 2.12+ | Experiment tracking, model registry, deployment lifecycle | |
| **OSMnx** | 1.9+ | Download + parse OSM road network thành NetworkX graph | |
| **NetworkX** | 3.3+ | Tính centrality, graph features từ road network | |

### Frontend

| Công nghệ | Version | Vai trò | Ghi chú |
|-----------|---------|---------|---------|
| **Next.js** | 14+ (App Router) | Framework chính | Mix Server Components + Client Components |
| **TypeScript** | 5+ | Type safety toàn bộ frontend | |
| **Tailwind CSS** | 3.4+ | Utility-first styling | |
| **shadcn/ui** | latest | Component library | |
| **Recharts** | 2.12+ | Charts | TrafficTrend, ForecastChart, SHAP bar, Latency |
| **Leaflet + react-leaflet** | 1.9 / 4.2+ | Map thật với OSM tiles | Segment polylines + hotspot circles |
| **SWR** | 2.2+ | Real-time polling | `/traffic/current` 60s · `/alerts/active` 30s |
| **TanStack Query** | 5+ | Cached data fetching | Forecast, SHAP explanation |
| **Zustand** | 4.5+ | Global state | selectedCity, selectedSegment, filters |
| **Axios** | 1.6+ | HTTP client | Base instance với interceptors |

### Visualization & Monitoring

| Công nghệ | Version | Vai trò | Ghi chú |
|-----------|---------|---------|---------|
| **Apache Superset** | 3.1+ | BI dashboard — heatmap, trend charts, báo cáo | Kết nối qua Trino |
| **Grafana** | 10.4+ | Infrastructure + pipeline monitoring | Hiển thị Kafka lag, Spark duration, MAE/RMSE trend |
| **Prometheus** | 2.51+ | Metrics scraping | Scrape Kafka JMX, Spark metrics, custom app metrics |

### Infrastructure & DevOps

| Công nghệ | Version | Vai trò | Ghi chú |
|-----------|---------|---------|---------|
| **Docker** | 25+ | Container runtime | |
| **Docker Compose** | 2.24+ | Orchestrate toàn bộ stack locally | Entry point chính cho demo và development |
| **Kubernetes** | 1.29+ | Production deployment (tương lai) | Migrate từ Docker Compose khi cần scale |

### External APIs & Data Sources

| Nguồn | Loại | Dữ liệu | Cơ chế |
|-------|------|---------|--------|
| **TomTom Flow API** | REST, polling | Real-time traffic speed, jamFactor | 5–30 phút/lần |
| **TomTom Traffic Stats** | REST async | Historical baseline p15/p50/p85 | Airflow DAG theo lịch |
| **OpenWeatherMap API** | REST, polling | Temp, rain, humidity, visibility | 15–60 phút/lần |
| **OpenStreetMap** | Batch PBF | Road network topology, geometry | Import 1 lần + cập nhật định kỳ |
| **NewsCrawler / RSS** | Web scraping | Tai nạn, ngập lụt, sự kiện | Crawl định kỳ + geocoding tiếng Việt |
| **MeTS-10 Bangkok** | Batch download | Traffic dataset Đông Nam Á | Pretrain + transfer learning |
| **PEMS-BAY** | HuggingFace datasets | Benchmark dataset quốc tế | Kiểm thử pipeline + đánh giá model |
| **HCMC Traffic Flow** | Batch CSV (Kaggle) | Traffic data TP.HCM | Fine-tune model cho HCM |
| **Hanoi Traffic Stats** | Tích lũy từ TomTom Flow polling | Dữ liệu giao thông Hà Nội tự thu thập | Training data dài hạn; lưu vào Gold feature/training table |

---

## Tổng quan

| Phase | Tên | Trạng thái | Thời gian |
|-------|-----|-----------|-----------|
| Phase 1 | Hạ tầng & Data Ingestion nền | ✅ Hoàn thành | ~3 giờ thực tế |
| Phase 2 | Data Cleaning & Silver Layer | 🔲 Chưa bắt đầu | 2 tuần |
| Phase 3 | Feature Engineering & Gold Layer | 🔲 Chưa bắt đầu | 2–3 tuần |
| Phase 4 | AI Analytics: DBSCAN, SHAP, Transfer Learning | 🔲 Chưa bắt đầu | 2 tuần |
| Phase 5 | Serving Layer, Dashboard & Observability | 🔲 Chưa bắt đầu | 2 tuần |
| Phase 6 | Frontend Connection | 🔲 Chưa bắt đầu | 1 tuần |

**Tổng cộng:** ~10–12 tuần

---

## Folder Structure

```
cognitive-traffic-analytics/
│
├── docker-compose.yml
├── Makefile
├── README.md
├── .env
├── .env.example
│
├── frontend/                           # Next.js 14 App Router — UI đã dựng sẵn, chưa connect
│
├── infra/
│   ├── kafka/
│   │   ├── create-topics.sh
│   │   └── schema-registry/
│   │       ├── traffic-realtime.avsc
│   │       ├── weather-current.avsc
│   │       └── events-news.avsc
│   ├── spark/
│   │   ├── spark-defaults.conf
│   │   └── log4j2.properties
│   ├── trino/
│   │   ├── catalog/
│   │   │   └── iceberg.properties
│   │   └── config.properties
│   ├── airflow/
│   │   └── airflow.cfg
│   ├── minio/
│   │   └── init-buckets.sh
│   └── grafana/
│       └── dashboards/
│           ├── pipeline-monitoring.json
│           └── model-monitoring.json
│
├── ingestion/
│   ├── producers/
│   │   ├── base_producer.py
│   │   ├── tomtom_producer.py
│   │   ├── weather_producer.py
│   │   ├── news_producer.py
│   │   └── traffic_weather_producer.py
│   ├── batch/
│   │   ├── osm_importer.py
│   │   ├── pems_bay_importer.py
│   │   ├── mets10_importer.py
│   │   └── hcmc_traffic_importer.py
│   └── tomtom_stats/
│       ├── stats_client.py
│       └── stats_loader.py
│
├── processing/
│   ├── bronze/
│   │   ├── kafka_to_bronze.py
│   │   └── batch_to_bronze.py
│   ├── silver/
│   │   ├── clean_traffic.py
│   │   ├── clean_weather.py
│   │   ├── clean_events.py
│   │   ├── map_osm_segments.py
│   │   └── load_stats_lookup.py
│   ├── gold/
│   │   ├── feature_temporal.py
│   │   ├── feature_traffic.py
│   │   ├── feature_weather.py
│   │   ├── feature_spatial.py
│   │   ├── feature_stats_baseline.py
│   │   ├── feature_lag.py
│   │   ├── feature_event.py
│   │   ├── feature_graph.py
│   │   └── build_training_dataset.py
│   └── utils/
│       ├── iceberg_utils.py
│       ├── spark_session.py
│       └── geo_utils.py
│
├── ml/
│   ├── training/
│   │   ├── train_lightgbm.py
│   │   ├── train_transfer.py
│   │   └── hyperparameter_search.py
│   ├── inference/
│   │   ├── batch_predict.py
│   │   └── online_predict.py
│   ├── evaluation/
│   │   ├── evaluate_model.py
│   │   └── drift_detector.py
│   ├── explainability/
│   │   └── shap_explainer.py
│   ├── clustering/
│   │   └── dbscan_hotspot.py
│   └── registry/
│       └── mlflow_utils.py
│
├── graph/
│   ├── load_road_network.py
│   ├── compute_centrality.py
│   ├── congestion_propagation.py
│   └── routing.py
│
├── alerts/
│   ├── alert_rules.py
│   ├── alert_writer.py
│   └── notifier.py
│
├── api/
│   ├── main.py
│   ├── routers/
│   │   ├── traffic.py
│   │   ├── alerts.py
│   │   ├── explain.py
│   │   ├── hotspots.py
│   │   ├── segments.py
│   │   ├── monitoring.py
│   │   ├── settings.py
│   │   └── routing.py
│   ├── services/
│   │   ├── redis_service.py
│   │   ├── trino_service.py
│   │   └── mlflow_service.py
│   ├── schemas/
│   │   ├── traffic.py
│   │   ├── alert.py
│   │   └── prediction.py
│   └── middleware/
│       └── rate_limit.py
│
├── airflow/
│   └── dags/
│       ├── dag_tomtom_stats.py
│       ├── dag_osm_refresh.py
│       ├── dag_batch_datasets.py
│       ├── dag_silver_processing.py
│       ├── dag_gold_features.py
│       ├── dag_batch_predict.py
│       ├── dag_dbscan_hotspot.py
│       ├── dag_data_quality.py
│       └── dag_auto_retrain.py
│
├── tests/
│   ├── unit/
│   │   ├── test_cleaning.py
│   │   ├── test_features.py
│   │   ├── test_alert_rules.py
│   │   └── test_shap.py
│   ├── integration/
│   │   ├── test_kafka_to_bronze.py
│   │   ├── test_silver_pipeline.py
│   │   └── test_api_endpoints.py
│   └── load/
│       └── k6_api_load_test.js
│
├── notebooks/
│   ├── 01_eda_traffic.ipynb
│   ├── 02_eda_weather.ipynb
│   ├── 03_feature_analysis.ipynb
│   ├── 04_lightgbm_baseline.ipynb
│   ├── 05_transfer_learning.ipynb
│   └── 06_shap_analysis.ipynb
│
├── scripts/
│   ├── seed_demo_data.py
│   ├── check_stack_health.sh
│   └── export_superset_dashboards.sh
│
└── docs/
    ├── SDD.pdf
    ├── api-spec.yaml
    ├── data-dictionary.md
    └── adr/
        ├── adr-001-kappa-vs-lambda.md
        ├── adr-002-iceberg-vs-delta.md
        └── adr-003-lightgbm-vs-nn.md
```

> **Quy ước đặt tên:**
> - Spark jobs: `verb_noun.py` — ví dụ `clean_traffic.py`, `build_training_dataset.py`
> - Airflow DAGs: tiền tố `dag_` — ví dụ `dag_silver_processing.py`
> - Feature files: tiền tố `feature_` — ví dụ `feature_temporal.py`
> - Tất cả config nhạy cảm (API keys, passwords) đều qua `.env` / `.env.local`, không hardcode

---

## Phase 1 — Hạ tầng & Data Ingestion nền

> **✅ HOÀN THÀNH** — 2026-05-31 | Thời gian thực tế: ~3 giờ

### 1.1 Infrastructure Setup

- [x] `docker-compose.yml` với 12 services: Kafka + Zookeeper + Schema Registry, MinIO, Spark (master + worker), Hive Metastore (PostgreSQL), Trino, Airflow, Redis, Neo4j
- [x] MinIO bucket `lakehouse` với thư mục `bronze/`, `silver/`, `gold/`
- [x] Iceberg catalog kết nối Hive Metastore + MinIO (S3A endpoint)
- [x] 6 Kafka topics tạo qua `make create-topics`
- [x] Schema Registry đăng ký Avro schema cho các topics chính
- [x] `Makefile` 12 targets: `make up/down/health/logs/check-kafka/create-topics/demo`
- [x] `scripts/check_stack_health.sh`
- [x] `processing/utils/spark_session.py` — SparkSession factory với Iceberg + S3A config

### 1.2 Data Producers

- [x] `base_producer.py` — exponential backoff retry (3 attempts), Dead Letter Queue, metrics tracking
- [x] `tomtom_producer.py` — polling TomTom Flow API, peak/off-peak interval (5–30 phút)
- [x] `weather_producer.py` — polling OpenWeatherMap mỗi 15–60 phút
- [x] `news_producer.py` — crawl RSS, geocoding tiếng Việt (refactored dùng BaseProducer)
- [x] `traffic_weather_producer.py` — sync traffic + weather cùng interval 5 phút (bonus)

### 1.3 Bronze Layer

- [x] `kafka_to_bronze.py` — Spark Structured Streaming: Kafka → Bronze Iceberg tables
- [x] `batch_to_bronze.py` — ghi batch dataset vào Bronze
- [x] Partition `city/year/month/day`, checkpoint management

### 1.4 Batch Importers *(structure sẵn sàng, chưa có logic thật)*

- [x] `osm_importer.py`, `pems_bay_importer.py`, `mets10_importer.py`, `hcmc_traffic_importer.py`

> ⚠️ Implement actual download/parse logic ở **đầu Phase 2** — OSM là dependency cứng của Silver cleaning.

### 1.5 Airflow DAGs

- [x] `dag_silver_processing.py` — hourly
- [x] `dag_data_quality.py` — hourly (30 phút offset)
- [x] `dag_batch_datasets.py` — weekly
- [x] `dag_tomtom_stats.py` — weekly (structure only)

> ⚠️ Implement `stats_client.py` thật ở **đầu Phase 2** — `silver_tomtom_stats_lookup` là dependency cứng của Phase 3 Stats Baseline Features.

### 1.6 Utilities

- [x] `spark_session.py`, `iceberg_utils.py`, `geo_utils.py`

### Test Results

```
6/6 tests passed ✅  (Imports / Configuration / Kafka Schema / Data Models / Processing Pipeline / File Structure)
```

### Checklist go/no-go sang Phase 2

- [x] `make up` không lỗi, 12 services UP
- [x] `make create-topics` tạo đủ 6 topics
- [x] Producers đẩy data vào Kafka được
- [x] Bronze tables có data tại `lakehouse/bronze/` trên MinIO
- [x] Airflow UI accessible tại `:8080`
- [x] Spark UI accessible tại `:8082`
- [ ] **Implement OSM importer actual logic** ← làm trước khi Silver cleaning
- [ ] **Implement TomTom Stats client actual logic** ← làm trước khi Phase 3
- [x] **MongoDB**: không dùng — đã xác nhận remove khỏi stack. Lakehouse (Iceberg/MinIO) là kho dữ liệu trung tâm; Redis + Neo4j đóng vai trò serving store chuyên biệt.

---

## Phase 2 — Data Cleaning & Silver Layer

> 🔲 Chưa bắt đầu | **Thời gian:** 2 tuần

### 2.1 Spark Cleaning Jobs

| Tác vụ | Nội dung xử lý |
|--------|----------------|
| **Schema Validation** | Validate từng record theo schema định nghĩa trước; log lỗi vào `bronze_error_log` |
| **Missing Value Handling** | Phát hiện null `currentSpeed`, `timestamp`, `segment_id`; điền median hoặc flag để loại |
| **Duplicate Removal** | Dedup theo `(segment_id, timestamp, source)` dùng Iceberg merge-on-read |
| **Timestamp Standardization** | Chuẩn hóa về UTC+7; đồng bộ format `yyyy-MM-dd HH:mm:ss` giữa các nguồn |
| **Coordinate Validation** | Loại record có lat/lon nằm ngoài bounding box HN + HCM |
| **Outlier Detection** | Loại tốc độ âm, tốc độ > 150 km/h, `jamFactor` ngoài `[0, 10]` |
| **Data Enrichment** | Join với OSM để gán `road_class`, `district`, `city` cho mỗi segment |
| **Lookup Join Validation** | Kiểm tra khả năng join với TomTom Traffic Stats lookup |
| **Iceberg Table Management** | Quản lý partition, schema evolution, snapshot, metadata |
| **Lineage Tracking** | Ghi `_ingested_at`, `_source`, `_pipeline_run_id` vào mọi Silver table |

### 2.2 Silver Tables

- [ ] `silver_traffic_cleaned`
- [ ] `silver_weather_cleaned`
- [ ] `silver_traffic_osm_mapped`
- [ ] `silver_tomtom_stats_lookup` — p15/p50/p85 theo khung giờ
- [ ] `silver_events_cleaned` — sự kiện/tai nạn/tin tức đã geocode, phục vụ Event Features ở Phase 3

### 2.3 TomTom Traffic Stats Pipeline

- [ ] Implement `stats_client.py` — async API: submit job → poll → download result
- [ ] Implement `stats_loader.py` — parse → nạp vào `silver_tomtom_stats_lookup`
- [ ] Airflow DAG lịch chạy: hàng tuần tùy quota API

### 2.4 Data Quality Monitoring

- [ ] Airflow DAG DQ check hàng giờ: row count, null rate, latency p95
- [ ] Phân loại 3 tier: **Vàng** (>95% complete, <1% dup) · **Bạc** (80–95%) · **Đồng** (<80%)

### Deliverables Phase 2

- [ ] Silver tables có dữ liệu sạch + lineage đầy đủ
- [ ] `silver_tomtom_stats_lookup` sẵn sàng cho feature engineering
- [ ] Cleaning job report: null rate, outlier rate, duplicate rate per source
- [ ] Airflow DQ DAG chạy tự động

---

## Phase 3 — Feature Engineering & Gold Layer

> 🔲 Chưa bắt đầu | **Thời gian:** 2–3 tuần

### 3.1 Feature Engineering — 8 nhóm đặc trưng

| Nhóm | Đặc trưng ví dụ |
|------|-----------------|
| **Temporal** | `hour_of_day`, `day_of_week`, `is_weekend`, `is_peak_hour`, `is_holiday_vn` |
| **Traffic** | `congestion_ratio = 1 - currentSpeed/freeFlowSpeed`, rolling avg 5/15/30 phút |
| **Weather** | `temp`, `humidity`, `rain_1h`, `visibility`, `wind_speed`; asof join theo city + timestamp |
| **Spatial** | `road_class`, `district`, khoảng cách tới nút giao lớn, mật độ đường, hướng di chuyển |
| **Stats Baseline** | `p50`, `p15`, `p85`, `baseline_congestion_ratio`, `speed_vs_monthly_median`, `pct_below_p15`, `pct_above_p85` |
| **Historical** | Trung bình cùng giờ tuần trước, median 7 ngày, xu hướng theo tháng |
| **Event** | `has_accident`, `has_flood`, `has_roadwork`, `has_event`; join `silver_events_cleaned` |
| **Lag** | `speed_lag_1`, `speed_lag_2`, `speed_lag_3` (mỗi lag = 5 phút) |

### 3.2 Graph Features

- [ ] Tính `degree_centrality`, `betweenness_centrality` qua NetworkX
- [ ] Join vào `gold_traffic_features`

### 3.3 Gold Tables

- [ ] `gold_traffic_features` — full feature vector per `(segment_id, timestamp)`
- [ ] `gold_training_dataset` — features + targets: `future_speed_15m`, `future_speed_60m`, `future_speed_240m`
- [ ] `gold_prediction_results` — kết quả dự báo từ LightGBM, bao gồm `shap_top_features` (JSON)
- [ ] `gold_congestion_hotspots` — DBSCAN clusters (tạo ở Phase 4, schema định nghĩa tại đây)
- [ ] `gold_alerts` — cảnh báo giao thông (tạo ở Phase 4, schema định nghĩa tại đây)
- [ ] `gold_dashboard_metrics` — bảng tổng hợp chỉ số theo khu vực/khung giờ phục vụ Superset

### 3.4 LightGBM Baseline Training

- [ ] Train 3 models riêng cho 3 horizon (15 / 60 / 240 phút)
- [ ] Evaluate MAE + RMSE per city, per `road_class`, per hour band
- [ ] Log params + metrics + artifacts vào MLflow
- [ ] Register model vào MLflow Registry, stage = `Staging`
- [ ] Populate `gold_prediction_results` với inference batch đầu tiên

### Deliverables Phase 3

- [ ] `gold_traffic_features` với đủ 8 nhóm feature
- [ ] 3 LightGBM models trong MLflow Registry
- [ ] MAE/RMSE baseline report per city per horizon
- [ ] Pipeline verify: Kafka → Bronze → Silver → Gold → Prediction
- [ ] `dag_gold_features.py` — Airflow DAG chạy feature engineering định kỳ (hourly)
- [ ] `dag_batch_predict.py` — Airflow DAG chạy batch inference, ghi `gold_prediction_results`

---

## Phase 4 — AI Analytics: DBSCAN, SHAP, Transfer Learning

> 🔲 Chưa bắt đầu | **Thời gian:** 2 tuần

### 4.1 DBSCAN Hotspot Detection

- [ ] DBSCAN clustering trên `(lat, lon, congestion_ratio)`
- [ ] Airflow DAG chạy mỗi 15 phút → ghi `gold_congestion_hotspots`
- [ ] Tune `eps` + `min_samples` riêng cho HN vs HCM

### 4.2 SHAP Explainability

- [ ] Tính SHAP values → top 3 features per prediction
- [ ] Lưu vào `gold_prediction_results.shap_top_features` (JSON array)
- [ ] FastAPI endpoint `GET /predictions/{segment_id}/explain`

### 4.3 Transfer Learning

- [ ] Pretrain trên MeTS-10 Bangkok → fine-tune Hanoi → fine-tune HCM
- [ ] So sánh MAE trước/sau fine-tune, log MLflow
- [ ] Promote lên `Production` nếu MAE giảm ≥ 5%

### 4.4 Graph Analytics (Neo4j)

- [ ] Nạp OSM road network vào Neo4j
- [ ] `betweenness_centrality` → join `gold_traffic_features`
- [ ] Cypher query: congestion propagation
- [ ] `GET /segments/{id}/upstream` — upstream sensor chain cho Live Corridor widget

### 4.5 Alert Engine

- [ ] Rule engine: `predicted_speed_15m < p15_baseline * 0.8` → HIGH · `< p50_baseline * 0.7` → MEDIUM
- [ ] Ghi `gold_alerts` + đẩy Kafka `traffic.alerts`

### 4.6 Auto-Retraining

- [ ] Airflow DAG daily: MAE rolling 7 ngày → trigger retrain nếu vượt ngưỡng
- [ ] Promote lên `Production` nếu MAE mới tốt hơn

### Deliverables Phase 4

- [ ] `gold_congestion_hotspots` + `gold_alerts` có data thật
- [ ] SHAP endpoint hoạt động
- [ ] Transfer learning report
- [ ] Auto-retrain DAG chạy được

---

## Phase 5 — Serving Layer, Dashboard & Observability

> 🔲 Chưa bắt đầu | **Thời gian:** 2 tuần

### 5.1 FastAPI Backend

| Method | Endpoint | Nguồn | Mô tả |
|--------|----------|-------|-------|
| `GET` | `/traffic/current/{city}` | Redis | Trạng thái giao thông mới nhất |
| `GET` | `/traffic/predict/{segment_id}?horizon=15` | `gold_prediction_results` | Dự báo tốc độ |
| `GET` | `/segments/geojson?city={city}` | `silver_traffic_osm_mapped` + Redis | GeoJSON cho Leaflet |
| `GET` | `/segments/{id}` | Redis → `silver_traffic_cleaned` | Segment detail cho map sidebar |
| `GET` | `/segments/{id}/upstream` | Neo4j | Upstream sensor chain |
| `GET` | `/alerts/active?city={city}` | `gold_alerts` + Redis | Cảnh báo đang hoạt động |
| `PATCH` | `/alerts/{id}/ack` | `gold_alerts` | Acknowledge/resolve một alert cụ thể |
| `PATCH` | `/alerts/bulk-ack` | `gold_alerts` | Bulk acknowledge/resolve |
| `GET` | `/predictions/{id}/explain` | SHAP output | Giải thích dự báo |
| `GET` | `/hotspots?city={city}` | `gold_congestion_hotspots` | DBSCAN clusters |
| `GET` | `/routing/alternatives` | Neo4j | Tuyến đường thay thế |
| `GET` | `/monitoring/pipeline` | Prometheus metrics | Pipeline status cho Monitoring page |
| `GET` | `/monitoring/model` | MLflow + DQ tables | Model quality metrics |
| `GET` | `/settings` | Redis config | App settings |
| `PUT` | `/settings` | Redis config | Lưu settings |

- [ ] Redis caching: TTL 1 phút real-time state, TTL 5 phút predictions
- [ ] Rate limiting middleware

### 5.2 Trino + Superset

- [ ] Connect Superset → Trino → Iceberg catalog
- [ ] Heatmap ùn tắc theo quận (HN + HCM)
- [ ] Biểu đồ tốc độ theo khung giờ
- [ ] So sánh HN vs HCM
- [ ] MAE/RMSE trend theo ngày
- [ ] Data quality tier chart (Vàng/Bạc/Đồng)

### 5.3 Grafana Monitoring

- [ ] Kafka consumer lag per topic
- [ ] Spark job duration
- [ ] Airflow task success rate
- [ ] Bronze/Silver/Gold row count per hour
- [ ] MAE per city per day
- [ ] Alert rule: Kafka lag > 5000 messages → webhook

### 5.4 Integration & Demo Testing

- [ ] E2E test: TomTom API → Kafka → Bronze → Silver → Gold → Prediction → Alert → API
- [ ] NFR-01: data mới cập nhật dashboard < 1 phút
- [ ] Load test FastAPI: 50 concurrent users, p95 < 500ms
- [ ] `make demo` spin up toàn stack + seed data

### Deliverables Phase 5

- [ ] FastAPI ≥ 14 endpoints, OpenAPI docs
- [ ] Superset ≥ 4 chart panels
- [ ] Grafana monitoring dashboard
- [ ] E2E test report

---

## Phase 6 — Frontend Connection

> 🔲 Chưa bắt đầu | **Thời gian:** 1 tuần  
> Frontend UI đã dựng sẵn tại `frontend/`, chưa connect vào backend thật.

### 6.1 Setup & Cấu hình

- [ ] Tạo `frontend/.env.local` với `NEXT_PUBLIC_API_URL=http://localhost:8000`
- [ ] Tạo `lib/api/client.ts` — Axios instance với `baseURL` từ env + global error interceptor
- [ ] Xác nhận FastAPI có bật CORS cho `http://localhost:3000`

### 6.2 Dashboard page

- [ ] Gọi `GET /traffic/current/{city}` → populate stat cards (segments, avg speed, jam factor)
- [ ] Gọi `GET /alerts/active?city=hanoi&limit=3` → populate Recent Alerts table
- [ ] Gọi `GET /monitoring/model` → populate Model Performance sidebar (MAE, RMSE, Latency)
- [ ] SWR polling stat cards + alerts mỗi 60s
- [ ] Gọi `GET /segments/{id}/upstream` → populate Live Corridor Tracking widget

### 6.3 Live Map page

- [ ] Gọi `GET /segments/geojson?city=hanoi` → render Leaflet polylines màu theo `jamFactor`
- [ ] Gọi `GET /hotspots?city=hanoi` → render DBSCAN CircleMarkers trên map
- [ ] Click polyline → gọi `GET /segments/{id}` → populate sidebar detail panel
- [ ] Click "View segment forecast" trong sidebar → navigate `/forecast?city=hanoi&segment={id}`
- [ ] SWR polling `GET /segments/geojson` mỗi 60s để update màu polylines

### 6.4 Forecast page

- [ ] Gọi `GET /traffic/predict/{segment_id}?horizon=15` → card +15 MIN
- [ ] Gọi `GET /traffic/predict/{segment_id}?horizon=60` → card +60 MIN
- [ ] Gọi `GET /traffic/predict/{segment_id}?horizon=240` → card +240 MIN
- [ ] Đọc `city` + `segment` từ URL params (`useSearchParams`) → fetch đúng segment
- [ ] TanStack Query cache kết quả forecast, stale time 5 phút

### 6.5 Hotspots page

- [ ] Gọi `GET /hotspots?city=hanoi` → render map clusters + populate Active Clusters list
- [ ] Click cluster card → pan map đến cluster đó
- [ ] SWR polling mỗi 60s

### 6.6 Alerts page

- [ ] Gọi `GET /alerts/active` → populate Alert Queue table
- [ ] Click "Ack" per row → gọi `PATCH /alerts/{id}/ack`
- [ ] Bulk select + "Acknowledge selected" → gọi `PATCH /alerts/bulk-ack`
- [ ] Filter tabs (All/Critical/High/Active/Acknowledged/Hanoi/HCMC) → thêm query params vào API call
- [ ] SWR polling mỗi 30s

### 6.7 Explanations page

- [ ] Gọi `GET /predictions/{id}/explain` → populate SHAP top contributing factors + bar chart
- [ ] Click item trong Recent Predictions list → fetch explanation cho prediction đó
- [ ] Populate Weather context + Historical baseline từ response

### 6.8 Monitoring page

- [ ] Gọi `GET /monitoring/pipeline` mỗi 10s → populate Pipeline Status list (Kafka lag, Spark, Feature Store, API uptime)
- [ ] Gọi `GET /monitoring/model` mỗi 60s → populate Model & Data Quality panel
- [ ] Format tooltip chart: `records` → `Math.round(value).toLocaleString()` (fix float display)

### 6.9 Settings page

- [ ] Gọi `GET /settings` khi mount → populate form (city toggles, threshold sliders, intervals)
- [ ] Click "Save settings" → gọi `PUT /settings` với form values
- [ ] Fallback: nếu API chưa có, lưu vào `localStorage` qua Zustand `persist`

### Deliverables Phase 6

- [ ] Tất cả 8 trang đều fetch data thật từ FastAPI (không còn mock data)
- [ ] SWR polling hoạt động — data auto-update không cần reload
- [ ] Live Map + Hotspots render đúng vị trí thật từ OSM/TomTom data
- [ ] Forecast cards hiển thị đúng giá trị từ LightGBM model
- [ ] SHAP explanation hiển thị đúng top features từ model thật

---

## Phân công gợi ý (nhóm 3 người)

| Thành viên | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 |
|------------|---------|---------|---------|---------|---------|
| Nguyễn Hoàng Phúc | TomTom Stats pipeline + DQ | Feature Engineering | Transfer Learning + Auto-retrain | Dashboard + Demo | Dashboard + Forecast connect |
| Nguyễn Mạnh Tiến | Spark cleaning jobs | LightGBM training + MLflow | DBSCAN + Alert Engine | FastAPI backend | API wiring + SWR hooks |
| Hà Đăng Long | Silver tables + Lineage | Gold tables schema | SHAP + Neo4j graph | Grafana + Testing | Map + Monitoring connect |

---

## Tech Stack tóm tắt

| Layer | Technology |
|-------|-----------|
| Message Broker | Apache Kafka + Schema Registry |
| Stream Processing | Apache Spark Structured Streaming |
| Object Storage | MinIO (S3-compatible) |
| Table Format | Apache Iceberg |
| Metadata Catalog | Hive Metastore (PostgreSQL backend) |
| SQL Query Engine | Trino |
| Pipeline Orchestration | Apache Airflow |
| ML Tracking | MLflow |
| Graph Database | Neo4j |
| Cache | Redis |
| API Backend | FastAPI |
| Frontend | Next.js 14 + shadcn/ui + Leaflet + Recharts |
| BI Dashboard | Apache Superset |
| Monitoring | Prometheus + Grafana |
| Container Runtime | Docker Compose → Kubernetes (production) |

---

*Tài liệu này được sinh từ SDD Cognitive Traffic Analytics Platform — Nhóm 09, 2026.*