#!/bin/bash

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                    PHASE 1 PIPELINE TEST - PRE-FLIGHT CHECK                 ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"

# Check if docker is running
echo ""
echo "Step 1: Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi
echo "✓ Docker installed"

# Check if docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon not running. Please start Docker."
    exit 1
fi
echo "✓ Docker daemon running"

# Check if docker-compose works
echo ""
echo "Step 2: Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found."
    exit 1
fi
echo "✓ Docker Compose installed"

# Check project structure
echo ""
echo "Step 3: Checking project structure..."
cd /home/longha/Desktop/leue

required_files=(
    "docker-compose.yml"
    "Makefile"
    "requirements.txt"
    ".env.example"
    "ingestion/producers/tomtom_producer.py"
    "ingestion/producers/weather_producer.py"
    "ingestion/producers/news_producer.py"
    "processing/bronze/kafka_to_bronze.py"
)

missing_files=0
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "❌ $file missing"
        missing_files=$((missing_files + 1))
    fi
done

if [ $missing_files -gt 0 ]; then
    echo "❌ Missing $missing_files required files"
    exit 1
fi

# Check Python dependencies
echo ""
echo "Step 4: Checking Python environment..."
python3 -c "import kafka; print('✓ kafka-python installed')" 2>/dev/null || echo "⚠ kafka-python not installed"
python3 -c "import pyspark; print('✓ pyspark installed')" 2>/dev/null || echo "⚠ pyspark not installed"
python3 -c "import pymongo; print('✓ pymongo installed')" 2>/dev/null || echo "⚠ pymongo not installed"
python3 -c "import redis; print('✓ redis installed')" 2>/dev/null || echo "⚠ redis not installed"

# Check if services are running
echo ""
echo "Step 5: Checking if services are running..."
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "kafka|postgres|mongo|redis" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Some services are running"
    echo ""
    echo "Current running services:"
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "kafka|postgres|mongo|redis|spark|minio|neo4j|zookeeper"
else
    echo "⚠ No Phase 1 services currently running"
    echo ""
    echo "To start the complete stack, run:"
    echo "  $ make up"
    echo "  $ make create-topics"
    echo ""
    exit 0
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                        PRE-FLIGHT CHECK PASSED ✓                            ║"
echo "║                                                                              ║"
echo "║  Next steps to test the pipeline:                                           ║"
echo "║                                                                              ║"
echo "║  1. In Terminal 1: Run TomTom producer                                       ║"
echo "║     $ python3 ingestion/producers/tomtom_producer.py                         ║"
echo "║                                                                              ║"
echo "║  2. In Terminal 2: Run Weather producer                                      ║"
echo "║     $ python3 ingestion/producers/weather_producer.py                        ║"
echo "║                                                                              ║"
echo "║  3. In Terminal 3: Run Spark streaming job                                   ║"
echo "║     $ spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \\"
echo "║         processing/bronze/kafka_to_bronze.py kafka:9092 events.news s3a://lakehouse"
echo "║                                                                              ║"
echo "║  4. Monitor with: make health                                                ║"
echo "║                                                                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
