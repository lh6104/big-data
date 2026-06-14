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
| **Amazon S3** | AWS S3 Standard / Free Tier | Object storage cloud cho Lakehouse | Lưu toàn bộ Bronze/Silver/Gold Parquet files, ML artifacts, reports |
| **Hive Metastore** | 3.1+ | Iceberg catalog — quản lý metadata & schema | Backend là PostgreSQL |
| **PostgreSQL** | 15+ | Backend cho Hive Metastore + Airflow metadata DB | |
| **Redis** | 7.2+ | In-memory cache | Cache real-time traffic state (TTL 1 phút), prediction cache (TTL 5 phút) |
| **Neo4j AuraDB** | AuraDB 5.x / Cloud | Managed graph database | Lưu road network từ OSM trên cloud; phục vụ upstream traversal, congestion propagation và routing. Không chạy Neo4j local trong Docker Compose |

> **AWS S3 configuration:** dùng `.env` để cấu hình `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET=cognitive-traffic-lakehouse`, `S3_WAREHOUSE=s3a://cognitive-traffic-lakehouse/warehouse`. Không hardcode credentials trong code hoặc notebook. Bật lifecycle rule xóa dữ liệu demo sau 7–14 ngày để kiểm soát chi phí.
>
> **Neo4j AuraDB configuration:** dùng `.env` để cấu hình `NEO4J_URI=neo4j+s://<dbid>.databases.neo4j.io`, `NEO4J_USERNAME=neo4j`, `NEO4J_PASSWORD`, `NEO4J_DATABASE=neo4j`. Không commit file credentials do Aura Console tải về; chỉ đưa biến mẫu vào `.env.example`.

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
| **Docker** | 25+ | Container runtime | Chạy local services: Kafka, Spark, Hive Metastore, Trino, Airflow, Redis, FastAPI |
| **Docker Compose** | 2.24+ | Orchestrate local stack | Entry point chính cho demo/dev; Neo4j dùng AuraDB cloud nên không nằm trong Compose |
| **Neo4j Aura Console** | Cloud platform | Quản lý AuraDB instance | Tạo database, lấy URI/username/password, theo dõi usage và import data |
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

---

## Tổng quan

| Phase | Tên | Trạng thái | Thời gian |
|-------|-----|-----------|-----------|
| Phase 1 | Hạ tầng & Data Ingestion nền | ✅ Hoàn thành | ~3 giờ thực tế |
| Phase 2 | Data Cleaning & Silver Layer | 🔲 Chưa bắt đầu | 2 tuần |
| Phase 3 | Feature Engineering & Gold Layer | 🔲 Chưa bắt đầu | 2–3 tuần |
| Phase 4 | AI Analytics: DBSCAN, SHAP, Transfer Learning, Neo4j Aura Graph | 🔲 Chưa bắt đầu | 2 tuần |
| Phase 5 | Serving Layer, Dashboard & Observability | 🔲 Chưa bắt đầu | 2 tuần |
| Phase 6 | Frontend Connection | 🔲 Chưa bắt đầu | 1 tuần |
| Phase 7 | Cognitive Intelligence Upgrade & Demo Hardening | 🔲 Đề xuất bổ sung | 1–2 tuần |

**Tổng cộng:** ~11–14 tuần nếu bổ sung Phase 7 cognitive/demo hardening

---

## Folder Structure

