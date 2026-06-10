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
| **Delta Lake / Apache Iceberg** | Iceberg 1.5+ | Table format cho Lakehouse | Schema evolution, time travel, partitioning, snapshot |

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

---

## Tổng quan

| Phase | Tên | Thời gian ước tính |
|-------|-----|--------------------|
| Phase 1 | Hạ tầng & Data Ingestion nền | 2–3 tuần |
| Phase 2 | Data Cleaning & Silver Layer | 2 tuần |
| Phase 3 | Feature Engineering & Gold Layer | 2–3 tuần |
| Phase 4 | AI Analytics: DBSCAN, SHAP, Transfer Learning | 2 tuần |
| Phase 5 | Serving Layer, Dashboard & Observability | 2 tuần |

**Tổng cộng:** ~10–12 tuần (có thể rút ngắn nếu các phase 1–2 chạy song song trong nhóm)

---

## Folder Structure

```
cognitive-traffic-analytics/
│
├── docker-compose.yml                  # Toàn bộ stack: Kafka, Spark, MinIO, Trino, Airflow, ...
├── Makefile                            # make up / make down / make demo / make test
├── README.md
├── .env                                # Biến môi trường: API keys, passwords, ports
├── .env.example
│
├── infra/                              # Cấu hình hạ tầng
│   ├── kafka/
│   │   ├── create-topics.sh            # Script tạo Kafka topics khi khởi động
│   │   └── schema-registry/
│   │       ├── traffic-realtime.avsc   # Avro schema cho traffic.realtime.tomtom
│   │       ├── weather-current.avsc
│   │       └── events-news.avsc
│   ├── spark/
│   │   ├── spark-defaults.conf         # Iceberg catalog config, S3 endpoint, ...
│   │   └── log4j2.properties
│   ├── trino/
│   │   ├── catalog/
│   │   │   └── iceberg.properties      # Kết nối Trino → Hive Metastore → MinIO
│   │   └── config.properties
│   ├── airflow/
│   │   └── airflow.cfg
│   ├── minio/
│   │   └── init-buckets.sh             # Tạo bucket lakehouse + thư mục bronze/silver/gold
│   └── grafana/
│       └── dashboards/
│           ├── pipeline-monitoring.json
│           └── model-monitoring.json
│
├── ingestion/                          # Kafka producers & batch importers
│   ├── producers/
│   │   ├── tomtom_producer.py          # Polling TomTom Flow API → Kafka
│   │   ├── weather_producer.py         # Polling OpenWeatherMap → Kafka
│   │   ├── news_producer.py            # Crawl RSS/NewsCrawler → Kafka
│   │   └── base_producer.py            # Base class: retry, dead letter queue, rate limit
│   ├── batch/
│   │   ├── osm_importer.py             # Download + parse OSM PBF → Bronze Iceberg
│   │   ├── pems_bay_importer.py        # HuggingFace datasets → Bronze
│   │   ├── mets10_importer.py          # MeTS-10 Bangkok batch download → Bronze
│   │   └── hcmc_traffic_importer.py    # Kaggle CSV → Bronze
│   └── tomtom_stats/
│       ├── stats_client.py             # Gọi TomTom Traffic Stats REST API async
│       └── stats_loader.py             # Parse response → Silver lookup table
│
├── processing/                         # Spark jobs: cleaning, feature engineering
│   ├── bronze/
│   │   ├── kafka_to_bronze.py          # Spark Structured Streaming: Kafka → Bronze Iceberg
│   │   └── batch_to_bronze.py          # Ghi batch dataset vào Bronze
│   ├── silver/
│   │   ├── clean_traffic.py            # Schema validation, dedup, outlier, enrichment
│   │   ├── clean_weather.py
│   │   ├── clean_events.py
│   │   ├── map_osm_segments.py         # Map TomTom segment_id → OSM way_id
│   │   └── load_stats_lookup.py        # Nạp TomTom Stats → silver_tomtom_stats_lookup
│   ├── gold/
│   │   ├── feature_temporal.py         # Temporal features
│   │   ├── feature_traffic.py          # Traffic features + rolling avg
│   │   ├── feature_weather.py          # Weather join (asof)
│   │   ├── feature_spatial.py          # Spatial features từ OSM
│   │   ├── feature_stats_baseline.py   # Stats baseline: p50, speed_vs_monthly_median, ...
│   │   ├── feature_lag.py              # Lag features: speed_lag_1/2/3
│   │   ├── feature_event.py            # Event flags: has_accident, has_flood, ...
│   │   ├── feature_graph.py            # Graph features từ Neo4j / NetworkX
│   │   └── build_training_dataset.py   # Join tất cả features → gold_training_dataset
│   └── utils/
│       ├── iceberg_utils.py            # Helper: tạo table, upsert, partition management
│       ├── spark_session.py            # Khởi tạo SparkSession với Iceberg config
│       └── geo_utils.py               # Bounding box validation, coordinate helpers
│
├── ml/                                 # ML: training, inference, explainability
│   ├── training/
│   │   ├── train_lightgbm.py           # Train LightGBM cho 3 horizon (15/60/240 phút)
│   │   ├── train_transfer.py           # Pretrain MeTS-10 → fine-tune HN/HCM
│   │   └── hyperparameter_search.py    # Optuna / grid search cho LightGBM params
│   ├── inference/
│   │   ├── batch_predict.py            # Batch inference → gold_prediction_results
│   │   └── online_predict.py           # Real-time inference cho FastAPI
│   ├── evaluation/
│   │   ├── evaluate_model.py           # Tính MAE/RMSE per city, road_class, hour band
│   │   └── drift_detector.py           # Phát hiện data drift + model drift
│   ├── explainability/
│   │   └── shap_explainer.py           # Tính SHAP values, trả về top-3 features
│   ├── clustering/
│   │   └── dbscan_hotspot.py           # DBSCAN clustering → gold_congestion_hotspots
│   └── registry/
│       └── mlflow_utils.py             # Log experiment, register model, promote stage
│
├── graph/                              # Neo4j graph analytics
│   ├── load_road_network.py            # Nạp OSM road network vào Neo4j
│   ├── compute_centrality.py           # Betweenness / degree centrality
│   ├── congestion_propagation.py       # Cypher queries: phát hiện lan truyền ùn tắc
│   └── routing.py                      # Alternative route suggestions
│
├── alerts/                             # Alert engine
│   ├── alert_rules.py                  # Rule engine: ngưỡng severity HIGH/MEDIUM/LOW
│   ├── alert_writer.py                 # Ghi gold_alerts + đẩy Kafka traffic.alerts
│   └── notifier.py                     # Webhook / email notification
│
├── api/                                # FastAPI backend
│   ├── main.py                         # App entry point, router mount
│   ├── routers/
│   │   ├── traffic.py                  # /traffic/current, /traffic/predict
│   │   ├── alerts.py                   # /alerts/active
│   │   ├── explain.py                  # /predictions/{id}/explain
│   │   ├── hotspots.py                 # /hotspots
│   │   └── routing.py                  # /routing/alternatives
│   ├── services/
│   │   ├── redis_service.py            # Cache read/write helpers
│   │   ├── trino_service.py            # Query Gold tables qua Trino
│   │   └── mlflow_service.py           # Load model từ MLflow registry
│   ├── schemas/
│   │   ├── traffic.py                  # Pydantic models cho request/response
│   │   ├── alert.py
│   │   └── prediction.py
│   └── middleware/
│       ├── auth.py                     # JWT middleware
│       └── rate_limit.py
│
├── airflow/                            # Airflow DAGs
│   └── dags/
│       ├── dag_tomtom_stats.py         # TomTom Stats async ingestion (weekly)
│       ├── dag_osm_refresh.py          # OSM batch refresh (monthly)
│       ├── dag_batch_datasets.py       # Import PEMS-BAY, MeTS-10, HCMC (one-time)
│       ├── dag_silver_processing.py    # Trigger cleaning jobs (hourly)
│       ├── dag_gold_features.py        # Trigger feature engineering (hourly)
│       ├── dag_batch_predict.py        # Batch inference (every 15 phút)
│       ├── dag_dbscan_hotspot.py       # DBSCAN clustering (every 15 phút)
│       ├── dag_data_quality.py         # DQ checks (hourly)
│       └── dag_auto_retrain.py         # Check MAE → trigger retrain nếu degraded (daily)
│
├── tests/                              # Unit + integration tests
│   ├── unit/
│   │   ├── test_cleaning.py
│   │   ├── test_features.py
│   │   ├── test_alert_rules.py
│   │   └── test_shap.py
│   ├── integration/
│   │   ├── test_kafka_to_bronze.py     # E2E: producer → Kafka → Bronze table
│   │   ├── test_silver_pipeline.py
│   │   └── test_api_endpoints.py       # FastAPI endpoint tests
│   └── load/
│       └── k6_api_load_test.js         # k6 load test: 50 concurrent users
│
├── notebooks/                          # EDA, prototyping, báo cáo
│   ├── 01_eda_traffic.ipynb
│   ├── 02_eda_weather.ipynb
│   ├── 03_feature_analysis.ipynb
│   ├── 04_lightgbm_baseline.ipynb
│   ├── 05_transfer_learning.ipynb
│   └── 06_shap_analysis.ipynb
│
├── scripts/                            # Utility scripts
│   ├── seed_demo_data.py               # Seed fake data để demo offline
│   ├── check_stack_health.sh           # Ping tất cả services, báo lỗi nếu có
│   └── export_superset_dashboards.sh   # Export Superset dashboard JSON
│
└── docs/                               # Tài liệu kỹ thuật
    ├── SDD.pdf                         # Solution Design Document (tài liệu gốc)
    ├── api-spec.yaml                   # OpenAPI 3.0 spec cho FastAPI
    ├── data-dictionary.md              # Data dictionary từ SDD Section 5.2
    └── adr/                            # Architecture Decision Records
        ├── adr-001-kappa-vs-lambda.md
        ├── adr-002-iceberg-vs-delta.md
        └── adr-003-lightgbm-vs-nn.md
```

