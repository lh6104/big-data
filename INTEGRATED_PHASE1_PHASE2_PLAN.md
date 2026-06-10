# Integrated Phase 1 + Phase 2 Execution Plan

**Strategy:** Clean historical data FIRST, then add continuous Phase 1 producers

---

## Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     STEP 1: LOAD RAW DATA                       │
│                    (Historical: May 14-20)                      │
└─────────────────────────────────────────────────────────────────┘

  raw/traffic/*.jsonl (601 files)
  raw/weather/*.jsonl (360 files)
           ↓
  Spark: load_raw_data.py
           ↓
  bronze_traffic_raw
  bronze_weather_raw
           ↓
  ~600K traffic records
  ~100K weather records

┌─────────────────────────────────────────────────────────────────┐
│                   STEP 2: CLEAN (Phase 2)                       │
│                  Run in parallel: 3 jobs                        │
└─────────────────────────────────────────────────────────────────┘

  Bronze Tables (Raw)
           ↓
  ┌─────────────────────────────────────────┐
  │  Parallel Cleaning Jobs                 │
  ├─────────────────────────────────────────┤
  │  1. clean_traffic.py                    │
  │     → silver_traffic_cleaned            │
  │                                         │
  │  2. clean_weather.py                    │
  │     → silver_weather_cleaned            │
  │                                         │
  │  3. match_traffic_weather.py            │
  │     → silver_traffic_weather_matched    │
  └─────────────────────────────────────────┘
           ↓
  Silver Tables (Historical data cleaned)
  - 500K+ traffic records (85-95% quality)
  - 90K+ weather records (95%+ quality)
  - 500K+ traffic+weather joined

┌─────────────────────────────────────────────────────────────────┐
│              STEP 3: START Phase 1 PRODUCERS                    │
│          (Real-time data feeds continuously)                    │
└─────────────────────────────────────────────────────────────────┘

  5 Producers (run simultaneously)
  ├── News Crawler → events.news
  ├── TomTom Traffic → traffic.realtime.tomtom
  ├── Weather (OWM) → weather.current
  ├── Aligned (Traffic+Weather) → bonus stream
  └── TomTom Stats → weekly baseline
           ↓
  Kafka (6 topics + DLQs)
           ↓
  Spark: kafka_to_bronze.py (continuous streaming)
           ↓
  bronze_traffic_raw (appends new records)
  bronze_weather_raw (appends new records)
           ↓
  Silver Cleaning (continuous hourly runs)
           ↓
  silver_traffic_cleaned (grows with new data)
  silver_weather_cleaned (grows with new data)
  silver_traffic_weather_matched (grows)

┌─────────────────────────────────────────────────────────────────┐
│         RESULT: Complete training dataset                       │
│    Historical (May 14-20) + Real-time (continuous)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Timeline & Execution

### Timeline
```
Time    Activity                                    Status
─────────────────────────────────────────────────────────────
0:00    Start: Load raw/ data → Bronze             (5-10 min)
0:10    Start: Phase 2 cleaning (parallel jobs)    (5-10 min)
0:20    DONE: Silver tables populated              ✅
        ~600K traffic + 100K weather cleaned
        
0:20    Start: Phase 1 producers                   (continuous)
        - 5 producers → Kafka
        - Spark streaming → Bronze
        - Hourly Silver cleaning
        
0:30    Monitor: Data flowing into Silver          ✅ Live
        Real-time data appends to Silver tables
        
...     Phase 3 ready when you want                (2-3 weeks)
```

### Total Duration
- **Step 1 (Raw data load):** 5-10 minutes
- **Step 2 (Cleaning):** 5-10 minutes  
- **Step 3 (Producers):** Continuous (run 24/7)
- **Total to ready:** ~20 minutes for historical data
- **+ Real-time:** Ongoing data collection

---

## Commands to Execute

### Step 1: Load Raw Data (One-time)

```bash
# Via Airflow (Recommended)
# Open http://localhost:8080
# Dags → load_raw_data → Trigger DAG

# Wait ~10 minutes for completion
```

**What happens:**
- ✅ 601 traffic files → bronze_traffic_raw
- ✅ 360 weather files → bronze_weather_raw
- ✅ Deduplicated by (segment_id, timestamp, source)

---

### Step 2: Run Phase 2 Cleaning (Parallel)

```bash
# These run in parallel (all at same time)
# Can use Spark submit directly or via Airflow

# Option A: Via Spark (Direct)
spark-submit --master spark://spark-master:7077 \
  processing/silver/clean_traffic.py s3a://lakehouse &

spark-submit --master spark://spark-master:7077 \
  processing/silver/clean_weather.py s3a://lakehouse &

spark-submit --master spark://spark-master:7077 \
  processing/silver/match_traffic_weather.py s3a://lakehouse &

wait

# Option B: Via Airflow (Recommended)
# Dags → silver_processing → Trigger manually
# Runs all 3 jobs in parallel
```

**What happens:**
- ✅ Validates & cleans traffic data (85-95% retained)
- ✅ Validates & cleans weather data (95%+ retained)
- ✅ Joins traffic ↔ weather by nearest time
- ✅ Creates silver_traffic_cleaned (500K+ records)
- ✅ Creates silver_weather_cleaned (90K+ records)
- ✅ Creates silver_traffic_weather_matched (500K+ joined records)

**Duration:** ~5-10 minutes

---

### Step 3: Start Phase 1 Producers (Continuous)

```bash
# Terminal 1: News Crawler
python3 ingestion/producers/news_producer.py

# Terminal 2: TomTom Traffic (requires API key)
export TOMTOM_API_KEY="your_key_here"
python3 ingestion/producers/tomtom_producer.py

# Terminal 3: Weather (requires API key)
export OWM_API_KEY="your_key_here"
python3 ingestion/producers/weather_producer.py

# Terminal 4: Aligned Producer (bonus)
python3 ingestion/producers/traffic_weather_producer.py

# Terminal 5: Bronze Streaming (Spark)
spark-submit --master spark://spark-master:7077 \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.0 \
  processing/bronze/kafka_to_bronze.py \
  kafka:9092 traffic.realtime.tomtom s3a://lakehouse
```

**What happens:**
- ✅ Producers fetch data from APIs (TomTom, OWM, RSS)
- ✅ Data goes to Kafka topics
- ✅ Spark continuously streams Kafka → bronze_traffic_raw / bronze_weather_raw
- ✅ New records append to Bronze tables

**Duration:** Continuous (24/7)

---

### Step 4: Monitor Silver Tables (Hourly Auto-run)

```bash
# Airflow automatically runs silver_processing DAG hourly
# No manual action needed

# OR check via Trino:
trino> SELECT COUNT(*) FROM iceberg.lakehouse.silver_traffic_cleaned;
→ Should see count growing as new data comes in

trino> SELECT COUNT(*) FROM iceberg.lakehouse.silver_weather_cleaned;
→ Should see count growing
```

**What happens:**
- ✅ Each hour, new Bronze records are cleaned
- ✅ Silver tables grow with new data
- ✅ Combined dataset: historical + real-time
- ✅ Ready for Phase 3 feature engineering

---

## Data Volume Expectations

### Historical (Raw) Data
```
Traffic:  601 files × ~1000 rows/file = ~600K records
Weather:  360 files × ~300 rows/file = ~100K records
Total:    ~700K raw records
```

### After Cleaning
```
Traffic (cleaned):           500K+ (85% retained)
Weather (cleaned):           95K+ (95% retained)
Traffic ↔ Weather (matched): 500K+ (98% match rate)
```

### Real-time (Phase 1 Producers)
```
News events:      1-5 per hour (RSS crawl)
Traffic updates:  12-288 per hour (5-30 min intervals)
Weather updates:  2-12 per hour (hourly/6-hour intervals)
```

### Combined (Historical + Real-time)
```
Training dataset: 500K+ traffic + weather records
+ Continuous growth from Phase 1 producers
= Complete ML training data
```

---

## Benefits of This Approach

| Aspect | Benefit |
|--------|---------|
| **Speed** | Clean historical data while setting up producers |
| **Completeness** | Start with 600K historical records + continuous new data |
| **Testing** | Phase 2 cleaned pipeline tested on real data immediately |
| **ML Ready** | Training dataset ready in <30 minutes |
| **Continuous** | Real-time data feeds automatically after setup |
| **Scalable** | Same cleaning pipeline handles both batch + stream |

---

## Comparison: Sequential vs Integrated

### Sequential (Original)
```
Phase 1 Producers (weeks) → Bronze (weeks)
                              ↓
Phase 2 Cleaning → Silver (2-3 weeks)
                    ↓
Phase 3 Features
```
⏱️ Takes 3-4 weeks before ML features

### Integrated (Recommended)  
```
Raw/ Data Load (10 min) → Bronze
                          ↓
Phase 2 Cleaning (10 min) → Silver ✅ READY
                            ↓
+ Phase 1 Producers (continuous) → Bronze → Silver
                                     ↓
Phase 3 Features (after 20 min!) ✅ READY FASTER
```
⏱️ Takes 20 minutes to first version + continuous growth

---

## Monitoring Dashboard

Open **Airflow** (`http://localhost:8080`) to see:

```
DAG: load_raw_data
  Status: SUCCESS (once-off)
  
DAG: silver_processing
  Status: RUNNING (hourly)
  Tasks:
    ✅ clean_traffic (parallel)
    ✅ clean_weather (parallel)
    ✅ match_traffic_weather (after both)
    
DAG: dag_tomtom_stats
  Status: SCHEDULED (weekly)
```

Check **MinIO** (`http://localhost:9001`) to see:
```
lakehouse/
├── bronze/
│   ├── traffic_raw/ (growing)
│   └── weather_raw/ (growing)
└── silver/
    ├── traffic_cleaned/ (clean data)
    ├── weather_cleaned/ (clean data)
    └── traffic_weather_matched/ (joined)
```

---

## Next: Phase 3 (Features)

Once Silver tables are populated (~20 min):

```bash
# Start Phase 3 feature engineering
spark-submit processing/gold/build_training_dataset.py
# Creates gold_traffic_features with 8 feature groups
# Ready for LightGBM model training
```

---

## Summary

✅ **Integrated Approach:**
1. Load raw/ data → Bronze (10 min)
2. Clean → Silver (10 min)
3. Start producers → Continuous feed
4. Phase 3 ready in 20 min + grows with real-time data

**Total code:** ~1,500 lines  
**Total setup time:** ~20 minutes  
**Data volume:** 600K+ records from day 1  
**Status:** ✅ Ready to execute now