```
cognitive-traffic-analytics/
│
├── docker-compose.yml                 # Không chứa Neo4j local; graph DB dùng Neo4j AuraDB cloud
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
│   ├── aws/
│   │   ├── s3-bucket-policy.json
│   │   └── s3-lifecycle-rule.json
│   ├── neo4j-aura/
│   │   ├── constraints.cypher
│   │   ├── indexes.cypher
│   │   └── sample-import.cypher
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
├── intelligence/                       # Cognitive intelligence layer — đề xuất bổ sung
│   ├── risk_scoring.py
│   ├── what_if_simulator.py
│   ├── prediction_reliability.py
│   ├── smart_alert_reasoner.py
│   └── corridor_ranker.py
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
│   │   ├── mlflow_service.py
│   │   └── neo4j_aura_service.py
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
│   ├── check_neo4j_aura.py
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
> - Với AWS S3, `.env.example` cần có: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`, `S3_WAREHOUSE`, `S3_ENDPOINT` để trống nếu dùng AWS S3 thật
> - Với Neo4j AuraDB, `.env.example` cần có: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`. Không đưa credential thật vào Git.

---

## Phase 1 — Hạ tầng & Data Ingestion nền

> **✅ HOÀN THÀNH** — 2026-05-31 | Thời gian thực tế: ~3 giờ

### 1.1 Infrastructure Setup

- [x] `docker-compose.yml` với 10 local services: Kafka + Zookeeper + Schema Registry, Spark (master + worker), Hive Metastore (PostgreSQL), Trino, Airflow, Redis; Object Storage chuyển sang Amazon S3; Graph Database chuyển sang Neo4j AuraDB cloud
- [x] Amazon S3 bucket `cognitive-traffic-lakehouse` với prefix `bronze/`, `silver/`, `gold/`, `models/`, `reports/`
- [x] Iceberg catalog kết nối Hive Metastore + Amazon S3 qua S3A connector
- [x] 6 Kafka topics tạo qua `make create-topics`
- [x] Schema Registry đăng ký Avro schema cho các topics chính
- [x] `Makefile` 12 targets: `make up/down/health/logs/check-kafka/create-topics/demo`
- [x] `scripts/check_stack_health.sh`
- [x] `processing/utils/spark_session.py` — SparkSession factory với Iceberg + S3A config cho Amazon S3

#### 1.1.1 AWS S3 Lakehouse Setup

- [x] Tạo S3 bucket `cognitive-traffic-lakehouse` tại region gần Việt Nam, ưu tiên `ap-southeast-1` nếu dùng AWS Singapore
- [x] Chuẩn hóa prefix: `bronze/`, `silver/`, `gold/`, `checkpoints/`, `models/`, `reports/`
- [x] Cấu hình IAM user/role chỉ có quyền tối thiểu: `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` trên bucket project
- [x] Cấu hình Spark/Trino/Iceberg đọc ghi qua `s3a://cognitive-traffic-lakehouse/...`
- [x] Bật S3 Block Public Access; không public bucket
- [x] Bật lifecycle rule cho dữ liệu demo: xóa temporary/checkpoint cũ sau 7–14 ngày, giữ Gold/Reports lâu hơn nếu cần evidence

#### 1.1.2 Neo4j AuraDB Cloud Setup

- [ ] Tạo AuraDB instance trên Neo4j Aura Console, ưu tiên tier Free/Professional tùy giới hạn dữ liệu demo
- [ ] Lưu credential vào `.env`: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- [ ] Bổ sung `scripts/check_neo4j_aura.py` để gọi `driver.verify_connectivity()` trước khi chạy graph jobs
- [ ] Bổ sung `infra/neo4j-aura/constraints.cypher` và `infra/neo4j-aura/indexes.cypher`
- [ ] Import OSM graph theo batch nhỏ: node trước, relationship sau; tạo uniqueness constraint trước khi nạp
- [ ] Không đưa service `neo4j:` vào `docker-compose.yml`; backend/FastAPI kết nối trực tiếp tới AuraDB qua URI `neo4j+s://...`

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