> **Quy ước đặt tên:**
> - Spark jobs: `verb_noun.py` — ví dụ `clean_traffic.py`, `build_training_dataset.py`
> - Airflow DAGs: tiền tố `dag_` — ví dụ `dag_silver_processing.py`
> - Feature files: tiền tố `feature_` — ví dụ `feature_temporal.py`
> - Tất cả config nhạy cảm (API keys, passwords) đều qua `.env`, không hardcode

---

## Phase 1 — Hạ tầng & Data Ingestion nền

**Thời gian:** 2–3 tuần  
**Mục tiêu:** Dựng toàn bộ nền tảng hạ tầng. Đảm bảo dữ liệu thô chảy liên tục từ nguồn vào Kafka rồi ghi xuống Bronze Iceberg tables. Đây là foundation cho mọi thứ phía sau.

### 1.1 Infrastructure Setup

- [ ] Viết `docker-compose.yml` gồm toàn bộ stack: Kafka + Zookeeper, MinIO, Spark (master + 1 worker), Hive Metastore (PostgreSQL backend), Trino, Airflow, Redis
- [ ] Cấu hình MinIO: tạo bucket `lakehouse`, phân thư mục `bronze/`, `silver/`, `gold/`
- [ ] Cấu hình Iceberg catalog kết nối Hive Metastore + MinIO (S3-compatible endpoint)
- [ ] Tạo các Kafka topics:
  - `traffic.realtime.tomtom`
  - `weather.current`
  - `events.news`
  - `traffic.historical`
  - `traffic.predictions`
  - `traffic.alerts`
