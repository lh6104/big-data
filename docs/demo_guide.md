# Demo Guide

This guide is the recommended walkthrough for a capstone/demo presentation. It uses the local Docker API, the React frontend, and the local Gold traffic/model artifacts already present in the working tree.

## Run The API With Docker

Build the Python 3.11 API image:

```bash
docker compose build api
```

Start the API:

```bash
make docker-api
```

Equivalent direct command:

```bash
docker compose up --build api
```

The API is available at:

```text
http://localhost:8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Run The Frontend On Port 8080

In another terminal:

```bash
cd frontend
bun install
VITE_API_BASE_URL=http://localhost:8000 bun run dev --host 0.0.0.0 --port 8080
```

Open:

```text
http://localhost:8080
```

## API Docs

FastAPI docs:

```text
http://localhost:8000/docs
```

OpenAPI JSON:

```text
http://localhost:8000/openapi.json
```

## Demo Flow

1. Dashboard

   Open the dashboard first. Show that the main cards are backed by local traffic Gold data through `/dashboard/summary?city=hanoi` and `/dashboard/trends?city=hanoi&hours=24`.

2. Live Map

   Open Live Map for Hanoi or HCMC. It renders local Gold GeoJSON segments and, in the UI, requests `/segments/geojson?city={city}&include_demo_coverage=true` to add clearly marked interpolated demo coverage lines. The current local dataset has about 75 Hanoi measured/latest Gold segments and about 72 HCMC measured/latest Gold segments from TomTom Flow Segment snapshots; the expanded map view displays about 150 Hanoi lines and about 140 HCMC lines by adding `demo_coverage_interpolated` overlays. Do not describe the overlay as live measured citywide coverage. If the API is unavailable, the UI marks unavailable data clearly.

3. Alerts

   Open Alerts. Active alert rows are generated from local traffic conditions, not silent hard-coded production data.

4. Hotspots

   Open Hotspots. Current hotspot clusters come from `/hotspots?city=hanoi` using local traffic state.

5. Forecast

   Open Forecast. Select a real segment such as `HN_005`. The page calls:

   ```text
   /traffic/predict/HN_005?horizon=15m
   /traffic/predict/HN_005?horizon=60m
   ```

   Show current speed, predicted speed, model name, model artifact/source, latest timestamp, and feature coverage. If `filled_feature_count > 0`, the UI shows `Partial feature fill`.

6. Predicted Hotspots API

   Use Swagger or curl to show predictive analytics beyond the current map:

   ```bash
   curl "http://localhost:8000/hotspots/predicted?city=hanoi&horizon=15m"
   curl "http://localhost:8000/hotspots/predicted?city=hanoi&horizon=60m"
   ```

   This endpoint runs the LightGBM model over latest local segments and flags predicted congestion risks using transparent demo rules.

## Important Demo Endpoints

```text
GET /dashboard/summary?city=hanoi
GET /segments/geojson?city=hanoi
GET /traffic/segments?city=hanoi
GET /traffic/predict/{segment_id}?horizon=15m
GET /traffic/predict/{segment_id}?horizon=60m
GET /hotspots/predicted?city=hanoi&horizon=15m
GET /traffic/model/status?load_models=true
GET /system/status
```

## Quick Smoke Commands

```bash
curl "http://localhost:8000/dashboard/summary?city=hanoi"
curl "http://localhost:8000/segments/geojson?city=hanoi"
curl "http://localhost:8000/traffic/segments?city=hanoi"
curl "http://localhost:8000/traffic/predict/HN_005?horizon=15m"
curl "http://localhost:8000/traffic/predict/HN_005?horizon=60m"
curl "http://localhost:8000/hotspots/predicted?city=hanoi&horizon=15m"
curl "http://localhost:8000/traffic/model/status?load_models=true"
curl "http://localhost:8000/system/status"
```

## Demo Evidence Commands

Run smoke checks and write reproducibility evidence:

```bash
make demo-check
```

Run endpoint benchmark evidence:

```bash
make benchmark-demo
```

Run minimal Kafka evidence if Kafka is already running:

```bash
make streaming-mini-demo
```

## Presenter Notes

- The demo is local-first and reproducible with Docker Python 3.11.
- The forecast model name and artifact should be read from `/traffic/model/status` or the Forecast API response. Do not hard-code the model family in the presentation.
- Some model inputs are filled because the current Gold data does not contain every training feature.
- The current Hanoi coverage is suitable for a capstone prototype demo, not a full-city operational deployment.
- `/hotspots/predicted` is prototype explainable risk scoring, not a production risk engine.