- [x] `make up` không lỗi, local services UP; kết nối AWS S3 qua credentials trong `.env`; Neo4j AuraDB kiểm tra riêng qua `make check-neo4j` hoặc script `scripts/check_neo4j_aura.py`
- [x] `make create-topics` tạo đủ 6 topics
- [x] Producers đẩy data vào Kafka được
- [x] Bronze tables có data tại `s3a://cognitive-traffic-lakehouse/bronze/` trên Amazon S3
- [x] Airflow UI accessible tại `:8080`
- [x] Spark UI accessible tại `:8082`
- [ ] **Implement OSM importer actual logic** ← làm trước khi Silver cleaning
- [ ] **Implement TomTom Stats client actual logic** ← làm trước khi Phase 3
- [ ] **Quyết định MongoDB**: giữ (nêu rõ dùng để làm gì) hoặc remove khỏi stack
- [ ] **Tạo Neo4j AuraDB instance**: lấy `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, cấu hình `.env`, chạy kiểm tra kết nối

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

### 3.4 LightGBM Baseline Training

- [ ] Train 3 models riêng cho 3 horizon (15 / 60 / 240 phút)
- [ ] Evaluate MAE + RMSE per city, per `road_class`, per hour band
- [ ] Log params + metrics + artifacts vào MLflow
- [ ] Register model vào MLflow Registry, stage = `Staging`
- [ ] Tạo `gold_prediction_results`

### Deliverables Phase 3

- [ ] `gold_traffic_features` với đủ 8 nhóm feature
- [ ] 3 LightGBM models trong MLflow Registry
- [ ] `model_manifest.json` + model cards cho 15/60/240 phút
- [ ] MAE/RMSE baseline report per city per horizon
- [ ] Confidence band hoặc reliability score cơ bản cho prediction
- [ ] Pipeline verify: Kafka → Bronze → Silver → Gold → Prediction

---

## Phase 4 — AI Analytics: DBSCAN, SHAP, Transfer Learning, Neo4j Aura Graph

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

### 4.4 Graph Analytics (Neo4j AuraDB)

- [ ] Tạo Neo4j AuraDB instance trên cloud; cấu hình `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` trong `.env`
- [ ] Tạo constraints/indexes: `:RoadNode(node_id)`, `:RoadSegment(segment_id)`, relationship `:CONNECTS_TO`
- [ ] Nạp OSM road network vào AuraDB bằng `graph/load_road_network.py` hoặc CSV từ S3 + Cypher `LOAD CSV`
- [ ] Tính static centrality bằng NetworkX/Spark batch để kiểm soát chi phí; ghi kết quả vào `gold_traffic_features` và đồng bộ thuộc tính cần tra cứu sang AuraDB
- [ ] Cypher query: congestion propagation, upstream/downstream traversal, alternative corridor
- [ ] `GET /segments/{id}/upstream` — upstream sensor chain cho Live Corridor widget
- [ ] `GET /routing/alternatives` — tìm tuyến/đoạn thay thế dựa trên topology + trạng thái ùn tắc

### 4.5 Alert Engine

- [ ] Rule engine: `predicted_speed_15m < p15_baseline * 0.8` → HIGH · `< p50_baseline * 0.7` → MEDIUM
- [ ] Ghi `gold_alerts` + đẩy Kafka `traffic.alerts`

### 4.6 Auto-Retraining

- [ ] Airflow DAG daily: MAE rolling 7 ngày → trigger retrain nếu vượt ngưỡng
- [ ] Promote lên `Production` nếu MAE mới tốt hơn

### Deliverables Phase 4

- [ ] `gold_congestion_hotspots` + `gold_alerts` có data thật
- [ ] SHAP endpoint hoạt động
- [ ] Smart alert có `why_json` + `recommended_action`
- [ ] Graph propagation score từ Neo4j AuraDB hoặc NetworkX batch
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
| `GET` | `/segments/{id}/upstream` | Neo4j AuraDB | Upstream sensor chain |
| `GET` | `/alerts/active?city={city}` | `gold_alerts` + Redis | Cảnh báo đang hoạt động |
| `PATCH` | `/alerts/bulk-ack` | `gold_alerts` | Bulk acknowledge/resolve |
| `GET` | `/predictions/{id}/explain` | SHAP output | Giải thích dự báo |
| `GET` | `/hotspots?city={city}` | `gold_congestion_hotspots` | DBSCAN clusters |
| `GET` | `/routing/alternatives` | Neo4j AuraDB | Tuyến đường thay thế |
| `GET` | `/monitoring/pipeline` | Prometheus metrics | Pipeline status cho Monitoring page |
| `GET` | `/monitoring/model` | MLflow + DQ tables | Model quality metrics |
| `GET` | `/monitoring/data-quality` | DQ tables | Freshness/null/outlier/DQ score |
| `GET` | `/model/status` | MLflow + manifest | Model loaded, version, feature schema readiness |
| `POST` | `/traffic/predict/batch` | Model + Redis/Iceberg | Batch prediction cho nhiều segment trên map |
| `POST` | `/traffic/simulate` | Model + scenario input | What-if simulation cho mưa/tai nạn/giờ cao điểm |
| `GET` | `/graph/propagation/{segment_id}` | Neo4j AuraDB | Đường lan truyền ùn tắc + propagation score |
| `GET` | `/corridors/risk?city={city}` | `gold_corridor_risk_scores` | Xếp hạng hành lang giao thông nguy cơ cao |
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
- [ ] E2E graph test: OSM import → Neo4j AuraDB → `/segments/{id}/upstream` → Live Corridor widget
- [ ] NFR-01: data mới cập nhật dashboard < 1 phút
- [ ] Load test FastAPI: 50 concurrent users, p95 < 500ms
- [ ] `make demo-lite` seed dữ liệu nhỏ + model artifact + AuraDB graph sample + FastAPI + frontend
- [ ] `make demo-full` spin up toàn stack + Kafka → Bronze → Silver → Gold → prediction → alert

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

## Các cải tiến đề xuất cho bản kế hoạch

### 1. Làm rõ boundary giữa Lakehouse và Graph Database

- Iceberg/S3 là nguồn lưu trữ chính cho dữ liệu lịch sử, feature vector, prediction, alerts và báo cáo.
- Neo4j AuraDB chỉ nên lưu topology graph và các thuộc tính cần traversal nhanh: `segment_id`, `node_id`, `road_class`, `length_m`, `district`, `current_jam_factor`, `risk_score`.
- Không nên duplicate toàn bộ traffic time-series vào Neo4j; time-series vẫn để trong Iceberg/Redis để tránh tốn chi phí và query không tối ưu.

### 2. Giảm rủi ro chi phí cloud

- S3 đã có lifecycle rule; cần bổ sung thêm lifecycle cho `checkpoints/`, `tmp/`, `reports/demo/`.
- Neo4j AuraDB nên chạy dataset demo theo phạm vi nhỏ trước: một quận hoặc một số hành lang giao thông chính của Hà Nội/TP.HCM.
- GDS/graph analytics nặng nên để NetworkX/Spark batch ở local hoặc chỉ dùng Aura Graph Analytics khi thật sự cần.

### 3. Bổ sung data contracts và schema governance

- Mỗi topic Kafka cần có schema version rõ ràng: `traffic-realtime.v1`, `weather-current.v1`, `events-news.v1`.
- Thêm bảng `bronze_error_log` và `data_quality_results` để lưu lỗi schema, null/outlier/duplicate rate theo pipeline run.
- Mỗi Gold table cần có data dictionary: khóa chính, partition, refresh interval, owner, downstream API.

### 4. Chuẩn hóa API theo frontend sớm hơn

- Tạo `docs/api-spec.yaml` ngay đầu Phase 5, sau đó frontend dùng OpenAPI client để giảm lệch contract.
- Các endpoint nên có response model cố định: `TrafficCurrentResponse`, `ForecastResponse`, `AlertResponse`, `GeoJsonSegmentResponse`, `GraphUpstreamResponse`.
- Thêm endpoint health riêng cho phụ thuộc ngoài: `/health/s3`, `/health/trino`, `/health/neo4j`, `/health/mlflow`.

### 5. Cải thiện demo path

- Nên có `make demo-lite`: seed dữ liệu nhỏ, dùng S3 + AuraDB thật nhưng không cần chạy toàn bộ pipeline nặng.
- Nên có `make demo-full`: chạy Kafka → Bronze → Silver → Gold → prediction → alert → frontend.
- Chuẩn bị sẵn 3 kịch bản demo: Live Map, Forecast + SHAP, Upstream/Routing graph.

### 6. Bổ sung testing thực tế hơn

- Thêm integration test cho Neo4j AuraDB: connect, tạo constraint, upsert 10 nodes/relationships, chạy upstream query.
- Thêm contract test giữa FastAPI và frontend bằng schema OpenAPI.
- Thêm cost/safety test: xác nhận không log credentials, không commit `.env`, không public S3 bucket.



## Brainstorm bổ sung — Hệ thống cần gì để thật sự là Cognitive Traffic Analytics

Phần này bổ sung sau khi rà lại notebook huấn luyện model. Notebook hiện phù hợp vai trò **training prototype** cho dự báo tốc độ, nhưng toàn hệ thống cần thêm các lớp nhận thức, suy luận, giải thích, ra quyết định và tự cải thiện để đúng tinh thần "cognitive".

### 1. Capability Map — từ Traffic Dashboard đến Cognitive System

| Năng lực | Cần có trong hệ thống | Trạng thái hiện tại | Mức ưu tiên |
|----------|------------------------|---------------------|-------------|
| **Perception** — nhận thức hiện trạng | Thu thập traffic, weather, events, OSM; đồng bộ timestamp; hiển thị current state | Plan đã có Kafka/TomTom/OWM/RSS/Bronze/Silver; cần hoàn thiện Silver thật | P0 |
| **Prediction** — dự báo tương lai | Forecast tốc độ 15/60/240 phút, confidence interval, batch prediction | Notebook đã tốt cho 15/60 phút; thiếu 240 phút + uncertainty | P0 |
| **Explanation** — giải thích dự báo | SHAP top factors, baseline comparison, natural-language explanation | Plan có SHAP; notebook mới có feature importance, chưa có SHAP thật | P0 |
| **Graph Reasoning** — suy luận mạng đường | Upstream/downstream traversal, propagation risk, bottleneck/corridor detection | Plan có Neo4j AuraDB; cần thêm graph schema + graph feature thật | P1 |
| **Decision Support** — hỗ trợ quyết định | Alert có severity, lý do, affected segments, recommended action | Plan có alert rule cơ bản; cần smart alert reasoning | P1 |
| **Simulation** — giả lập tình huống | What-if: mưa lớn, tai nạn, đóng đường, tăng lưu lượng | Chưa có trong plan cũ | P2 |
| **Learning Loop** — tự cải thiện | Drift monitor, rolling MAE, auto-retraining, model promotion | Plan có auto-retrain; cần audit log + model governance | P1 |
| **Operational Intelligence** — vận hành thông minh | Data quality score, freshness, pipeline lag, model health, cost guardrails | Plan có Grafana/DQ; cần chuẩn hóa score và dashboard | P1 |

### 2. Các khối còn thiếu nên bổ sung

#### 2.1 Prediction Reliability Layer

Mỗi kết quả dự báo không nên chỉ trả `predicted_speed`, mà cần trả thêm độ tin cậy để frontend và alert engine biết dự báo có đáng tin không.

**Bổ sung field cho prediction response:**

```json
{
  "segment_id": "HN_005",
  "horizon": 60,
  "predicted_speed": 32.4,
  "confidence_band": [27.8, 38.9],
  "reliability_level": "high",
  "feature_coverage_ratio": 0.94,
  "model_version": "lightgbm_60m_v3",
  "data_freshness_seconds": 42
}
```

**Cách làm khả thi cho đồ án:**
- Tính `feature_coverage_ratio` = số feature có dữ liệu / tổng feature yêu cầu.
- Tính `reliability_level`: `high` nếu feature đầy đủ và data mới; `medium` nếu thiếu weather/event; `low` nếu dùng fallback.
- Confidence band có thể ước lượng từ residual validation theo từng horizon hoặc từng road_class.

#### 2.2 Traffic Risk Scoring Layer

Bổ sung điểm rủi ro cho từng segment/corridor để hệ thống không chỉ dự báo tốc độ mà còn xếp hạng nguy cơ ùn tắc.

```text
risk_score = 0.35 * congestion_ratio
           + 0.25 * prediction_drop_ratio
           + 0.15 * upstream_congestion_score
           + 0.10 * rain_severity
           + 0.10 * event_severity
           + 0.05 * data_uncertainty