- [ ] Setup Schema Registry để validate message format trước khi ghi vào topic

### 1.2 Data Producers (Python)

- [ ] Viết `tomtom_producer.py`: polling TomTom Flow API mỗi 5–30 phút → validate schema → đẩy JSON vào `traffic.realtime.tomtom` (tần suất thay đổi theo peak/off-peak)
- [ ] Viết `weather_producer.py`: polling OpenWeatherMap mỗi 15–60 phút → `weather.current`
- [ ] Viết `news_producer.py`: crawl RSS/NewsCrawler → geocoding tiếng Việt → `events.news`
- [ ] Cấu hình rate limit, retry logic (exponential backoff), dead letter queue cho từng producer

### 1.3 Bronze Layer (Spark → Iceberg)

- [ ] Viết Spark Structured Streaming job đọc từng Kafka topic → ghi raw vào Bronze Iceberg tables:
  - `bronze_traffic_raw`
  - `bronze_weather_raw`
  - `bronze_events_raw`
- [ ] Partition Bronze tables theo `city` + `date` + `hour`
- [ ] Viết Airflow DAG batch import cho các dataset tĩnh:
  - OSM: import PBF file qua `osmium` hoặc `OSMnx`
  - PEMS-BAY: tải từ HuggingFace datasets library
  - MeTS-10 Bangkok: batch download → Bronze
  - HCMC Traffic Flow: batch CSV từ Kaggle → Bronze

