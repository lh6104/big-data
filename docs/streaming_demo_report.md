# Streaming Mini Demo Report

Generated at: 2026-06-13T23:25:34.744242+00:00
Bootstrap servers: `kafka:9092`

| Step | Status | Evidence |
|---|---|---|
| Kafka connection | PASS | connected; existing_topics=8 |
| Topic exists | PASS | events.news |
| Topic exists | PASS | created traffic.raw |
| Topic exists | PASS | created weather.raw |
| Producer sent messages | PASS | 9 |
| Consumer read messages | PASS | 9 |
| Bronze output written | PASS | path=data/bronze/streaming_mini_demo.jsonl rows=9 |

Overall status: **PASS**

This is minimal streaming evidence only. It is not a production streaming deployment.
