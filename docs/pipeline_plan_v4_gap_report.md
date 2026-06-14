# Pipeline vs IMPLEMENTATION_PLAN_v4_Cognitive_Intelligence

Generated: 2026-06-13

## Summary

Current project is a working local-demo pipeline, not a full cloud lakehouse deployment yet. It matches the plan at the code-structure and API-demo level for ingestion, Silver/Gold local datasets, model serving, monitoring, and cognitive API surfaces. It still needs real cloud credentials, real 240m model artifacts, and Neo4j AuraDB data loading to fully match plan v4.

## Matches Plan

| Area | Current status |
|---|---|
| Kafka/Schema Registry | Compose services and topic creation target exist. |
| Producers | TomTom, weather, news, and combined traffic-weather producers exist. |
| Bronze/Silver/Gold local path | Local build targets and scripts produce Silver/Gold snapshots for demo/API. |
| TomTom Stats | Async client and loader exist, but production quota/config must be verified. |
| OSM import | OSMnx importer exists for road network import. |
| FastAPI | Traffic, alerts, hotspots, explain, monitoring, settings, routing, dashboard, system routes exist. |
| Cognitive API | Prediction reliability, what-if simulation, graph propagation, corridor risk, and smart alert fields are now wired. |
| Model serving | 15m/60m local artifacts are supported; model status now reports 240m readiness too. |
| Demo evidence | Smoke-check script writes `docs/demo_smoke_report.*`. |

## Added To Align With Plan V4

| Requirement | Added files/changes |
|---|---|
| Neo4j AuraDB configuration | `.env.example`, `docker-compose.yml`, `infra/settings.py` |
| AuraDB connectivity check | `scripts/check_neo4j_aura.py`, `make check-neo4j` |
| Graph schema | `infra/neo4j-aura/constraints.cypher`, `indexes.cypher`, `sample-import.cypher` |
| No default local Neo4j | `neo4j` service moved to Compose profile `local-graph` |
| Demo paths | `make demo-lite`, `make demo-full` |
| Cognitive intelligence layer | `intelligence/` package |
| Plan API endpoints | `/model/status`, `/graph/propagation/{segment_id}`, `/corridors/risk`, `/traffic/simulate` |

## Remaining Gaps

| Priority | Gap | Next action |
|---|---|---|
| P0 | 240m forecast artifact missing | Train/export `selected_model_240m_speed_lightgbm_main.joblib` and metadata. |
| P0 | MLflow logging/registry not fully wired | Add MLflow logging to training script and expose registry version in API. |
| P0 | SHAP endpoint is not guaranteed to use real per-prediction SHAP | Generate batch SHAP outputs or compute SHAP from loaded LightGBM model. |
| P1 | Neo4j AuraDB has schema/check script but no full OSM loader to AuraDB yet | Implement `graph/load_road_network.py` or CSV export + `LOAD CSV`. |
| P1 | Gold tables for risk/audit are prototype-only | Materialize `gold_segment_risk_scores`, `gold_corridor_risk_scores`, `gold_prediction_audit_log`. |
| P1 | Docker Compose still uses MinIO as local fallback | Keep for local demo, but production plan should point Spark/Trino to AWS S3. |
| P1 | Frontend wiring not verified here | Connect UI to new cognitive endpoints and update smoke coverage. |

## Current Assessment

The pipeline is now closer to plan v4 for demo defense: it exposes the cognitive capabilities and infrastructure hooks required by the plan. It is not yet a full implementation of the cloud lakehouse + AuraDB production path because that requires credentials, data loading, model retraining, and MLflow registry integration.