### Deliverables Phase 1

- `docker-compose.yml` hoàn chỉnh, chạy được `docker compose up`
- 3 Kafka producers hoạt động ổn định
- Bronze Iceberg tables có dữ liệu thật từ TomTom + OpenWeatherMap
- Airflow DAG batch import cho toàn bộ dataset tĩnh
- MinIO console hiển thị data tại `lakehouse/bronze/`

---

## Phase 2 — Data Cleaning & Silver Layer

**Thời gian:** 2 tuần  
**Mục tiêu:** Biến dữ liệu thô Bronze thành Silver sạch, chuẩn hóa và có thể tin cậy. Đây là layer để mọi feature engineering và model training dựa vào.

### 2.1 Spark Cleaning Jobs

Áp dụng thống nhất cho cả dữ liệu streaming (Spark Structured Streaming) và batch (Spark batch job):

| Tác vụ | Nội dung xử lý |
|--------|----------------|
| **Schema Validation** | Validate từng record theo schema định nghĩa trước; log lỗi vào `bronze_error_log` |
| **Missing Value Handling** | Phát hiện null `currentSpeed`, `timestamp`, `segment_id`; điền median hoặc flag để loại |
| **Duplicate Removal** | Dedup theo `(segment_id, timestamp, source)` dùng Iceberg merge-on-read |
| **Timestamp Standardization** | Chuẩn hóa về UTC+7; đồng bộ format `yyyy-MM-dd HH:mm:ss` giữa các nguồn |
| **Coordinate Validation** | Loại record có lat/lon nằm ngoài bounding box HN + HCM |
| **Outlier Detection** | Loại tốc độ âm, tốc độ > 150 km/h, `jamFactor` ngoài `[0, 10]` |
| **Data Enrichment** | Join với OSM để gán `road_class`, `district`, `city` cho mỗi segment |
| **Lookup Join Validation** | Kiểm tra khả năng join giữa real-time data và TomTom Traffic Stats lookup |
| **Iceberg Table Management** | Quản lý partition, schema evolution, snapshot, metadata |
| **Lineage Tracking** | Ghi `_ingested_at`, `_source`, `_pipeline_run_id` vào mọi Silver table |

### 2.2 Silver Tables

- [ ] `silver_traffic_cleaned` — traffic đã cleaned + enriched với OSM metadata
- [ ] `silver_weather_cleaned` — weather chuẩn hóa đơn vị và timezone
- [ ] `silver_traffic_osm_mapped` — map `segment_id` TomTom → `way_id` OSM
- [ ] `silver_tomtom_stats_lookup` — TomTom Traffic Stats baseline (p15/p50/p85 theo khung giờ)

### 2.3 TomTom Traffic Stats Pipeline

- [ ] Viết Airflow DAG gọi TomTom Stats REST API async: submit job → poll → download result
- [ ] Parse kết quả → nạp vào `silver_tomtom_stats_lookup` partitioned theo `(segment_id, timeSet_name, month)`
- [ ] Lịch chạy: hàng tuần hoặc hàng tháng tùy quota API

### 2.4 Data Quality Monitoring

- [ ] Viết Airflow DAG chạy DQ check hàng giờ: row count, null rate, latency p95
- [ ] Phân loại chất lượng theo 3 tier: **Vàng** (>95% complete, <1% duplicate), **Bạc** (80–95%), **Đồng** (<80%)

### Deliverables Phase 2

