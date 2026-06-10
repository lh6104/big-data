# NewsCrawler Integration Summary

**Date:** 2026-05-30  
**Status:** ✅ Integrated into cognitive-traffic-analytics

## Integration Points

### 1. Ingestion Layer (`ingestion/producers/`)

The NewsCrawler has been integrated as the news data producer:

| Component | Location | Purpose |
|-----------|----------|---------|
| `rss_fetcher.py` | `ingestion/producers/rss_fetcher.py` | Polls RSS feeds from `sources.yaml` |
| `html_scraper.py` | `ingestion/producers/html_scraper.py` | Scrapes web pages for news content |
| `article_parser.py` | `ingestion/producers/article_parser.py` | Parses and normalizes article metadata |
| `news_producer.py` | `ingestion/producers/news_producer.py` | Main entry point for news crawling pipeline |

**How to run:**
```bash
python -m ingestion.producers.news_producer
```

**Output:** Publishes to Kafka topic `events.news`

### 2. Processing Layer (`processing/silver/`)

News events are processed through the Silver layer:

| Component | Purpose |
|-----------|---------|
| `clean_events.py` | Orchestrates news event cleaning pipeline |
| `deduplicator.py` | Removes duplicate articles |
| `classifier.py` | Classifies event types (accident, flood, road_work, etc.) |
| `ner.py` | Named Entity Recognition for Vietnamese locations |
| `geocoder.py` | Converts location text → coordinates → OSM segment snapping |
| `preprocessor.py` | Text preprocessing for Vietnamese |
| `severity.py` | Severity scoring based on keywords |

**How to run:**
```bash
spark-submit processing/silver/clean_events.py
```

**Input:** `bronze_events_raw` (Iceberg table from Kafka)  
**Output:** `silver_events_clean` (cleaned & enriched events)

### 3. Processing Bronze Layer (`processing/bronze/`)

Raw news events ingested via Spark Structured Streaming:

| Component | Purpose |
|-----------|---------|
| `kafka_to_bronze.py` | Streams Kafka `events.news` → Iceberg `bronze_events_raw` |

**How to run:**
```bash
spark-submit processing/bronze/kafka_to_bronze.py \
  --kafka-brokers kafka:9092 \
  --kafka-topic events.news \
  --output-path s3://warehouse
```

### 4. Kafka Schema (`infra/kafka/`)

News events schema defined in Avro format:

```
infra/kafka/events-news.avsc
```

**Schema includes:**
- Event metadata (id, source, crawled_at, published_at)
- Extracted content (title, content, event_type, severity)
- Location information (location_entity, lat, lon, snapped_segment_id)
- Quality metrics (event_confidence, snap_distance_m)
- Deduplication tracking (mirrored_sources)

### 5. Configuration

**News sources:** `sources.yaml`
```yaml
sources:
  - name: vnexpress_giaothong
    type: rss
    url: https://vnexpress.net/rss/giao-thong.rss
    poll_interval_sec: 600
    enabled: true
  # ... more sources
```

**Application settings:** `infra/settings.py`
- Redis configuration for caching
- Geocoder settings (Nominatim URL, rate limits)
- NLP configuration (model paths, thresholds)

### 6. Data Models

Event data model defined in:
```
models/event.py
```

Pydantic model for type-safe event handling across the pipeline.

### 7. Testing

Unit tests integrated into main test suite:

```
tests/unit/
├── test_rss_fetcher.py
├── test_dedup.py
├── test_nlp.py
└── test_geocoder.py
```

### 8. Airflow DAG

News crawler scheduled via Airflow:

```
airflow/dags/dag_newscrawler.py
```

**Schedule:**
- RSS feeds: every 10 minutes
- HTML scraping: every 30 minutes
- Concurrency: max_active_runs=1 (prevent overlap)

## Data Flow

```
sources.yaml
    ↓
┌─────────────────────────┐
│  RSS/HTML Crawlers      │ (ingestion/producers/)
│  News Parser            │
└────────────┬────────────┘
             ↓
        Kafka Topic: events.news
             ↓
┌──────────────────────────────────────┐
│  Spark Structured Streaming          │ (processing/bronze/)
│  Kafka → bronze_events_raw (Iceberg) │
└────────────┬─────────────────────────┘
             ↓
        bronze_events_raw
             ↓
┌──────────────────────────────────────┐
│  Silver Processing Pipeline          │ (processing/silver/)
│  1. Deduplication                    │
│  2. Classification                   │
│  3. NER (location extraction)        │
│  4. Geocoding & snapping             │
│  5. Severity scoring                 │
│  6. Confidence calculation           │
└────────────┬─────────────────────────┘
             ↓
        silver_events_clean
             ↓
   (Ready for Gold layer joins)
```

## Integration with Main Pipeline

The news events are integrated with other data sources:

| Data Source | Topic | Bronze Table | Silver Table |
|-------------|-------|--------------|--------------|
| TomTom Flow | traffic.realtime.tomtom | bronze_traffic_raw | silver_traffic_cleaned |
| OpenWeatherMap | weather.current | bronze_weather_raw | silver_weather_cleaned |
| **News Crawler** | **events.news** | **bronze_events_raw** | **silver_events_clean** |

Gold layer features can join on:
- `city` + `timestamp` (time window)
- Segment location (spatial join via OSM)

Example query in feature engineering:
```sql
SELECT 
  t.segment_id,
  t.timestamp,
  t.current_speed,
  COUNT(e.event_id) as num_events,
  MAX(e.severity) as max_event_severity,
  ARRAY_AGG(e.event_type) as event_types
FROM silver_traffic_cleaned t
LEFT JOIN silver_events_clean e
  ON t.city = e.city
  AND t.timestamp BETWEEN e.published_at - INTERVAL '1 hour' AND e.published_at + INTERVAL '2 hours'
  AND ST_DWithin(ST_Point(t.lat, t.lon), ST_Point(e.lat, e.lon), 500)  -- 500m radius
GROUP BY t.segment_id, t.timestamp
```

## Next Steps

1. **Configure sources.yaml** with actual news sources (RSS feeds, websites)
2. **Setup Nominatim** for geocoding (self-hosted Docker container recommended)
3. **Configure Kafka** topics:
   - Create topic: `events.news`
   - Register schema in Schema Registry
4. **Run integration tests** to verify end-to-end pipeline
5. **Monitor pipeline** via Grafana dashboards
   - Crawl frequency, dedup rate, geocoding success rate

## Files Reference

### Newscrawler-specific configuration
- `sources.yaml` - News source definitions
- `infra/settings.py` - Application configuration
- `infra/kafka/events-news.avsc` - Avro schema

### Newscrawler-specific code
- `ingestion/producers/news_producer.py` - Main crawler
- `processing/silver/clean_events.py` - Processing orchestrator
- `processing/*/` - Data processing pipeline

### Newscrawler-specific tests
- `tests/unit/test_rss_fetcher.py`
- `tests/unit/test_dedup.py`
- `tests/unit/test_nlp.py`
- `tests/unit/test_geocoder.py`

### Documentation
- `docs/PHASE1_NEWSCRAWLER.md` - Original NewsCrawler specification

---

**Status:** Ready for Phase 1 implementation  
**Backup Location:** `/home/longha/Desktop/leue/newscrawler_old_backup/`
