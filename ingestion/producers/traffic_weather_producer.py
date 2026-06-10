"""Aligned traffic + weather producer - fetches both in sync."""

import asyncio
import logging
import argparse
from .tomtom_producer import TomTomProducer
from .weather_producer import WeatherProducer

logger = logging.getLogger(__name__)


class AlignedTrafficWeatherProducer:
    """Fetch traffic and weather in aligned time buckets."""

    def __init__(self, bucket_minutes: int = 5):
        self.bucket_minutes = bucket_minutes
        self.traffic_producer = TomTomProducer()
        self.weather_producer = WeatherProducer()

        # Override poll intervals to match bucket
        self.traffic_producer.poll_interval = bucket_minutes * 60
        self.weather_producer.poll_interval = bucket_minutes * 60

    def run_sync(self, continuous: bool = True):
        """Run both producers synchronously in aligned buckets."""
        logger.info(
            f"Aligned producer started with {self.bucket_minutes}-minute buckets"
        )

        hanoi_bbox = {
            "south": 20.9,
            "north": 21.1,
            "west": 105.7,
            "east": 106.0,
        }
        hcm_bbox = {
            "south": 10.5,
            "north": 10.9,
            "west": 106.5,
            "east": 107.0,
        }

        try:
            import time

            while True:
                start_time = time.time()
                logger.info("Starting synchronized polling cycle...")

                # Fetch traffic for both cities
                for city_name, bbox in [("Hanoi", hanoi_bbox), ("HCM", hcm_bbox)]:
                    segments = self.traffic_producer.fetch_traffic_data(bbox)
                    if segments:
                        for segment in segments:
                            msg = self.traffic_producer.process_segment(segment)
                            if msg:
                                self.traffic_producer.send(
                                    key=msg.get("segment_id", "unknown"),
                                    value=msg,
                                    timestamp_ms=int(time.time() * 1000),
                                )
                        logger.info(f"Sent {len(segments)} traffic segments from {city_name}")

                # Fetch weather for both cities
                for loc in self.weather_producer.locations:
                    data = self.weather_producer.fetch_weather(
                        loc["lat"], loc["lon"], loc["city"]
                    )
                    if data:
                        msg = self.weather_producer.process_weather(data, loc["city"])
                        if msg:
                            self.weather_producer.send(
                                key=loc["city"],
                                value=msg,
                                timestamp_ms=int(time.time() * 1000),
                            )
                            logger.info(f"Sent weather data for {loc['city']}")

                if not continuous:
                    break

                # Sleep until next bucket
                elapsed = time.time() - start_time
                sleep_time = max(0, self.bucket_minutes * 60 - elapsed)
                logger.info(
                    f"Polling cycle completed in {elapsed:.1f}s. "
                    f"Sleeping {sleep_time:.1f}s until next cycle..."
                )
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Producer interrupted by user")
        finally:
            self.traffic_producer.close()
            self.weather_producer.close()
            logger.info(
                f"Traffic stats: {self.traffic_producer.get_stats()}, "
                f"Weather stats: {self.weather_producer.get_stats()}"
            )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Aligned traffic + weather producer"
    )
    parser.add_argument(
        "--bucket-minutes",
        type=int,
        default=5,
        help="Polling bucket size in minutes (default: 5)",
    )
    args = parser.parse_args()

    producer = AlignedTrafficWeatherProducer(bucket_minutes=args.bucket_minutes)
    producer.run_sync(continuous=True)
