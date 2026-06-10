# Cognitive Traffic Analytics Platform

Local-first big data prototype for urban traffic analytics and forecasting. The project ingests traffic, weather, and traffic-news data, builds Bronze/Silver/Gold datasets, exposes a FastAPI backend, and renders an operational React dashboard.

## Architecture

Data flow:

```text
TomTom / OpenWeather / RSS + HTML news
  -> ingestion producers and raw JSONL snapshots
  -> Bronze evidence/raw layer
  -> Silver cleaned traffic, weather, and events
  -> Gold feature and training datasets
  -> ML training / alerts / hotspots / API
  -> React frontend
```

Infrastructure in `docker-compose.yml` includes Kafka, Schema Registry, Postgres, Redis, Neo4j, MinIO, Hive Metastore, Trino, and Airflow. The local data path can run without the full stack by reading `raw/` and writing `data/`.

## Folder Structure

- `ingestion/`: Kafka producers and API/batch importers.
- `processing/`: Bronze, Silver, Gold, and utility processing jobs.
- `scripts/`: local pipeline and validation scripts.
- `raw/`: JSONL source snapshots for traffic, weather, and events.
- `data/`: generated Bronze/Silver/Gold CSV and Parquet outputs.
- `ml/`: training, clustering, inference, and explainability code.
- `api/`: FastAPI app and routers.
- `frontend/`: React/TanStack/Vite dashboard.
- `airflow/dags/`: orchestration DAGs.
- `infra/`: settings and Kafka schema files.
- `tests/`: pytest unit tests.

## Local Setup

Use Python 3.11 when possible.

```bash
cd /home/phuc/big-data
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
```

Fill `.env.local` with real local values. Do not commit it.

## Environment Variables

Important variables used by the code and compose stack:

- `TOMTOM_API_KEY`
- `OWM_API_KEY` or `OPENWEATHER_API_KEY`
- `TOMTOM_POLL_INTERVAL_MINUTES`
- `WEATHER_POLL_INTERVAL_MINUTES`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_TOPIC_EVENTS`
- `SCHEMA_REGISTRY_URL`
- `REDIS_URL`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `NOMINATIM_URL`
- `PHOBERT_CHECKPOINT`
- `API_DATA_DIR`
- `VITE_API_BASE_URL`

## Build Local Data Pipeline

Build local Bronze/Silver/Gold outputs from `raw/`:

```bash
make gold
```

Useful individual targets:

```bash
make news-bronze
make news-events
python3 scripts/build_local_gold_dataset.py --raw-dir raw --output-dir data
```

Fetch one live raw-data cycle, if API keys are configured:

```bash
make ingest-raw-once
```

## Run API

The API reads local `data/` by default and can run from the project root:

```bash
uvicorn api.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Example endpoints:

- `GET /traffic/current/hanoi`
- `GET /traffic/segments?city=hanoi`
- `GET /traffic/predict/HN_001?horizon=15`
- `GET /alerts/active`
- `GET /hotspots?city=hanoi`
- `GET /segments/geojson?city=hanoi`
- `GET /predictions/HN_001/explain`

## Run with Docker

Use Docker when the host Python version is not 3.11. The backend image uses `python:3.11-slim`, so host Python is not required for backend tests or API development.

```bash
docker compose build api
docker compose run --rm api python --version
```

The `api` compose service mounts the working tree into `/app` and reads local `data/`.

### Run API with Docker

```bash
make docker-api
# or
docker compose up --build api
```

The API runs on `http://localhost:8000`.

### Run tests with Docker

```bash
make docker-test
# or
docker compose run --rm api make test
docker compose run --rm api pytest
docker compose run --rm api python3 scripts/test_news_pipeline.py
```

### Why Python 3.11 container is used

The project targets Python 3.11. Running backend commands through Docker avoids host Python mismatches such as Python 3.14 dependency build failures.

## Run Frontend

```bash
cd frontend
cp .env.example .env.local
bun install
bun run dev
```

Set:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Build:

```bash
bun run build
```

## Run Docker Infrastructure

Docker Compose reads shell environment variables or a `.env` file. To use `.env.local`, pass it explicitly:

```bash
docker compose --env-file .env.local up -d
make create-topics
make health
```

Stop:

```bash
make down
```

The Spark services are currently lightweight placeholders in compose; local pipeline scripts are the reliable path for building `data/` in this repo state.

## Run Tests

```bash
python3 scripts/test_news_pipeline.py
pytest
```

Docker-based Python 3.11 test path:

```bash
make docker-test
docker compose run --rm api make test
```

Open a Python 3.11 shell in the same image:

```bash
make docker-shell
```

Frontend:

```bash
cd frontend
bun run build
```

Tests that require live external APIs or the full Docker stack should be kept as integration tests and skipped unless the needed services are available.

## Known Limitations

- API endpoints are local-data backed, not yet connected to Trino/Redis/model registry.
- Some frontend views still contain demo-only UI states where no backend endpoint exists.
- `routing` is still a demo endpoint because no road graph routing service is wired.
- Compose Spark master/worker are placeholders, not a production Spark cluster image.
- ML training still expects an Iceberg Gold table unless adapted to a local CSV training path.
- Data coverage in the current raw snapshots has large time gaps for some segments.
