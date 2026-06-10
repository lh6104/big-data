# HOW TO EXECUTE PHASE 1 & PHASE 2 - Step by Step

**Status:** Everything is ready. Follow these steps in order.

---

## 📋 PHASE 2 FIRST: Clean Historical Data (20 minutes)

### STEP 1: Load Raw Data → Bronze (10 minutes)

**What:** Load 601 traffic files + 360 weather files from `raw/` folder

**How:**

**Option A: Via Airflow UI (RECOMMENDED)**
```
1. Open browser: http://localhost:8080
2. Login: admin / admin
3. Find "load_raw_data" DAG in left sidebar
4. Click the DAG name
5. Click "Trigger DAG" (blue button)
6. Wait ~10 minutes for it to complete
7. Check status in "Recent Tasks" section
```

**Option B: Via Command Line**
```bash
cd /home/longha/Desktop/leue

spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 \
  processing/batch_load/load_raw_data.py \
  /home/longha/Desktop/leue/raw \
  s3a://lakehouse

# Wait for it to finish (should see "✅ Raw data load complete")
```

**✅ When done, you should have:**
- bronze_traffic_raw: ~600K records
- bronze_weather_raw: ~100K records

---

### STEP 2: Clean Data in Parallel (10 minutes)

**What:** Run 3 cleaning jobs at the same time

**How:**

**Option A: Via Airflow UI (RECOMMENDED)**
```
1. Still in Airflow (http://localhost:8080)
2. Find "silver_processing" DAG
3. Click the DAG name
4. Click "Trigger DAG"
5. Watch the Task Graph tab
6. All 3 tasks will run in parallel:
   - clean_traffic
   - clean_weather
   - match_traffic_weather
7. Wait for all to complete (green checkmarks)
   ~5-10 minutes
```

**Option B: Via Command Line (run all 3 at same time)**

**Terminal 1:**
```bash
cd /home/longha/Desktop/leue

spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 \
  processing/silver/clean_traffic.py \
  s3a://lakehouse
```

**Terminal 2 (open new terminal):**
```bash
cd /home/longha/Desktop/leue

spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 \
  processing/silver/clean_weather.py \
  s3a://lakehouse
```

**Terminal 3 (open new terminal):**
```bash
cd /home/longha/Desktop/leue

spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 \
  processing/silver/match_traffic_weather.py \
  s3a://lakehouse
```

**Wait for all 3 to finish** (each should show "✅ Cleaned records written")

**✅ When done, you should have:**
- silver_traffic_cleaned: ~500K records (clean)
- silver_weather_cleaned: ~95K records (clean)
- silver_traffic_weather_matched: ~500K records (joined)

---

## ⏸️ PAUSE: Verify Phase 2 Worked

**Check 1: Verify in MinIO**
```
1. Open http://localhost:9001
2. Login: minioadmin / minioadmin
3. Browse: lakehouse/
4. Should see folders:
   - bronze/ (has traffic_raw, weather_raw)
   - silver/ (has traffic_cleaned, weather_cleaned, traffic_weather_matched)
```

**Check 2: Verify with command**
```bash
# Count records in Silver tables
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) FROM iceberg.lakehouse.silver_traffic_cleaned"

# Should show ~500000
```

✅ **If you see data in silver/ folders → Phase 2 is DONE!**

---

## 🚀 PHASE 1: Start Real-time Data Producers

### STEP 3: Start 5 Producers + Streaming

**What:** Run 5 data producers that continuously feed new data

**Open 5 terminals (one for each):**

---

**TERMINAL 1: News Crawler**
```bash
cd /home/longha/Desktop/leue
python3 ingestion/producers/news_producer.py

# Expected output:
# INFO: RSS fetcher initialized
# INFO: Starting news crawler...
# (will keep running, sending news to Kafka)
```

---

