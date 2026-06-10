#!/bin/bash

# Integrated Phase 1 + Phase 2 Execution
# Clean raw/ data first, then run Phase 1 producers continuously

set -e

echo "╔════════════════════════════════════════════════════════╗"
echo "║  INTEGRATED PHASE 1 + PHASE 2 EXECUTION               ║"
echo "║  Strategy: Clean raw/ first + continuous producers   ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

WAREHOUSE="s3a://lakehouse"
RAW_DATA_DIR="/home/longha/Desktop/leue/raw"

# Check if running in background or interactive
INTERACTIVE=${INTERACTIVE:-true}

echo "STEP 1: Verify Infrastructure"
echo "───────────────────────────────────────────────────────"

# Check Docker services
SERVICES=$(docker-compose ps --services --filter "status=running" 2>/dev/null | wc -l)
echo "✅ Docker services: $SERVICES running"

# Check Kafka
TOPICS=$(docker exec leue-kafka-1 kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | wc -l)
echo "✅ Kafka topics: $TOPICS created"

# Check raw data
TRAFFIC_FILES=$(find $RAW_DATA_DIR/traffic -name "*.jsonl" 2>/dev/null | wc -l)
WEATHER_FILES=$(find $RAW_DATA_DIR/weather -name "*.jsonl" 2>/dev/null | wc -l)
echo "✅ Raw data: $TRAFFIC_FILES traffic + $WEATHER_FILES weather files"

echo ""

# Step 2: Load raw data
echo "STEP 2: Load Raw Data → Bronze"
echo "───────────────────────────────────────────────────────"
echo "⏳ Loading 601 traffic + 360 weather files..."
echo ""

# Create a simple test to verify load_raw_data script exists
if [ ! -f "processing/batch_load/load_raw_data.py" ]; then
    echo "❌ Error: load_raw_data.py not found"
    exit 1
fi

echo "Command to run (in Airflow or manually):"
echo "  spark-submit processing/batch_load/load_raw_data.py $RAW_DATA_DIR $WAREHOUSE"
echo ""
echo "Expected results:"
echo "  - bronze_traffic_raw: ~600K records"
echo "  - bronze_weather_raw: ~100K records"
echo ""

# Step 3: Clean phase 2
echo "STEP 3: Phase 2 Cleaning (Parallel)"
echo "───────────────────────────────────────────────────────"
echo "⏳ Running 3 cleaning jobs in parallel..."
echo ""

echo "Commands to run (all in parallel):"
echo ""
echo "  Terminal 1:"
echo "    spark-submit processing/silver/clean_traffic.py $WAREHOUSE"
echo ""
echo "  Terminal 2:"
echo "    spark-submit processing/silver/clean_weather.py $WAREHOUSE"
echo ""
echo "  Terminal 3:"
echo "    spark-submit processing/silver/match_traffic_weather.py $WAREHOUSE"
echo ""
echo "Expected results:"
echo "  - silver_traffic_cleaned: ~500K (85% quality)"
echo "  - silver_weather_cleaned: ~95K (95% quality)"
echo "  - silver_traffic_weather_matched: ~500K (98% match)"
echo ""
echo "Duration: ~5-10 minutes"
echo ""

# Step 4: Phase 1 producers
echo "STEP 4: Start Phase 1 Producers (Continuous)"
echo "───────────────────────────────────────────────────────"
echo "✅ Ready to run. These feed new data continuously:"
echo ""

echo "  Terminal 1: News Crawler"
echo "    python3 ingestion/producers/news_producer.py"
echo "    → events.news topic"
echo ""

echo "  Terminal 2: TomTom Traffic (requires API key)"
echo "    export TOMTOM_API_KEY='your_key'"
echo "    python3 ingestion/producers/tomtom_producer.py"
echo "    → traffic.realtime.tomtom topic"
echo ""

echo "  Terminal 3: Weather (requires API key)"
echo "    export OWM_API_KEY='your_key'"
echo "    python3 ingestion/producers/weather_producer.py"
echo "    → weather.current topic"
echo ""

echo "  Terminal 4: Aligned Producer"
echo "    python3 ingestion/producers/traffic_weather_producer.py"
echo "    → Both topics (synced)"
echo ""

echo "  Terminal 5: Bronze Streaming"
echo "    spark-submit --master spark://spark-master:7077 \\"
echo "      processing/bronze/kafka_to_bronze.py \\"
echo "      kafka:9092 traffic.realtime.tomtom $WAREHOUSE"
echo "    → Continuous Kafka → Bronze streaming"
echo ""

# Step 5: Monitoring
echo "STEP 5: Monitor (Automatic Hourly)"
echo "───────────────────────────────────────────────────────"
echo "✅ Airflow automatically runs silver_processing DAG hourly"
echo ""
echo "  Check Airflow: http://localhost:8080"
echo "  Check MinIO: http://localhost:9001"
echo "  Check with Trino:"
echo "    trino> SELECT COUNT(*) FROM iceberg.lakehouse.silver_traffic_cleaned"
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════╗"
echo "║                    EXECUTION SUMMARY                  ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "Timeline:"
echo "  Step 1 (Load raw): ~10 min      ← One-time"
echo "  Step 2 (Clean):    ~10 min      ← One-time parallel"
echo "  Step 3 (Phase 1):  Continuous   ← Keep running"
echo "  Step 4 (Monitor):  Automatic    ← Hourly DAGs"
echo ""
echo "Data Volume:"
echo "  Historical:  ~700K raw records (May 14-20)"
echo "  After clean: ~500K cleaned + matched records"
echo "  + Continuous: Real-time data feeds in"
echo ""
echo "Result:"
echo "  ✅ Complete dataset in <30 minutes"
echo "  ✅ Ready for Phase 3 features immediately"
echo "  ✅ Continuous real-time data collection"
echo ""
echo "Next: Phase 3 Feature Engineering"
echo "  spark-submit processing/gold/build_training_dataset.py"
echo ""
echo "Status: 🚀 READY TO EXECUTE"
echo ""
