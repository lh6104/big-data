# Cloud & Pipeline Status Report

Generated: 2026-06-14 Asia/Bangkok

## Result

The local serving pipeline and cloud evidence paths are mostly operational after this check.

## Cloud Platforms

| Platform | Status | Evidence |
|---|---|---|
| AWS S3 bucket | PASS | `traffic-cg` reachable in `ap-southeast-1` |
| S3 Bronze | PASS | `bronze/`: 7 objects, 1,356,370 bytes |
| S3 Silver | PASS | `silver/local_demo/`: 6 objects, 42,959,462 bytes |
| S3 Gold | PASS | `gold/local_demo/`: 28 objects, 141,862,004 bytes |
| S3 Model artifacts | PASS | `artifacts/model_pack/`: 18 objects, 32,377,824 bytes |
| S3 Warehouse | GAP | `warehouse/`: placeholder only, 1 object, 0 bytes |
| Neo4j AuraDB connectivity | PASS | `RETURN 1` succeeded from API container |
| Neo4j AuraDB graph data | PASS | 62 nodes, 78 relationships |
| Neo4j schema | PASS | RoadSegment, Intersection, RoadNode, District constraints exist |

## Local Pipeline

| Layer | Status | Evidence |
|---|---|---|
| Docker services | PASS | API, Kafka, Schema Registry, Postgres, Redis, MinIO, Hive Metastore, Trino, Spark, Airflow are up |
| Container networking | PASS | API container connects to Postgres, Redis, Kafka, Schema Registry, Hive Metastore, and MinIO |
| Kafka topics | PASS | `events.news`, `traffic.realtime.tomtom`, `weather.current`, `traffic.alerts`, DLQ topics, plus mini-demo raw topics |
| Streaming mini demo | PASS | Produced 9 messages, consumed 9 messages, wrote `data/bronze/streaming_mini_demo.jsonl` |
| API/model smoke | PASS | `scripts/demo_check.py --base-url http://localhost:8000` overall PASS |
| Airflow | PASS | `/health` reports metadatabase and scheduler healthy |
| Trino catalog | PARTIAL | `SHOW CATALOGS` returns `hive` and `system` |
| Trino write to MinIO warehouse | GAP | Hive catalog loads, but `CREATE SCHEMA ... location='s3://warehouse/cta/'` fails creating external path |

## Assessment

Stream, Bronze/Silver/Gold local data, model serving, S3 evidence storage, and Neo4j AuraDB graph data are now present and verifiable.

The remaining cloud/lakehouse gap is the query warehouse path: Trino can load the Hive catalog, but cannot yet write/query managed lakehouse tables in MinIO/S3 warehouse. The current S3 `warehouse/` prefix is still empty except for a placeholder, so this part is not fully pipeline-ready.