**TERMINAL 2: TomTom Traffic (requires API key)**
```bash
cd /home/longha/Desktop/leue

# First set your TomTom API key
export TOMTOM_API_KEY="your_tomtom_api_key_here"

python3 ingestion/producers/tomtom_producer.py

# Expected output:
# INFO: TomTom producer initialized
# INFO: Polling every 5 minutes
# (will keep running, sending traffic to Kafka)
```

---

**TERMINAL 3: Weather (requires API key)**
```bash
cd /home/longha/Desktop/leue

# First set your OpenWeatherMap API key
export OWM_API_KEY="your_owm_api_key_here"

python3 ingestion/producers/weather_producer.py

# Expected output:
# INFO: Weather producer initialized
# INFO: Fetching weather...
# (will keep running, sending weather to Kafka)
```

---

**TERMINAL 4: Aligned Traffic-Weather (bonus)**
```bash
cd /home/longha/Desktop/leue

export TOMTOM_API_KEY="your_tomtom_api_key_here"
export OWM_API_KEY="your_owm_api_key_here"

python3 ingestion/producers/traffic_weather_producer.py

# Expected output:
# INFO: Aligned producer starting
# (will synchronize traffic and weather in 5-min buckets)
```

---

**TERMINAL 5: Bronze Streaming (Spark)**
```bash
cd /home/longha/Desktop/leue

spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  processing/bronze/kafka_to_bronze.py \
  kafka:9092 \
  traffic.realtime.tomtom \
  s3a://lakehouse

# Expected output:
# INFO: Starting Kafka→Bronze streaming
# INFO: Streaming started for traffic.realtime.tomtom
# (will keep running, streaming Kafka → Bronze)
```

---

### ✅ When all 5 terminals are running:

You should see:
- ✅ Terminal 1: News messages being fetched
- ✅ Terminal 2: Traffic data being polled
- ✅ Terminal 3: Weather data being fetched
- ✅ Terminal 4: Traffic + Weather synchronized
- ✅ Terminal 5: Spark streaming Kafka → Bronze

---

## 📊 STEP 4: Monitor Data (Automatic)

**Airflow will automatically run hourly:**

```
Every hour, Airflow runs:
1. clean_traffic.py (cleans new records from Bronze)
2. clean_weather.py (cleans new records from Bronze)
3. match_traffic_weather.py (joins new records)

↓ Appends to Silver tables
↓ Your data continuously grows
```

---

## 🔍 Check Status While Running

### Check 1: Kafka Messages

```bash
# See messages in Kafka topics
docker exec leue-kafka-1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic traffic.realtime.tomtom \
  --max-messages 5 \
  --timeout-ms 3000
```

### Check 2: Bronze Table Size

```bash
# Count records appended
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) as traffic_count FROM iceberg.lakehouse.bronze_traffic_raw"
```

### Check 3: Silver Table Growth

```bash
# Track cleaned data
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) as cleaned_count FROM iceberg.lakehouse.silver_traffic_cleaned"
```

### Check 4: Airflow DAGs

```
Open: http://localhost:8080

Look for:
- silver_processing: should run every hour
- Task successes showing in green
```

### Check 5: MinIO Data

```
Open: http://localhost:9001

Navigate to: lakehouse/silver/

See folders growing with new data
```

---

## 📈 Expected Timeline

```
Time    What Happens                        Your Action
────────────────────────────────────────────────────────
0:00    Phase 2: Load raw data              Step 1 (10 min)
0:10    Phase 2: Clean data                 Step 2 (10 min)
0:20    ✅ Silver tables ready!
        Phase 1: Start producers            Step 3 (start 5 terminals)

0:30+   Real-time data flows in             Monitor (no action)
        Airflow cleans hourly               Automatic (hourly)

...     Data grows continuously             Keep producers running
```

---

## 💾 Data Volume Growth