```

**Gold table mới:**

| Table | Mục đích |
|-------|----------|
| `gold_segment_risk_scores` | Điểm rủi ro theo segment, timestamp, horizon |
| `gold_corridor_risk_scores` | Gom nhiều segment thành hành lang giao thông |
| `gold_prediction_audit_log` | Log input features, model version, prediction, actual later, error |

#### 2.3 Graph Propagation Layer với Neo4j AuraDB

Neo4j AuraDB nên dùng cho topology và traversal, không dùng để lưu toàn bộ time-series. Cần tách rõ:

| Dữ liệu | Nơi lưu chính | Lý do |
|---------|---------------|-------|
| Time-series traffic/weather/events | Iceberg/S3 | Dữ liệu lớn, query phân tích, time travel |
| Current state/prediction cache | Redis | Truy cập nhanh cho API |
| Road topology, upstream/downstream, adjacent segments | Neo4j AuraDB | Traversal và graph reasoning |
| Prediction/alert/report | Iceberg/S3 + Redis cache | Lưu lịch sử và phục vụ dashboard |

**Graph schema gợi ý:**

```cypher
(:Segment {segment_id, road_class, city, district, length_m})
(:Intersection {node_id, lat, lon})
(:District {name, city})
(:Segment)-[:STARTS_AT]->(:Intersection)
(:Segment)-[:ENDS_AT]->(:Intersection)
(:Segment)-[:UPSTREAM_OF {distance_m, direction}]->(:Segment)
(:Segment)-[:IN_DISTRICT]->(:District)
```

**Graph API nên thêm:**

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/segments/{id}/upstream?depth=3` | Danh sách segment upstream ảnh hưởng đến segment hiện tại |
| `GET` | `/segments/{id}/downstream?depth=3` | Các segment có thể bị lan truyền ùn tắc |
| `GET` | `/graph/propagation/{segment_id}` | Điểm lan truyền ùn tắc và đường lan truyền |
| `GET` | `/corridors/risk?city=hanoi` | Xếp hạng hành lang giao thông rủi ro cao |

