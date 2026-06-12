# Demo Smoke Report

Generated at: 2026-06-12T01:24:51.113866+00:00
Base URL: `http://localhost:8000`

| Check | Status | Detail |
|---|---|---|
| API health | PASS | 200 OK |
| Dashboard summary | PASS | summary returned |
| GeoJSON Hanoi real | PASS | 75 features |
| GeoJSON HCMC real | PASS | 72 features |
| GeoJSON HCMC expanded | PASS | 140 features |
| Traffic segments | PASS | segments > 0 |
| Forecast 15m | PASS | model=lightgbm_main, coverage=52/67, latency_ms=1412.8 |
| Forecast 60m | PASS | model=lightgbm_main, coverage=52/67, latency_ms=128.4 |
| Predicted hotspots | PASS | risk list returned |
| Model status | PASS | model status returned |
| System status | PASS | system status returned |
| Frontend build | PASS | npm run build completed in 7.05s |

Overall status: **PASS**

Endpoint failures are real demo blockers. Optional local dependencies such as Bun may be marked SKIPPED.
