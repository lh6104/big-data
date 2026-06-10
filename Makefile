.PHONY: help up down logs restart clean demo test seed health gold gold-docker train-data news-bronze news-events ingest-raw-once ingest-raw-10m repair-env

COMPOSE_FILE := docker-compose.yml
COMPOSE_CMD := docker compose -f $(COMPOSE_FILE)
PYTHON ?= python3
RAW_DIR ?= raw
DATA_DIR ?= data
INGEST_SECONDS ?= 600
INGEST_POLL_SECONDS ?= 300

help:
	@echo "Cognitive Traffic Analytics Platform — Make targets"
	@echo ""
	@echo "Infrastructure:"
	@echo "  make up          - Start all services (Kafka, Postgres, MongoDB, Spark, etc)"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs from all containers"
	@echo "  make clean       - Remove containers and volumes"
	@echo ""
	@echo "Pipeline:"
	@echo "  make demo        - Run full demo (up + seed + test pipeline)"
	@echo "  make gold        - Build local Silver/Gold train data from raw JSONL"
	@echo "  make news-bronze - Build auditable Bronze news evidence layer"
	@echo "  make news-events - Normalize raw news and build event aggregate features"
	@echo "  make gold-docker - Build local Silver/Gold train data in Docker"
	@echo "  make ingest-raw-once - Fetch one live raw-data cycle into raw/"
	@echo "  make ingest-raw-10m  - Fetch live raw data into raw/ for 10 minutes"
	@echo "  make seed        - Seed demo data into Kafka"
	@echo "  make test        - Run test suite"
	@echo "  make health      - Check stack health"
	@echo ""
	@echo "Development:"
	@echo "  make install     - Install Python dependencies"
	@echo "  make repair-env  - Reinstall NumPy/Pandas/PyArrow compatible binary wheels"
	@echo "  make lint        - Run code linting"
	@echo "  make format      - Format code with black/isort"
	@echo ""

## Infrastructure

up:
	@echo "Starting all services..."
	$(COMPOSE_CMD) up -d
	@sleep 10
	@$(MAKE) health

down:
	@echo "Stopping all services..."
	$(COMPOSE_CMD) down

restart: down up

logs:
	$(COMPOSE_CMD) logs -f

clean:
	@echo "Removing containers and volumes..."
	$(COMPOSE_CMD) down -v
	@echo "✓ Cleaned"

## Pipeline

demo: up seed test
	@echo ""
	@echo "╔════════════════════════════════════════════════════════╗"
	@echo "║  ✅ DEMO COMPLETE — Pipeline running end-to-end       ║"
	@echo "║                                                        ║"
	@echo "║  🌐 Dashboards:                                        ║"
	@echo "║     - MinIO:      http://localhost:9001               ║"
	@echo "║     - Spark App:  http://localhost:4040               ║"
	@echo "║     - Spark UI:   http://localhost:8082               ║"
	@echo "║     - Airflow:    http://localhost:8080               ║"
	@echo "║     - Neo4j:      http://localhost:7474               ║"
	@echo "║     - Trino:      http://localhost:8888               ║"
	@echo "╚════════════════════════════════════════════════════════╝"
	@echo ""

seed:
	@echo "Seeding demo data..."
	@$(PYTHON) scripts/seed_demo_data.py
	@echo "✓ Demo data seeded"

ingest-raw-once:
	@echo "Ingesting one live cycle into $(RAW_DIR)..."
	$(PYTHON) scripts/ingest_raw_sources.py --raw-dir $(RAW_DIR) --once
	@echo "✓ Raw ingest cycle complete"

ingest-raw-10m:
	@echo "Ingesting live data into $(RAW_DIR) for $(INGEST_SECONDS) seconds..."
	$(PYTHON) scripts/ingest_raw_sources.py --raw-dir $(RAW_DIR) --duration-seconds $(INGEST_SECONDS) --poll-seconds $(INGEST_POLL_SECONDS)
	@echo "✓ Raw ingest run complete"

news-bronze:
	@echo "Building Bronze news evidence layer..."
	$(PYTHON) scripts/build_news_bronze.py --raw-dir $(RAW_DIR) --output-dir $(DATA_DIR)
	@echo "✓ Bronze news:   $(DATA_DIR)/bronze/news_bronze_raw_enhanced.parquet"
	@echo "✓ Bronze report: $(DATA_DIR)/bronze/news_bronze_quality_report.md"

