# Phase 1 Pipeline Testing Guide

**Status:** ✅ Pre-flight check passed  
**Date:** 2026-05-31

---

## Prerequisites Checklist ✅

- [x] Docker installed and running
- [x] Docker Compose available
- [x] All Phase 1 code files present
- [x] Python environment configured
- [x] Project structure complete

---

## Testing Strategy

Phase 1 testing validates the complete data ingestion pipeline:

```
External APIs → Producers → Kafka → Spark → Iceberg (Bronze)
```

---

## Step 1: Start Docker Stack (5-10 minutes)

### Option A: Using Make (Recommended)

```bash
cd /home/longha/Desktop/leue

# Start all services
make up

# Wait for services to be ready (check logs)
make logs

# Create Kafka topics
make create-topics

# Verify health
make health
```

### Option B: Manual Docker Compose

```bash
docker-compose -f docker-compose.yml up -d
docker-compose ps

# Wait ~30-60 seconds for services to stabilize
sleep 30

# Create Kafka topics manually
docker exec kafka kafka-topics --create --topic events.news \
  --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
docker exec kafka kafka-topics --create --topic traffic.realtime.tomtom \
  --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
docker exec kafka kafka-topics --create --topic weather.current \
  --bootstrap-server localhost:9092 --partitions 2 --replication-factor 1
```

### Verify Services Are Running

```bash
# Check Docker containers
docker ps | grep -E "kafka|postgres|mongo|redis|spark|minio"

# Should see output like:
# kafka:9092, spark-master:7077, postgres:5432, mongodb:27017, redis:6379, minio:9000
```

---

## Step 2: Test Kafka Connectivity

### Verify Kafka is ready

```bash
# List topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Should output:
# events.news
# traffic.realtime.tomtom
# weather.current
```

### Send a test message

```bash
# Send test message to events.news
echo '{"event_id":"test_001","source":"test","title":"Test Event"}' | \
  docker exec -i kafka kafka-console-producer --broker-list localhost:9092 \
  --topic events.news

# Consume the message
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic events.news --from-beginning --max-messages 1
```

---

## Step 3: Run News Producer Test

This tests the News crawler + Kafka producer integration:

```bash
# Terminal 1: Run news producer
cd /home/longha/Desktop/leue
conda activate traffic_cognitive
python3 ingestion/producers/news_producer.py

# Terminal 2: Monitor Kafka topic
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic events.news --from-beginning
```

**Expected Output:**
- Messages flowing into `events.news` topic
- Each message is a parsed news article in JSON format

---

## Step 4: Run Weather Producer Test

This tests the OpenWeatherMap API producer:

```bash
# You need to set OWM_API_KEY first
export OWM_API_KEY="your_api_key_here"

# Terminal 1: Run weather producer
python3 ingestion/producers/weather_producer.py

# Terminal 2: Monitor Kafka topic  
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic weather.current --from-beginning
```

**Expected Output:**
- Temperature, humidity, weather data for Hanoi and HCMC
- Updates every 15-60 minutes

---

## Step 5: Run TomTom Producer Test

This tests the TomTom Flow API producer:

```bash
# You need to set TOMTOM_API_KEY first
export TOMTOM_API_KEY="your_api_key_here"

# Terminal 1: Run TomTom producer
python3 ingestion/producers/tomtom_producer.py

# Terminal 2: Monitor Kafka topic
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic traffic.realtime.tomtom --from-beginning
```

**Expected Output:**
- Traffic segment data (speed, jam factor, congestion)
- Updates every 5-30 minutes based on time of day

---

## Step 6: Test Spark Streaming (Bronze Layer)

### Start Spark Consumer for News Events

```bash
# Terminal: Run Spark streaming job
spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  processing/bronze/kafka_to_bronze.py \
  kafka:9092 events.news s3a://lakehouse

# Should see logs like:
# "Starting streaming from events.news → bronze_events_raw"
# "Writing to Iceberg table..."
```

### Verify Data in Bronze Layer

```bash
# Check MinIO for data
docker exec minio mc ls minio/lakehouse/bronze_events_raw/

# Or query with Spark SQL
spark-sql \
  --master spark://spark-master:7077 \
  -e "SELECT COUNT(*) FROM iceberg.bronze_events_raw"
```

---

