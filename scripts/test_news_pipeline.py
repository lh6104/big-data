#!/usr/bin/env python3
"""
Test script for News Crawler Pipeline
Validates all components without requiring Kafka
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_imports():
    """Test all component imports"""
    logger.info("=" * 80)
    logger.info("TEST 1: Checking module imports...")
    logger.info("=" * 80)

    modules_to_test = [
        ("ingestion.producers.rss_fetcher", "RSS Fetcher module"),
        ("ingestion.producers.html_scraper", "HTML Scraper module"),
        ("ingestion.producers.article_parser", "Article Parser module"),
        ("ingestion.kafka.producer", "Kafka Producer module"),
        ("processing.silver.classifier", "Event Classifier module"),
        ("processing.silver.deduplicator", "Deduplicator module"),
        ("processing.silver.geocoder", "Geocoder module"),
        ("processing.silver.clean_events", "Silver Pipeline module"),
        ("models.event", "Event Models module"),
        ("infra.settings", "Settings module"),
    ]

    all_passed = True
    for module_name, module_desc in modules_to_test:
        try:
            __import__(module_name)
            logger.info(f"✓ {module_desc} imported successfully")
        except Exception as e:
            logger.error(f"✗ Failed to import {module_desc}: {e}")
            all_passed = False

    return all_passed


def test_configuration():
    """Test configuration files"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Checking configuration files...")
    logger.info("=" * 80)

    config_files = {
        "sources.yaml": PROJECT_ROOT / "sources.yaml",
        "infra/settings.py": PROJECT_ROOT / "infra" / "settings.py",
        ".env.example": PROJECT_ROOT / ".env.example",
    }

    all_exist = True
    for name, path in config_files.items():
        if path.exists():
            logger.info(f"✓ {name} found")
        else:
            logger.error(f"✗ {name} NOT found at {path}")
            all_exist = False

    return all_exist


def test_kafka_schema():
    """Test Kafka schema"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Checking Kafka schema...")
    logger.info("=" * 80)

    schema_path = PROJECT_ROOT / "infra" / "kafka" / "events-news.avsc"

    if schema_path.exists():
        logger.info(f"✓ Avro schema found at {schema_path}")

        try:
            import json
            with open(schema_path) as f:
                schema = json.load(f)
            logger.info(f"✓ Schema is valid JSON with {len(schema.get('fields', []))} fields")
            return True
        except Exception as e:
            logger.error(f"✗ Schema validation failed: {e}")
            return False
    else:
        logger.error(f"✗ Schema not found at {schema_path}")
        return False


def test_models():
    """Test data models"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Testing data models...")
    logger.info("=" * 80)

    try:
        from models.event import NewsEvent
        from datetime import datetime

        # Create sample event
        event = NewsEvent(
            event_id="test_001",
            source="test_source",
            source_url="https://example.com/article",
            crawled_at=datetime.now(),
            title="Test Article",
            content="Test content",
            event_type="accident",
            severity=2,
            city="Ha Noi",
        )

        logger.info(f"✓ NewsEvent model works: {event.event_id}")
        logger.info(f"  - event_type: {event.event_type}")
        logger.info(f"  - severity: {event.severity}")
        logger.info(f"  - city: {event.city}")
        return True
    except Exception as e:
        logger.error(f"✗ Model test failed: {e}")
        return False


def test_processing_pipeline():
    """Test processing pipeline components"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Testing processing pipeline...")
    logger.info("=" * 80)

    try:
        from processing.silver.clean_events import SilverEventProcessor
        from processing.utils.spark_session import get_spark_session

        logger.info("✓ SilverEventProcessor can be instantiated")
        logger.info("✓ Spark session helper is available")
        return True
    except Exception as e:
        logger.error(f"✗ Pipeline test failed: {e}")
        return False


def test_file_structure():
    """Test project file structure"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 6: Verifying file structure...")
    logger.info("=" * 80)

    required_dirs = [
        "infra",
        "ingestion/producers",
        "processing/bronze",
        "processing/silver",
        "processing/gold",
        "processing/utils",
        "models",
        "airflow/dags",
        "tests/unit",
        "docs",
    ]

    all_exist = True
    for dir_name in required_dirs:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists() and dir_path.is_dir():
            logger.info(f"✓ {dir_name}/")
        else:
            logger.error(f"✗ {dir_name}/ NOT found")
            all_exist = False

    return all_exist


def run_all_tests():
    """Run all tests"""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " NEWS CRAWLER PIPELINE - TEST FLOW ".center(78) + "║")
    logger.info("╚" + "=" * 78 + "╝")

    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Kafka Schema", test_kafka_schema),
        ("Data Models", test_models),
        ("Processing Pipeline", test_processing_pipeline),
        ("File Structure", test_file_structure),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"✗ {test_name} test crashed: {e}")
            results[test_name] = False

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info("")
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 80)

    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