news-events: news-bronze
	@echo "Normalizing raw news events and building event features..."
	$(PYTHON) scripts/build_news_event_features.py --raw-dir $(RAW_DIR) --output-dir $(DATA_DIR)
	@echo "✓ Normalized news events: $(DATA_DIR)/silver/news_events_normalized.parquet"
	@echo "✓ Traffic event features: $(DATA_DIR)/gold/traffic_event_features.parquet"
	@echo "✓ News event report:      $(DATA_DIR)/gold/news_event_quality_report.csv"

gold train-data:
	@echo "Building local Silver/Gold datasets from $(RAW_DIR)..."
	@$(MAKE) news-events
	$(PYTHON) scripts/build_local_gold_dataset.py --raw-dir $(RAW_DIR) --output-dir $(DATA_DIR)
	@echo "✓ Clean dashboard features: $(DATA_DIR)/gold/cleaned_traffic_features.parquet"
	@echo "✓ Baseline train data:      $(DATA_DIR)/gold/train_features_15m.parquet"
	@echo "✓ Quality report:           $(DATA_DIR)/gold/data_quality_report.csv"

gold-docker:
	@echo "Building local Silver/Gold datasets in Docker..."
	$(COMPOSE_CMD) run --build --rm local-pipeline --raw-dir /app/raw --output-dir /app/data
	@echo "✓ Clean dashboard features: $(DATA_DIR)/gold/cleaned_traffic_features.parquet"
	@echo "✓ Baseline train data:      $(DATA_DIR)/gold/train_features_15m.parquet"
	@echo "✓ Quality report:           $(DATA_DIR)/gold/data_quality_report.csv"

test:
	@echo "Running test pipeline..."
	@$(PYTHON) scripts/test_news_pipeline.py
	@echo "✓ Tests passed"

health:
	@echo "Checking stack health..."
	@bash scripts/check_stack_health.sh
	@echo "✓ Stack healthy"

## Development

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "✓ Dependencies installed"

repair-env:
	@echo "Repairing local dataframe binary stack..."
	$(PYTHON) -m pip install --force-reinstall "numpy>=1.26.4,<2.0.0" "pandas>=2.2.2,<2.3.0" "pyarrow>=15.0.2,<16.0.0"
	$(PYTHON) -c "import numpy, pandas, pyarrow; print('numpy', numpy.__version__, 'pandas', pandas.__version__, 'pyarrow', pyarrow.__version__)"
	@echo "✓ Local dataframe stack repaired"

lint:
	@echo "Running linter..."
	pylint ingestion/ processing/ ml/ api/ --disable=all --enable=E,F --max-line-length=120
	@echo "✓ Linting passed"

format:
	@echo "Formatting code..."
	black ingestion/ processing/ ml/ api/ scripts/ --line-length=120
	isort ingestion/ processing/ ml/ api/ scripts/ --profile black
	@echo "✓ Formatted"

## Utility

ps:
	$(COMPOSE_CMD) ps

shell:
	docker exec -it kafka bash

spark-shell:
	docker exec -it spark-master /opt/spark/bin/pyspark --master spark://spark-master:7077

view-logs-%:
	$(COMPOSE_CMD) logs -f $*

check-kafka:
	docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

create-topics:
	@echo "Creating 6 Kafka topics..."
	docker exec kafka kafka-topics --create --topic events.news --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1 2>/dev/null || true
	docker exec kafka kafka-topics --create --topic traffic.realtime.tomtom --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 2>/dev/null || true
	docker exec kafka kafka-topics --create --topic weather.current --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1 2>/dev/null || true
	docker exec kafka kafka-topics --create --topic traffic.alerts --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1 2>/dev/null || true
	docker exec kafka kafka-topics --create --topic events.news.dlq --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 2>/dev/null || true
	docker exec kafka kafka-topics --create --topic traffic.realtime.tomtom.dlq --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1 2>/dev/null || true
	docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
	@echo "✓ 6 topics created"

.DEFAULT_GOAL := help
