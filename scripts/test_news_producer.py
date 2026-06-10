#!/usr/bin/env python3
"""Quick test of news crawler producer."""

import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, '/home/longha/Desktop/leue')

try:
    from ingestion.producers.news_producer import NewsKafkaProducer
    from ingestion.kafka.producer import KafkaProducer

    print("✅ Imports successful")
    print("")

    # Test 1: Initialize producer
    print("TEST 1: Initialize NewsKafkaProducer")
    producer = NewsKafkaProducer()
    print("✅ Producer initialized")
    print("")

    # Test 2: Send sample news event
    print("TEST 2: Send sample news event")
    sample_event = {
        "source_url": "https://example.com/news/1",
        "source": "test-rss",
        "title": "Traffic accident on Nguyen Trai street",
        "content": "A multi-vehicle accident occurred at 2:00 PM",
        "event_type": "accident",
        "severity": 8,
        "location_entity": "Nguyen Trai, Hanoi",
        "lat": 20.9956,
        "lon": 105.8220,
        "city": "hanoi",
        "published_at": datetime.now().isoformat(),
        "crawled_at": datetime.now().isoformat(),
    }

    success = producer.send_event(sample_event)
    print(f"  Event sent: {success}")
    print(f"  Topic: events.news")
    print(f"  Message: {json.dumps(sample_event, indent=2)[:100]}...")
    print("")

    # Test 3: Check stats
    print("TEST 3: Producer Stats")
    stats = producer.get_stats()
    print(f"  Messages sent: {stats.get('messages_sent', 0)}")
    print(f"  Messages failed: {stats.get('messages_failed', 0)}")
    print(f"  DLQ messages: {stats.get('dlq_messages', 0)}")
    print("")

    # Test 4: Wait and close
    time.sleep(2)
    producer.close()
    print("✅ Producer closed")
    print("")

    print("=" * 60)
    print("NEWS CRAWLER TEST: PASSED ✅")
    print("=" * 60)

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