#### 2.4 Smart Alert Reasoning

Alert nên có lý do và khuyến nghị, không chỉ là threshold.

```json
{
  "alert_id": "ALERT_HN_20260613_001",
  "severity": "HIGH",
  "segment_id": "HN_005",
  "predicted_speed_15m": 18.7,
  "baseline_p15": 31.0,
  "why": [
    "Predicted speed is 39.7% below p15 baseline",
    "Upstream congestion score increased for 3 consecutive intervals",
    "Rain severity is high in the same district"
  ],
  "recommended_action": "Prioritize monitoring this corridor and suggest alternative route"
}
```

**Bổ sung bảng:** `gold_smart_alerts` hoặc mở rộng `gold_alerts` với các cột:
- `why_json`
- `recommended_action`
- `affected_segments`
- `confidence_level`
- `ack_status`
- `resolved_at`

#### 2.5 What-if Simulation Layer

Đây là phần làm demo "xịn" vì người dùng có thể giả lập tình huống.

| Scenario | Input | Output |
|----------|-------|--------|
| Mưa lớn | `rain_1h=30mm`, `visibility=low` | Dự báo speed giảm bao nhiêu % |
| Tai nạn | `event_type=accident`, `distance=500m` | Risk score tăng bao nhiêu |
| Giờ cao điểm | `hour=18`, `is_peak_hour=true` | So sánh với off-peak |
| Đóng đường | `closed_segment_id` | Tuyến thay thế + affected downstream |

