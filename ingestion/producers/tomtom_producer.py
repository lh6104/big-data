"""TomTom Flow API producer - Real-time traffic data ingestion."""

import os
import json
import time
import logging
from datetime import datetime
from typing import Optional
import requests
from .base_producer import BaseProducer
from infra.settings import settings

logger = logging.getLogger(__name__)


class TomTomProducer(BaseProducer):
    """Producer for TomTom Flow API data."""

    def __init__(self):
        super().__init__(
            topic="traffic.realtime.tomtom",
            dlq_topic="traffic.realtime.tomtom.dlq",
            schema_subject="traffic-realtime-tomtom-value",
        )
        self.api_key = os.getenv("TOMTOM_API_KEY")
        if not self.api_key:
            raise ValueError("TOMTOM_API_KEY not set in environment")
        self.base_url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        self.poll_interval = int(os.getenv("TOMTOM_POLL_INTERVAL_MINUTES", "5")) * 60

    def fetch_traffic_data(self, bbox: dict) -> Optional[list]:
        """Fetch traffic flow data from TomTom API.

        Args:
            bbox: Bounding box dict with south, north, west, east

        Returns:
            List of flow segments or None on error
        """
        try:
            params = {
                "key": self.api_key,
                "bbox": f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}",
                "details": "true",
            }
            logger.info(f"Fetching TomTom data for bbox: {bbox}")
            response = requests.get(
                self.base_url,
                params=params,
                timeout=settings.HTTP_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            if "flowSegmentData" in data:
                return data["flowSegmentData"]
            else:
                logger.warning(f"No flowSegmentData in response: {data.keys()}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"TomTom API error: {e}")
            return None

    def process_segment(self, segment: dict) -> dict:
        """Process a flow segment into Kafka message format."""
        try:
            coords = segment.get("coordinates", [])
            if coords:
                lat = coords[-1][1]  # Last coordinate (current position)
                lon = coords[-1][0]
            else:
                lat = lon = None

            # Extract speed metrics
            current_speed = segment.get("currentSpeed")
            free_flow_speed = segment.get("freeFlowSpeed")
            jam_factor = segment.get("jamFactor")

            # Calculate congestion ratio
            congestion_ratio = (
                1 - (current_speed / free_flow_speed)
                if current_speed and free_flow_speed and free_flow_speed > 0
                else None
            )

            return {
                "segment_id": segment.get("id"),
                "current_speed": current_speed,
                "free_flow_speed": free_flow_speed,
                "jam_factor": jam_factor,
                "congestion_ratio": congestion_ratio,
                "confidence": segment.get("confidence"),
                "latitude": lat,
                "longitude": lon,
                "functional_road_class": segment.get("functionalRoadClass"),
                "road_closure": segment.get("roadClosure", False),
                "source": "tomtom",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error processing segment {segment.get('id')}: {e}")
            return None

    def run(self, hanoi_bbox: dict = None, hcm_bbox: dict = None, continuous: bool = True):
        """Run producer loop.

        Args:
            hanoi_bbox: Bounding box for Hanoi
            hcm_bbox: Bounding box for HCM
            continuous: Whether to run continuously
        """
        # Default bounding boxes
        if not hanoi_bbox:
            hanoi_bbox = {
                "south": 20.9,
                "north": 21.1,
                "west": 105.7,
                "east": 106.0,
            }
        if not hcm_bbox:
            hcm_bbox = {
                "south": 10.5,
                "north": 10.9,
                "west": 106.5,
                "east": 107.0,
            }

        logger.info("TomTom producer started")

        try:
            while True:
                # Fetch for both cities
                for city_name, bbox in [("Hanoi", hanoi_bbox), ("HCM", hcm_bbox)]:
                    segments = self.fetch_traffic_data(bbox)
                    if segments:
                        for segment in segments:
                            msg = self.process_segment(segment)
                            if msg:
                                segment_id = msg.get("segment_id", "unknown")
                                self.send(
                                    key=segment_id,
                                    value=msg,
                                    timestamp_ms=int(time.time() * 1000),
                                )
                        logger.info(f"Sent {len(segments)} segments from {city_name}")

                if not continuous:
                    break

                logger.info(f"Sleeping for {self.poll_interval} seconds...")
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Producer interrupted by user")
        finally:
            self.close()
            logger.info(f"Producer stats: {self.get_stats()}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    producer = TomTomProducer()
    producer.run(continuous=True)