- Silver tables có dữ liệu sạch và lineage đầy đủ
- `silver_tomtom_stats_lookup` sẵn sàng cho feature engineering
- Cleaning job report (null rate, outlier rate, duplicate rate per source)
- Airflow DQ check DAG chạy tự động

---

## Phase 3 — Feature Engineering & Gold Layer

**Thời gian:** 2–3 tuần  
**Mục tiêu:** Build đủ 8 nhóm feature từ SDD, tạo Gold feature table phục vụ model. Train LightGBM baseline để verify pipeline end-to-end.

### 3.1 Feature Engineering — 8 nhóm đặc trưng

Tất cả chạy trên Spark, đọc từ Silver tables, ghi xuống Gold:

| Nhóm | Đặc trưng ví dụ |
|------|-----------------|
| **Temporal** | `hour_of_day`, `day_of_week`, `is_weekend`, `is_peak_hour`, `is_holiday_vn` |
| **Traffic** | `congestion_ratio = 1 - currentSpeed/freeFlowSpeed`, rolling avg 5/15/30 phút |
| **Weather** | `temp`, `humidity`, `rain_1h`, `visibility`, `wind_speed`; asof join theo city + timestamp |
| **Spatial** | `road_class`, `district`, khoảng cách tới nút giao lớn, mật độ đường, hướng di chuyển |
| **Stats Baseline** | `p50`, `p15`, `p85`, `baseline_congestion_ratio`, `speed_vs_monthly_median`, `pct_below_p15`, `pct_above_p85` — join `silver_tomtom_stats_lookup` theo `(segment_id, hour, month)` |
| **Historical** | Trung bình cùng giờ tuần trước, median 7 ngày, xu hướng theo tháng |
| **Event** | Flag `has_accident`, `has_flood`, `has_roadwork`, `has_event`; join `silver_events_cleaned` theo city + time window |
| **Lag** | `speed_lag_1`, `speed_lag_2`, `speed_lag_3` (mỗi lag = 5 phút); Window function over `segment_id` |

> **Lưu ý quan trọng:** `speed_vs_monthly_median` và `pct_below_p15` là hai đặc trưng mạnh nhất trong nhóm Stats Baseline. `speed_vs_monthly_median` cho biết tốc độ hiện tại đang cao/thấp hơn mức trung vị thông thường; `pct_below_p15` phát hiện tình huống giao thông xấu hơn đáng kể so với baseline lịch sử.

### 3.2 Graph Features (có thể defer sang Phase 4)

- [ ] Nạp OSM road network vào NetworkX (hoặc Spark GraphX nếu cần scale)
- [ ] Tính `degree_centrality`, `betweenness_centrality` cho từng segment
- [ ] Join vào `gold_traffic_features` như graph feature

### 3.3 Gold Tables

- [ ] `gold_traffic_features` — full feature vector per `(segment_id, timestamp)`
- [ ] `gold_training_dataset` — features + target labels:
  - `future_speed_15m`
  - `future_speed_60m`
  - `future_speed_240m`

### 3.4 LightGBM Baseline Training

- [ ] Train 3 mô hình LightGBM riêng biệt cho 3 horizon (15, 60, 240 phút) trên `gold_training_dataset`
- [ ] Evaluate: MAE + RMSE per city, per `road_class`, per hour band
- [ ] Setup MLflow experiment tracking:
  - Log params: `num_leaves`, `learning_rate`, `feature_fraction`, ...
  - Log metrics: MAE, RMSE, R²
  - Log model artifacts
- [ ] Register model vào MLflow Model Registry với version + stage = `Staging`
- [ ] Tạo `gold_prediction_results`: lưu inference output + cột `model_version`

### Deliverables Phase 3

- `gold_traffic_features` table với đủ 8 nhóm feature
- 3 LightGBM models đăng ký trong MLflow Model Registry
- MAE/RMSE baseline report per city per horizon
- `gold_prediction_results` có data thật
- Pipeline end-to-end verify được: Kafka → Bronze → Silver → Gold → Prediction

---

## Phase 4 — AI Analytics: DBSCAN, SHAP, Transfer Learning

**Thời gian:** 2 tuần  
**Mục tiêu:** Hoàn thiện AI layer theo đúng SDD: hotspot clustering, explainability, transfer learning và auto-retraining pipeline.

