# Demo Smoke Report

Generated at: 2026-06-13T23:27:01.606559+00:00
Base URL: `http://localhost:8000`

| Check | Status | Detail |
|---|---|---|
| API health | PASS | 200 OK |
| Dashboard summary | PASS | summary returned |
| GeoJSON Hanoi real | PASS | 10 features |
| GeoJSON HCMC real | PASS | 10 features |
| GeoJSON HCMC expanded | PASS | 620 features |
| Traffic segments | PASS | segments > 0 |
| Forecast 15m | PASS | model=extra_trees, coverage=62/62, latency_ms=2968.9 |
| Forecast 60m | PASS | model=extra_trees, coverage=62/62, latency_ms=594.7 |
| Forecast reliability | PASS | model=extra_trees, coverage=62/62, latency_ms=45.9 |
| Predicted hotspots | PASS | risk list returned |
| Model status | PASS | model status returned |
| Graph propagation | PASS | propagation returned |
| Corridor risk | PASS | corridor risk returned |
| System status | PASS | system status returned |
| What-if simulation | PASS | scenario impact returned |
| Frontend build | PASS | npm run build completed in 57.56s |

Overall status: **PASS**

Endpoint failures are real demo blockers. Optional local dependencies such as Bun may be marked SKIPPED.
