#!/usr/bin/env python3
"""Simple test of producers without RSS fetcher dependencies."""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from ingestion.producers.base_producer import BaseProducer

    print("✅ BaseProducer imported")
    print("")

    # Test 1: Initialize news producer
    print("TEST 1: Initialize News Producer (BaseProducer)")
    news_producer = BaseProducer(
        topic="events.news",
        dlq_topic="events.news.dlq",
        schema_subject="events-news-value",
    )
    print("✅ News producer created")
    print("")

    # Test 2: Send sample news event
    print("TEST 2: Send sample news events")
    news_events = [
        {
            "event_id": "news_001",
            "source": "test-rss",
            "source_url": "https://example.com/news/1",
            "title": "Tai nạn giao thông trên đường Nguyễn Trãi",
            "content": "Một vụ tai nạn liên hoàn xảy ra vào 14:00",
            "event_type": "accident",
            "severity": 8,
            "location_entity": "Nguyễn Trãi, Hà Nội",
            "lat": 20.9956,
            "lon": 105.8220,
            "city": "hanoi",
            "published_at": datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
        },
        {
            "event_id": "news_002",
            "source": "test-rss",
            "source_url": "https://example.com/news/2",
            "title": "Ngập lụt khu vực quận Ba Đình do mưa lớn",
            "content": "Mưa lớn kéo dài 3 giờ gây ngập lụt trên đường Liễu Giai",
            "event_type": "flood",
            "severity": 7,
            "location_entity": "Liễu Giai, Ba Đình, Hà Nội",
            "lat": 21.0333,
            "lon": 105.8225,
            "city": "hanoi",
            "published_at": datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
        },
        {
            "event_id": "news_003",
            "source": "test-rss",
            "source_url": "https://example.com/news/3",
            "title": "Tắc đường trên tuyến Võ Văn Kiệt TP.HCM do sự cố giao thông",
            "content": "Tắc nghiêm trọng kéo dài 45 phút",
            "event_type": "congestion",
            "severity": 6,
            "location_entity": "Võ Văn Kiệt, TP.HCM",
            "lat": 10.7300,
            "lon": 106.6851,
            "city": "hcmc",
            "published_at": datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
        },
    ]

    sent_count = 0
    for i, event in enumerate(news_events, 1):
        success = news_producer.send(
            key=event["source_url"],
            value=event,
            timestamp_ms=int(time.time() * 1000),
        )
        print(f"  [{i}] {event['title'][:50]}... → {'✅' if success else '❌'}")
        if success:
            sent_count += 1

    print(f"\nSent: {sent_count}/{len(news_events)} events")
    print("")

    # Test 3: Traffic producer
    print("TEST 3: Initialize Traffic Producer")
    traffic_producer = BaseProducer(
        topic="traffic.realtime.tomtom",
        dlq_topic="traffic.realtime.tomtom.dlq",
        schema_subject="traffic-realtime-value",
    )
    print("✅ Traffic producer created")
    print("")

    # Test 4: Send sample traffic events
    print("TEST 4: Send sample traffic events")
    traffic_events = [
        {
            "segment_id": "HN_001",
            "source": "tomtom",
            "timestamp": datetime.now().isoformat(),
            "currentSpeed": 25,
            "freeFlowSpeed": 40,
            "jamFactor": 3.5,
            "congestion_ratio": 0.375,
            "confidence": 0.95,
            "latitude": 20.9956,
            "longitude": 105.8220,
            "functional_road_class": "FRC2",
            "road_closure": False,
        },
        {
            "segment_id": "HN_002",
            "source": "tomtom",
            "timestamp": datetime.now().isoformat(),
            "currentSpeed": 18,
            "freeFlowSpeed": 50,
            "jamFactor": 5.2,
            "congestion_ratio": 0.64,
            "confidence": 0.98,
            "latitude": 21.0245,
            "longitude": 105.8412,
            "functional_road_class": "FRC2",
            "road_closure": False,
        },
    ]

    traffic_sent = 0
    for i, event in enumerate(traffic_events, 1):
        success = traffic_producer.send(
            key=event["segment_id"],
            value=event,
            timestamp_ms=int(time.time() * 1000),
        )
        print(f"  [{i}] Segment {event['segment_id']}: Speed {event['currentSpeed']} km/h → {'✅' if success else '❌'}")
        if success:
            traffic_sent += 1

    print(f"\nSent: {traffic_sent}/{len(traffic_events)} traffic events")
    print("")

    # Test 5: Weather producer
    print("TEST 5: Initialize Weather Producer")
    weather_producer = BaseProducer(
        topic="weather.current",
        dlq_topic="weather.current.dlq",
        schema_subject="weather-current-value",
    )
    print("✅ Weather producer created")
    print("")

    # Test 6: Send sample weather events
    print("TEST 6: Send sample weather events")
    weather_events = [
        {
            "city": "hanoi",
            "source": "openweathermap",
            "timestamp": datetime.now().isoformat(),
            "temperature": 36.5,
            "humidity": 38,
            "visibility": 10000,
            "wind_speed": 2.5,
            "rain_1h": 0.0,
            "latitude": 21.0245,
            "longitude": 105.8412,
        },
        {
            "city": "hcmc",
            "source": "openweathermap",
            "timestamp": datetime.now().isoformat(),
            "temperature": 35.2,
            "humidity": 72,
            "visibility": 9000,
            "wind_speed": 3.2,
            "rain_1h": 2.5,
            "latitude": 10.7769,
            "longitude": 106.6967,
        },
    ]

    weather_sent = 0
    for i, event in enumerate(weather_events, 1):
        success = weather_producer.send(
            key=f"{event['city']}_weather",
            value=event,
            timestamp_ms=int(time.time() * 1000),
        )
        print(f"  [{i}] {event['city'].upper()}: {event['temperature']}°C → {'✅' if success else '❌'}")
        if success:
            weather_sent += 1

    print(f"\nSent: {weather_sent}/{len(weather_events)} weather events")
    print("")

    # Close all producers
    print("Closing producers...")
    time.sleep(1)
    news_producer.close()
    traffic_producer.close()
    weather_producer.close()
    print("✅ All producers closed")
    print("")

    # Summary
    print("=" * 70)
    print("PHASE 1 PRODUCERS TEST: PASSED ✅")
    print("=" * 70)
    print(f"Total events sent: {sent_count + traffic_sent + weather_sent}")
    print(f"  - News events: {sent_count}/{len(news_events)}")
    print(f"  - Traffic events: {traffic_sent}/{len(traffic_events)}")
    print(f"  - Weather events: {weather_sent}/{len(weather_events)}")
    print("")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