### 4.1 DBSCAN Hotspot Detection

- [ ] Implement DBSCAN clustering trên `(lat, lon, congestion_ratio)` để detect điểm nóng ùn tắc
- [ ] Chạy batch mỗi 15 phút qua Airflow DAG
- [ ] Ghi kết quả vào `gold_congestion_hotspots`:
  ```
  cluster_id | center_lat | center_lon | severity | segment_ids[] | detected_at
  ```
- [ ] Tune hyperparameters `eps` và `min_samples` theo density của mạng lưới đường HN vs HCM (khác nhau đáng kể)

### 4.2 SHAP Explainability

- [ ] Tính SHAP values cho mỗi prediction → lấy top 3 features ảnh hưởng nhất
- [ ] Lưu vào `gold_prediction_results` cột `shap_top_features` (JSON array)
- [ ] Ví dụ output: `[{"feature": "rain_1h", "shap": -3.2}, {"feature": "is_peak_hour", "shap": 2.1}, ...]`
- [ ] Viết FastAPI endpoint `GET /predictions/{segment_id}/explain` trả về SHAP explanation

### 4.3 Transfer Learning Pipeline

- [ ] Pretrain trên **MeTS-10 Bangkok** (context Đông Nam Á) → lưu pretrained model checkpoint
- [ ] Fine-tune trên **Hanoi Traffic Stats** (data tự tích lũy từ polling TomTom)
- [ ] Fine-tune trên **HCMC Traffic Flow** (Kaggle dataset)
- [ ] Chiến lược: freeze feature extractor, chỉ fine-tune prediction head
- [ ] So sánh MAE trước/sau fine-tune → log vào MLflow experiment riêng
- [ ] Promote model fine-tuned lên `Production` nếu MAE giảm ≥ 5%

### 4.4 Graph Analytics với Neo4j

- [ ] Nạp OSM road network vào Neo4j: nodes = intersections, edges = road segments với weight = `travel_time`
- [ ] Compute `betweenness_centrality` → join vào `gold_traffic_features`
- [ ] Viết Cypher query phát hiện **congestion propagation**: nếu segment A ùn tắc, segment nào kế tiếp rủi ro cao
- [ ] Expose kết quả qua API endpoint `GET /routing/alternatives?from=...&to=...`

### 4.5 Alert Engine

- [ ] Viết alert rule engine với logic:
  - Nếu `predicted_speed_15m < p15_baseline * 0.8` → severity = HIGH
  - Nếu `predicted_speed_15m < p50_baseline * 0.7` → severity = MEDIUM
- [ ] Alert schema theo SDD:
  ```
  location | severity | duration_estimate | probable_cause (từ SHAP top feature)
  ```
- [ ] Ghi vào `gold_alerts` + đẩy vào Kafka topic `traffic.alerts`

### 4.6 Auto-Retraining Pipeline

- [ ] Airflow DAG chạy daily: tính MAE rolling 7 ngày, so với threshold
- [ ] Nếu MAE vượt ngưỡng → trigger retrain job tự động
- [ ] Retrain → validate trên holdout set → promote lên `Production` trong MLflow nếu MAE mới tốt hơn
- [ ] Notify qua webhook/email khi model được promote hoặc retrain thất bại

### Deliverables Phase 4

- `gold_congestion_hotspots` table với dữ liệu DBSCAN thật
- SHAP API endpoint hoạt động
- Transfer learning report: MAE Bangkok pretrain vs Hanoi/HCM fine-tune
- `gold_alerts` table + Kafka alerts flowing
- Auto-retrain DAG chạy được

---

## Phase 5 — Serving Layer, Dashboard & Observability

**Thời gian:** 2 tuần  
**Mục tiêu:** Hoàn thiện serving layer, build dashboard demo được, setup monitoring đầy đủ. Đây là phase để có sản phẩm trình bày được với giảng viên.

### 5.1 FastAPI Backend

Các endpoints chính cần implement:

| Method | Endpoint | Nguồn dữ liệu | Mô tả |
|--------|----------|---------------|-------|
| `GET` | `/traffic/current/{city}` | Redis cache | Trạng thái giao thông mới nhất |
| `GET` | `/traffic/predict/{segment_id}?horizon=15` | `gold_prediction_results` | Dự báo tốc độ |
| `GET` | `/alerts/active?city=hanoi` | `gold_alerts` + Redis | Cảnh báo đang hoạt động |
| `GET` | `/predictions/{segment_id}/explain` | SHAP output | Giải thích dự báo |
| `GET` | `/routing/alternatives` | Neo4j graph query | Tuyến đường thay thế |
| `GET` | `/hotspots?city=hcm` | `gold_congestion_hotspots` | Điểm nóng ùn tắc |

- [ ] Redis caching layer: TTL 1 phút cho real-time state, 5 phút cho predictions
- [ ] JWT auth middleware cho admin endpoints
- [ ] Rate limiting để bảo vệ API khỏi quá tải

### 5.2 Trino + Superset

- [ ] Connect Superset → Trino → Iceberg catalog
- [ ] Build Superset dashboards:
  - Heatmap ùn tắc theo quận (HN + HCM)
  - Biểu đồ tốc độ trung bình theo khung giờ trong ngày
  - So sánh giao thông HN vs HCM
  - MAE/RMSE trend của model theo ngày
  - Data quality tier chart (Vàng/Bạc/Đồng per nguồn)
- [ ] Báo cáo ad-hoc qua Trino SQL

### 5.3 Grafana Monitoring

Setup Prometheus scrape + Grafana dashboards cho:

- [ ] **Pipeline metrics:** Kafka consumer lag per topic, Spark job duration, Airflow task success rate
- [ ] **Infrastructure metrics:** CPU/RAM/disk per container, MinIO storage usage
- [ ] **Data metrics:** Bronze/Silver/Gold row count per hour, latency end-to-end (Kafka ingest → Gold table)
- [ ] **Model metrics:** MAE per city per day, prediction latency, Redis hit rate
- [ ] Alert rule: Kafka lag > 5000 messages → webhook notification

### 5.4 Integration & Demo Testing

- [ ] Test end-to-end pipeline: TomTom API → Kafka → Bronze → Silver → Gold → Prediction → Alert → FastAPI → Dashboard
- [ ] Verify NFR-01: dữ liệu mới cập nhật dashboard trong < 1 phút
- [ ] Verify NFR-02: thêm city mới (test với dataset giả) không cần thay đổi architecture
- [ ] Load test FastAPI: 50 concurrent users, target p95 latency < 500ms
- [ ] Viết `README.md` hướng dẫn setup
- [ ] Viết `Makefile` với target `make demo` để spin up toàn bộ stack và seed dữ liệu

### Deliverables Phase 5

- FastAPI với ≥ 5 endpoints hoạt động và có OpenAPI docs
- Superset dashboard với ≥ 4 chart panels
- Grafana monitoring dashboard đầy đủ
- E2E test report + NFR compliance check
- `README.md` + `Makefile` để chạy demo được trong < 10 phút

---

## Phân công gợi ý (nhóm 3 người)

| Thành viên | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 |
|------------|---------|---------|---------|---------|---------|
| Nguyễn Hoàng Phúc (Trưởng nhóm) | Infrastructure setup + Airflow | TomTom Stats pipeline + DQ | Feature Engineering | Transfer Learning + Auto-retrain | Dashboard + Demo |
| Nguyễn Mạnh Tiến | Kafka producers + Spark streaming | Spark cleaning jobs | LightGBM training + MLflow | DBSCAN + Alert Engine | FastAPI backend |
| Hà Đăng Long | MinIO + Iceberg + Schema Registry | Silver tables + Lineage | Gold tables schema | SHAP + Neo4j graph | Grafana + Testing |

> Phase 1 và Phase 2 có thể chạy song song một phần: trong khi một người setup infra, người khác có thể bắt đầu viết cleaning logic offline.

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
| BI Dashboard | Apache Superset |
| Monitoring | Prometheus + Grafana |
| Container Runtime | Docker Compose → Kubernetes (production) |

---

*Tài liệu này được sinh từ SDD Cognitive Traffic Analytics Platform — Nhóm 09, 2026.*