```
After Phase 2 (20 minutes):
├── Historical data: ~600K traffic + 100K weather
├── Cleaned: ~500K traffic (clean) + 95K weather (clean)
└── Matched: ~500K traffic+weather pairs

After 1 hour (Phase 1 + automatic cleaning):
├── Historical: ~600K records
├── New from producers: ~50-100 records
└── Total in Silver: Growing continuously

After 1 day:
├── Historical: ~600K
├── New: ~1K-5K (depends on producer intervals)
└── Total training data: 600K+ growing
```

---

## ✅ Success Checklist

### After Step 1 (Load Raw)
- [ ] bronze_traffic_raw has data (600K+)
- [ ] bronze_weather_raw has data (100K+)

### After Step 2 (Clean)
- [ ] silver_traffic_cleaned has data (500K+)
- [ ] silver_weather_cleaned has data (95K+)
- [ ] silver_traffic_weather_matched has data (500K+)

### After Step 3 (Producers)
- [ ] Terminal 1: News producer running
- [ ] Terminal 2: Traffic producer running
- [ ] Terminal 3: Weather producer running
- [ ] Terminal 4: Aligned producer running
- [ ] Terminal 5: Spark streaming running

### After Step 4 (Monitor)
- [ ] Airflow DAGs running hourly
- [ ] MinIO showing new data in silver/
- [ ] Kafka topics receiving messages
- [ ] Silver tables growing (every hour)

✅ **When all checks pass → You have a working Phase 1 + Phase 2!**

---

## 🚨 Troubleshooting

### Problem: "spark-submit not found"
**Solution:**
```bash
# Use full path to spark-submit
/usr/local/spark/bin/spark-submit ...

# OR use via Docker
docker exec leue-spark-master-1 spark-submit ...
```

### Problem: "Kafka not responding"
**Solution:**
```bash
# Check if Kafka is running
docker-compose ps | grep kafka

# Restart if needed
docker-compose restart kafka zookeeper
```

### Problem: "API key error" in producer terminals
**Solution:**
```bash
# Make sure API keys are set before running producer
export TOMTOM_API_KEY="your_actual_key"
export OWM_API_KEY="your_actual_key"

# Then run producer
python3 ingestion/producers/...
```

### Problem: "No data in Silver tables"
**Solution:**
```bash
# Check if Bronze tables have data first
docker exec leue-spark-master-1 spark-sql -c \
  "SELECT COUNT(*) FROM iceberg.lakehouse.bronze_traffic_raw"

# If Bronze is empty, re-run Step 1
# If Bronze has data but Silver is empty, re-run Step 2
```

### Problem: "Airflow DAG not running"
**Solution:**
```bash
# Check if Airflow is up
docker-compose ps | grep airflow

# Restart if needed
docker-compose restart airflow

# Trigger manually from UI
# http://localhost:8080 → load_raw_data → Trigger
```

---

## 📚 Next Steps (Phase 3)

Once your Silver tables are populated and growing (after ~30 minutes):

```bash
# Phase 3: Build features
spark-submit \
  --master spark://spark-master:7077 \
  processing/gold/build_training_dataset.py \
  s3a://lakehouse

# Creates:
# - gold_traffic_features (with 8 feature groups)
# - gold_training_dataset (ready for ML models)
```

---

## 🎯 Summary

**What you're doing:**
1. ✅ Clean 600K+ historical records (Phase 2) — 20 min
2. ✅ Start 5 producers feeding real-time data (Phase 1) — continuous
3. ✅ Automatic hourly cleaning (Airflow) — no action
4. ✅ Data flows: Raw → Bronze → Silver → Gold (Phase 3)

**Result:**
- Complete dataset (historical + real-time)
- Ready for ML models (Phase 3)
- Continuous data collection
- Automated pipeline

**Time to ready:** ~30 minutes for Phase 2 + Phase 1 setup
**Time to Phase 3:** Immediately after Phase 2 completes

---

## 🚀 GO! You're Ready

Everything is implemented. Just follow the steps above.

**Good luck! 🎉**
