# Performance Report

Generated at: 2026-06-12T01:24:52.317015+00:00
Base URL: `http://localhost:8000`
Runs per endpoint: `20`

| Endpoint | Success rate | p50 ms | p95 ms | Avg ms | Payload KB | Status |
|---|---:|---:|---:|---:|---:|---|
| `/health` | 100% | 0.5 | 0.88 | 0.63 | 0.1 | PASS |
| `/dashboard/summary?city=hanoi` | 100% | 12.37 | 118.64 | 33.03 | 0.26 | PASS |
| `/segments/geojson?city=hanoi` | 100% | 37.36 | 90.19 | 46.92 | 491.89 | PASS |
| `/segments/geojson?city=hcmc` | 100% | 33.69 | 131.99 | 59.17 | 496.02 | PASS |
| `/segments/geojson?city=hcmc&include_demo_coverage=true` | 100% | 37.18 | 82.69 | 43.93 | 520.13 | PASS |
| `/traffic/segments?city=hanoi` | 100% | 11.19 | 25.27 | 14.91 | 8.96 | PASS |
| `/traffic/predict/HN_005?horizon=15m` | 100% | 17.45 | 23.03 | 18.16 | 0.91 | PASS |
| `/traffic/predict/HN_005?horizon=60m` | 100% | 16.76 | 23.34 | 17.77 | 0.91 | PASS |
| `/hotspots/predicted?city=hanoi&horizon=15m` | 100% | 1.11 | 1.86 | 1.15 | 84.32 | PASS |
| `/traffic/model/status?load_models=true` | 100% | 4.46 | 5.62 | 4.67 | 2.27 | PASS |
| `/system/status` | 100% | 360.28 | 410.48 | 362.73 | 1.49 | PASS |

## Notes

- Suitable for local demo: yes
- Production-ready: no
- Bottlenecks: `/hotspots/predicted` uses short-TTL cache for demo responsiveness; cold path still needs precomputed/batch risk scoring before scale-out.

## Extra Metrics

- Model load time: `{'15m': 594.58, '60m': 27.25}` (measured_in_benchmark_process)
- Model inference time: `{'15m': 163.57, '60m': 20.62}` (measured_in_benchmark_process)
- API memory after model load: `123.11` MB (measured_from_procfs)
- Frontend build time: npm run build completed in 7.05s (PASS)
