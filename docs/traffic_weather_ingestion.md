# Traffic + Weather Ingestion Design

## Kafka Topic Design

| Topic | Key | Producer | Purpose |
| --- | --- | --- | --- |
| `traffic.raw` | `segment_id` | `collectors/traffic_weather_producer.py` | Bronze TomTom traffic flow records |
| `weather.raw` | `weather_cell_id` | `collectors/traffic_weather_producer.py` | Bronze OpenWeatherMap current weather records |

Both topics use JSON values. The producer writes local JSONL snapshots in `data/raw/traffic/` and `data/raw/weather/` for offline testing when Kafka is unavailable.

## Bronze Raw Schemas

TomTom `traffic.raw` includes:

```text
source, provider, city, segment_id, segment_name, weather_cell_id,
lat, lon, event_time, ingestion_time, time_bucket,
currentSpeed, freeFlowSpeed, currentTravelTime, freeFlowTravelTime,
jamFactor, confidence, roadClosure, raw
```

OpenWeatherMap `weather.raw` includes:

```text
source, provider, city, weather_cell_id, lat, lon,
event_time, api_dt, ingestion_time, time_bucket,
temp, feels_like, humidity, pressure, weather_id, weather_main,
weather_desc, visibility, rain_1h, wind_speed, wind_deg, clouds, raw
```

All timestamps are UTC ISO-8601. `time_bucket` is floored to the configured 5 or 10 minute bucket from the shared polling cycle timestamp. TomTom Flow Segment does not return an observation timestamp, so `event_time` is the collector cycle time. OpenWeatherMap `event_time` is converted from response field `dt`.

## Silver Normalized Schema

Spark writes `data/cleaned/traffic_weather/` with:

```text
city, segment_id, segment_name, weather_cell_id, time_bucket,
traffic_event_ts, weather_event_ts, traffic_ingestion_ts, weather_ingestion_ts,
segment_lat, segment_lon, weather_lat, weather_lon,
current_speed_kmph, free_flow_speed_kmph,
current_travel_time_s, free_flow_travel_time_s,
jam_factor, traffic_confidence, road_closure,
temperature_c, feels_like_c, weather_main, weather_desc,
visibility_m, rain_1h_mm, humidity_pct, wind_speed_mps, clouds_pct
```

## Join Strategy

The producer maps each traffic segment to the nearest Hanoi weather cell and attaches `weather_cell_id` to every traffic record. Spark joins:

```text
traffic.weather_cell_id = weather.weather_cell_id
AND traffic.time_bucket = weather.time_bucket
```

Both streams apply a 20 minute watermark and deduplicate by:

```text
traffic: source, segment_id, time_bucket
weather: source, weather_cell_id, time_bucket
```

## Commands

Run one cycle:

```bash
python3 collectors/traffic_weather_producer.py --once --bucket-minutes 5
```

Run continuously with the UTC dynamic crawl schedule:

```bash
python3 collectors/traffic_weather_producer.py --bucket-minutes 5
```

The default UTC schedule is:

| Source | UTC window | Interval |
| --- | --- | --- |
| TomTom | 23:30-02:00 | 5 minutes |
| TomTom | 02:00-04:00 | 15 minutes |
| TomTom | 04:00-06:30 | 10 minutes |
| TomTom | 06:30-09:30 | 15 minutes |
| TomTom | 09:30-12:30 | 5 minutes |
| TomTom | 12:30-15:00 | 15 minutes |
| TomTom | 15:00-23:30 | 60 minutes |
| OpenWeatherMap | 23:30-15:00 | 15 minutes |
| OpenWeatherMap | 15:00-23:30 | 60 minutes |

For old fixed-interval behavior:

```bash
python3 collectors/traffic_weather_producer.py --fixed-interval --interval-minutes 5 --bucket-minutes 5
```

Create Kafka topics:

```bash
setup/create_topics.sh
```

Run Spark Silver join:

```bash
spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0 \
  spark/traffic_weather_silver_join.py
```

## Data Quality Checks

- Required fields are checked before Kafka publish.
- Records with duplicate `(source, segment_id, time_bucket)` or `(source, weather_cell_id, time_bucket)` are skipped inside the producer process.
- Spark drops duplicate stream records with the same keys.
- Traffic speed must be non-null and between 0 and 200 km/h.
- Free flow speed must be non-null and between 1 and 200 km/h.
- Weather temperature must be non-null and between -10 and 55 Celsius.
- Humidity must be null or between 0 and 100.
- Traffic confidence must be null or at least 0.5.
