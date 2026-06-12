# Known Limitations

This project is ready for a capstone/demo walkthrough, but it is not a production traffic platform. The points below should be stated clearly in reports and presentations.

## Data Coverage

- Latest local Gold traffic coverage is currently about 75 Hanoi segments and about 72 HCMC segments from TomTom Flow Segment snapshots, with real geometry when TomTom returns coordinates.
- Live Map can request `include_demo_coverage=true` to display interpolated demo coverage lines. These lines improve visual city coverage for demo navigation, but they are explicitly marked as `demo_coverage_interpolated` and must not be described as live measured road segments.
- With the demo overlay enabled, the current Live Map displays about 150 Hanoi lines and about 140 HCMC lines; only the `local_gold` subset is backed by local Gold/TomTom traffic measurements.
- The dataset is not full-city coverage and does not cover every road, ward, or district in Hanoi.
- The local data is built from controlled crawls and generated Silver/Gold artifacts, not a continuously operating citywide feed.

## Forecasting

- The Forecast page uses real backend inference through the default LightGBM model bundle.
- The current model input schema has 67 required features.
- Local Gold data still requires partial feature fill for demo inference. A typical Hanoi segment such as `HN_005` fills about 15 of 67 features.
- The UI exposes this as `Partial feature fill`; predictions should be presented as prototype model outputs, not final operational forecasts.

## Predicted Hotspots

- `/hotspots/predicted` is a prototype explainable risk scoring endpoint.
- It uses configurable thresholds in `config/risk_scoring.yaml` and returns `risk_score`, `risk_level`, `triggered_rules`, and `context_explanation`.
- The score combines forecast output, current speed/free-flow comparison, current jam factor, weather context, and event/news aggregate features when available.
- It is not a production risk engine, incident prediction service, or calibrated traffic-control decision system.

## Monitoring And System Health

- `/system/status` exposes real local demo status for API uptime, Gold data, model readiness, benchmark report status, and streaming mini-demo status.
- Monitoring is still not a full telemetry stack. Missing runtime metrics are shown as `not_measured` or `not_available`, not inferred.

## Streaming And Infrastructure

- The architecture includes Kafka, Redis, Postgres, MinIO, Trino, Airflow, and related big-data components.
- In the current demo state, the reliable path is local/batch-oriented processing over `raw/` and `data/`.
- `make streaming-mini-demo` provides minimal Kafka produce/consume evidence when Kafka is running. If Kafka is not running, the report is marked `SKIPPED`.
- Real streaming ingestion and full infrastructure integration are not yet productionized.

## Actual vs Target Architecture

- See `docs/actual_vs_target_architecture.md` for a component-by-component distinction between demo implementation and production target.

## Performance Evidence

- Use `make benchmark-demo` or `python scripts/smoke_benchmark.py --base-url http://localhost:8000 --runs 20` to generate `docs/performance_report.md`.
- Performance metrics are not production SLA evidence. If the API is not running, report rows are marked failed or `NOT MEASURED`.

## Model Artifacts

- Model artifacts are not committed to normal Git history.
- `cta_training_outputs/` and `results/cta_training_outputs_balanced_v3_latest/` are ignored to avoid storing large binary artifacts in Git.
- Use Git LFS, object storage, or a model registry for long-term artifact management.

## Frontend Fallbacks

- Live Map has explicit fallback behavior for demo continuity.
- Fallback data is labeled and should not be described as live API data.

## External Services

- Live crawling depends on external API keys and quotas.
- `.env.local` must remain local and must not be committed or printed in logs.
