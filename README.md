# Hanoi Datasource Scaffold

This scaffold implements the Hanoi-only datasource step for the Cognitive Traffic Analytics Platform.

## Setup

1. Create a local environment file:

   ```bash
   cp .env.example .env
   ```

2. Fill in `TOMTOM_API_KEY`, `HERE_API_KEY`, and `OWM_API_KEY`.

3. Install dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

## One-Time Setup

```bash
setup/create_topics.sh
python3 setup/mongo_init.py
python3 schemas/register_schemas.py
python3 collectors/osm_importer.py
python3 collectors/neo4j_importer.py
python3 collectors/hanoi_stats_cleaner.py
```

`collectors/hanoi_stats_cleaner.py` skips cleanly if `data/raw/historical/hanoi_traffic_stats.csv` is absent.

## Streaming Producers

Run each producer in its own terminal while Kafka is available:

```bash
python3 collectors/tomtom_producer.py
python3 collectors/here_producer.py
python3 collectors/weather_producer.py
python3 collectors/news_producer.py
```

For aligned traffic + weather ingestion in one polling cycle, use:

```bash
python3 collectors/traffic_weather_producer.py --bucket-minutes 5
```

This publishes to `traffic.raw` and `weather.raw`, writes JSONL snapshots locally, and uses the UTC dynamic crawl schedule in `docs/traffic_weather_ingestion.md`. Stop it with `Ctrl+C`.

## Silver Layer

```bash
spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0 \
  spark/silver_consumer.py
```

For joined traffic + weather Silver features:

```bash
spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0 \
  spark/traffic_weather_silver_join.py
```

## Health Check

```bash
python3 utils/health_check.py
```
