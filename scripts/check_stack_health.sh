#!/bin/bash

echo "🔍 Checking stack health..."
echo ""

# Check services
services=(
    "kafka:9092"
    "postgres:5432"
    "mongodb:27017"
    "redis:6379"
    "neo4j:7687"
    "minio:9000"
    "schema-registry:8081"
)

for service in "${services[@]}"; do
    host="${service%:*}"
    port="${service#*:}"
    if nc -z "$host" "$port" 2>/dev/null; then
        echo "✅ $service"
    else
        echo "❌ $service"
    fi
done

echo ""
echo "🌐 Web UIs:"
echo "   Kafka Topics: docker exec kafka kafka-topics --list --bootstrap-server localhost:9092"
echo "   MinIO:        http://localhost:9001 (minioadmin:minioadmin)"
echo "   Airflow:      http://localhost:8080 (admin:admin)"
echo "   Neo4j:        http://localhost:7474 (neo4j:password)"