## Step 7: Run Aligned Producer Test

Test synchronized traffic + weather collection:

```bash
# Terminal 1: Run aligned producer
python3 ingestion/producers/traffic_weather_producer.py --bucket-minutes 5

# Terminals 2-3: Monitor both topics
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic traffic.realtime.tomtom --max-messages 5

docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic weather.current --max-messages 5
```

**Expected Output:**
- Both topics receive messages at approximately the same time
- Data is synchronized in 5-minute buckets

---

## Step 8: Test Airflow DAGs

### Access Airflow UI

```bash
# Visit Airflow web UI
open http://localhost:8080

# Login: admin / admin
```

### Trigger DAGs manually

```bash
# Trigger silver processing DAG
docker exec airflow-webserver airflow dags test silver_processing 2026-05-31

# Trigger data quality DAG
docker exec airflow-webserver airflow dags test data_quality_checks 2026-05-31
```

---

## Monitoring & Debugging

### Health Check

```bash
# Built-in health check
make health

# Manual checks
docker ps
docker-compose logs

# Kafka lag
docker exec kafka kafka-consumer-groups --bootstrap-server localhost:9092 \
  --describe --all-groups
```

### View Logs

```bash
# All service logs
make logs

# Specific service
docker-compose logs kafka
docker-compose logs spark-master
docker-compose logs postgres
```

### Access Web Consoles

- **MinIO**: http://localhost:9001 (minioadmin / minioadmin)
- **Airflow**: http://localhost:8080 (admin / admin)
- **Neo4j**: http://localhost:7474 (neo4j / password)
- **Spark UI**: http://localhost:4040

---

## Troubleshooting

### "Kafka broker not available"
- Check if kafka container is running: `docker ps | grep kafka`
- Wait a bit longer - Kafka takes 10-20 seconds to start
- Check logs: `docker-compose logs kafka`

### "Connection refused: spark-master:7077"
- Spark might still be starting
- Try again in 30 seconds
- Check logs: `docker-compose logs spark-master`

### "S3AFileSystem not found"
- Spark packages not downloaded yet
- First submission takes longer
- Increase timeout or check internet connection

### "MinIO connection failed"
- Wait for MinIO to be ready
- Check credentials (minioadmin / minioadmin)
- Verify endpoint: http://minio:9000

---

## Expected Results

### After News Producer (15-30 seconds)
```
✓ Messages appearing in events.news topic
✓ JSON format validation passes
✓ Kafka consumer can read messages
```

### After Spark Streaming (30-60 seconds)
```
✓ Streaming checkpoint created
✓ Data written to Iceberg table
✓ MinIO shows /lakehouse/bronze_events_raw/ directory
```

### After Airflow DAGs Trigger (1-5 minutes)
```
✓ DAG execution shows success/failure status
✓ Task logs available in Airflow UI
✓ Lineage visible in graph view
```

---

## Performance Baseline

| Component | Metric | Expected |
|-----------|--------|----------|
| Kafka Throughput | msgs/sec | 100-1000 |
| Spark Latency | seconds | < 10 (per batch) |
| Bronze Table Inserts | rows/min | 100-1000 |
| API Response | seconds | 1-5 |

---

## Test Completion Checklist

- [ ] Docker services started successfully
- [ ] Kafka topics created
- [ ] Test message sent and consumed
- [ ] News producer ran and sent data to Kafka
- [ ] Weather producer ran (if API key set)
- [ ] TomTom producer ran (if API key set)
- [ ] Spark streaming job started
- [ ] Data appeared in MinIO / Iceberg
- [ ] Airflow DAGs accessible
- [ ] Health check passed
- [ ] All logs clean (no errors)

---

## Next: Phase 2

Once Phase 1 tests pass:

1. Implement `clean_traffic.py` for traffic data cleaning
2. Implement `clean_weather.py` for weather normalization
3. Create `map_osm_segments.py` for road mapping
4. Test Silver layer end-to-end
5. Proceed to Phase 2 data quality monitoring

---

## Support

For issues:

1. Check logs: `make logs`
2. Verify services: `make health`
3. Review docker-compose.yml configuration
4. Check API keys (.env file)
5. Review producer code for bugs

---

**Phase 1 testing is complete when all services are stable and data flows end-to-end through the pipeline.**