**API đề xuất:**

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/traffic/simulate` | Trả prediction/risk trong scenario giả lập |
| `POST` | `/routing/simulate-closure` | Giả lập đóng segment và tìm tuyến thay thế |

#### 2.6 Model Governance & Model Card

Mỗi model artifact cần đi kèm metadata để backend biết model có dùng được không.

```json
{
  "model_name": "traffic_speed_lightgbm_60m",
  "model_version": "v3",
  "horizon_minutes": 60,
  "feature_schema_version": "gold_features_v3",
  "trained_until": "2026-06-13",
  "test_mae": 4.49,
  "test_rmse": 6.21,
  "supported_cities": ["hanoi", "hcmc"],
  "supported_modes": ["known_segment", "cold_start"],
  "limitations": ["Performance may degrade on unseen road segments"]
}
```

**File/bảng nên có:**
- `models/model_manifest.json`
- `models/model_card_15m.md`, `model_card_60m.md`, `model_card_240m.md`
- `gold_model_registry_snapshot`
- `gold_model_prediction_audit`

### 3. Cập nhật riêng cho notebook training

Notebook chỉ tập trung train model là đúng, nhưng cần align với plan bằng các đầu ra rõ ràng sau:

| Việc cần thêm | Lý do | Ưu tiên |
|---------------|-------|---------|
| Train đủ 3 horizon `15m/60m/240m` | Plan yêu cầu 3 model forecast | P0 |
| MLflow logging | Có experiment tracking và registry | P0 |
| SHAP summary thật | Phục vụ Explanations page | P0 |
| Export `model_manifest.json` | Backend load model an toàn | P0 |
| Export `api_contract_prediction.json` | Đồng bộ FastAPI/frontend | P1 |
| Thêm cold-start model không dùng `segment_id` | Dự báo được segment mới | P1 |
| Thêm confidence band từ residual | Prediction có độ tin cậy | P1 |
| Viết lại thành `ml/training/train_lightgbm.py` | Tái lập ngoài notebook | P1 |

### 4. API contract mở rộng sau brainstorm

| Method | Endpoint | Response chính | Mục đích |
|--------|----------|----------------|----------|
| `GET` | `/traffic/predict/{segment_id}?horizon=15` | prediction + confidence + SHAP id | Dự báo 1 segment |
| `POST` | `/traffic/predict/batch` | list predictions | Dự báo nhiều segment cho map |
| `POST` | `/traffic/simulate` | scenario impact | What-if simulation |
| `GET` | `/predictions/{id}/explain` | SHAP + natural-language reason | Giải thích dự báo |
| `GET` | `/segments/{id}/upstream` | upstream chain | Graph reasoning |
| `GET` | `/graph/propagation/{segment_id}` | propagation path + score | Lan truyền ùn tắc |
| `GET` | `/corridors/risk` | ranked corridors | Xếp hạng hành lang nguy cơ cao |
| `GET` | `/monitoring/model` | MAE, drift, model version | Theo dõi model |
| `GET` | `/monitoring/data-quality` | freshness, null rate, DQ score | Theo dõi chất lượng dữ liệu |
| `GET` | `/model/status` | loaded models, versions, feature schema | Kiểm tra readiness của serving |

### 5. Demo Scenarios nên chuẩn bị

| Demo | Luồng trình diễn | Điểm thể hiện |
|------|------------------|---------------|
| **Live Map** | Mở map → segment đổi màu theo jamFactor → click segment | Real-time traffic perception |
| **Forecast + Explain** | Chọn segment → xem 15/60/240 forecast → xem SHAP reason | Prediction + explainability |
| **Upstream Propagation** | Chọn segment tắc → xem upstream chain từ Neo4j AuraDB | Graph reasoning |
| **Smart Alert** | Hệ thống tạo HIGH alert → xem why + recommended action | Decision support |
| **What-if Simulation** | Giả lập mưa lớn/tai nạn → so sánh speed/risk trước-sau | Cognitive simulation |
| **Monitoring** | Xem Kafka lag, DQ score, model MAE drift | Operational intelligence |

### 6. Chấm điểm sau brainstorm

| Mức đánh giá | Điểm hiện tại | Lý do |
|--------------|--------------:|-------|
| **Notebook training** | 7/10 | Train tốt cho 15/60m, có baseline/walk-forward; thiếu 240m, MLflow, SHAP thật |
| **Demo system** | 5.5/10 | Plan tốt, hạ tầng/ý tưởng đủ; còn thiếu serving thật, graph reasoning thật, alert reasoning |
| **Cognitive intelligence** | 4.5/10 | Có hướng SHAP/Neo4j/DBSCAN nhưng chưa có risk score, propagation, uncertainty, simulation |
| **Production readiness** | 3.5/10 | Thiếu MLOps hoàn chỉnh, audit log, drift, contract test, cost guardrails |

**Mục tiêu hợp lý cho đồ án:** đưa hệ thống lên **7.5–8/10 ở mức demo** bằng cách ưu tiên: `240m forecast` → `MLflow` → `SHAP` → `FastAPI prediction thật` → `Neo4j upstream` → `smart alerts` → `demo-lite`.

### 7. Roadmap ưu tiên sau brainstorm

#### Sprint A — Hoàn thiện ML training artifact

- [ ] Sửa notebook/train script để train đủ `15m`, `60m`, `240m`.
- [ ] Log toàn bộ metrics vào MLflow.
- [ ] Export `model_manifest.json` và model card.
- [ ] Sinh SHAP top features cho từng horizon.
- [ ] Tạo `api_contract_prediction.json` cho backend/frontend.

#### Sprint B — Model Serving thật

- [ ] Implement `api/services/model_loader.py` hoặc `mlflow_service.py`.
- [ ] Implement `api/services/feature_builder.py` đọc Redis/Iceberg để build online feature.
- [ ] Endpoint `GET /traffic/predict/{segment_id}` trả prediction + reliability.
- [ ] Endpoint `GET /model/status` kiểm tra model loaded, schema version, feature coverage.
- [ ] Cache prediction vào Redis TTL 5 phút.

#### Sprint C — Cognitive Graph với Neo4j AuraDB

- [ ] Tạo `infra/neo4j-aura/constraints.cypher` và `indexes.cypher`.
- [ ] Load OSM segment graph vào AuraDB ở phạm vi demo.
- [ ] Implement upstream/downstream traversal.
- [ ] Tính `upstream_congestion_score` và join vào `gold_traffic_features`.
- [ ] Endpoint `/graph/propagation/{segment_id}`.

#### Sprint D — Smart Alert + What-if

- [ ] Tạo `gold_segment_risk_scores`.
- [ ] Mở rộng `gold_alerts` thành smart alerts có `why_json` và `recommended_action`.
- [ ] Endpoint `POST /traffic/simulate`.
- [ ] Frontend hiển thị alert reasoning và scenario impact.

#### Sprint E — Demo & Observability

- [ ] `make demo-lite`: seed data nhỏ + model artifact + AuraDB graph sample + FastAPI + frontend.
- [ ] `make demo-full`: Kafka → Bronze → Silver → Gold → predict → alert.
- [ ] Grafana panel: Kafka lag, DQ score, MAE trend, API latency.
- [ ] Superset chart: speed trend, district heatmap, model error by road_class.

### 8. Định nghĩa bản "đủ tốt để bảo vệ"

Bản demo nên được xem là đạt nếu có tối thiểu:

- [ ] Dữ liệu traffic/weather/event mẫu chạy qua Bronze/Silver/Gold hoặc có Gold snapshot hợp lệ.
- [ ] Model LightGBM chạy thật cho 15/60/240 phút.
- [ ] API forecast trả prediction từ model artifact thật.
- [ ] SHAP/explanation trả top factors thật hoặc precomputed SHAP từ batch prediction.
- [ ] Neo4j AuraDB trả upstream chain cho ít nhất 20–50 segment demo.
- [ ] Alert engine sinh HIGH/MEDIUM alert có lý do.
- [ ] Frontend có Live Map, Forecast, Alerts, Explanations, Monitoring dùng API thật.
- [ ] Có báo cáo evaluation: MAE/RMSE, slice analysis, data quality, latency.


## Phân công gợi ý (nhóm 3 người)

| Thành viên | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 |
|------------|---------|---------|---------|---------|---------|
| Nguyễn Hoàng Phúc | TomTom Stats pipeline + DQ | Feature Engineering | Transfer Learning + Auto-retrain | Dashboard + Demo | Dashboard + Forecast connect |
| Nguyễn Mạnh Tiến | Spark cleaning jobs | LightGBM training + MLflow | DBSCAN + Alert Engine | FastAPI backend | API wiring + SWR hooks |
| Hà Đăng Long | Silver tables + Lineage | Gold tables schema | SHAP + Neo4j Aura graph | Grafana + Testing | Map + Monitoring connect |

---

## Tech Stack tóm tắt

| Layer | Technology |
|-------|-----------|
| Message Broker | Apache Kafka + Schema Registry |
| Stream Processing | Apache Spark Structured Streaming |
| Object Storage | Amazon S3 |
| Table Format | Apache Iceberg |
| Metadata Catalog | Hive Metastore (PostgreSQL backend) |
| SQL Query Engine | Trino |
| Pipeline Orchestration | Apache Airflow |
| ML Tracking | MLflow |
| Graph Database | Neo4j AuraDB (Cloud) |
| Cache | Redis |
| API Backend | FastAPI |
| Frontend | Next.js 14 + shadcn/ui + Leaflet + Recharts |
| BI Dashboard | Apache Superset |
| Monitoring | Prometheus + Grafana |
| Container Runtime | Docker Compose → Kubernetes (production) |

---

*Tài liệu này được cập nhật từ SDD Cognitive Traffic Analytics Platform — Nhóm 09, 2026. Bản v4 bổ sung Neo4j AuraDB và lớp Cognitive Intelligence Upgrade.*
