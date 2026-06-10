"""OpenWeatherMap producer - Real-time weather data ingestion."""

import os
import json
import time
import logging
from datetime import datetime
from typing import Optional, List
import requests
from .base_producer import BaseProducer
from infra.settings import settings

logger = logging.getLogger(__name__)


class WeatherProducer(BaseProducer):
    """Producer for OpenWeatherMap data."""

    def __init__(self):
        super().__init__(
            topic="weather.current",
            dlq_topic="weather.current.dlq",
            schema_subject="weather-current-value",
        )
        self.api_key = os.getenv("OWM_API_KEY")
        if not self.api_key:
            raise ValueError("OWM_API_KEY not set in environment")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        self.poll_interval = int(os.getenv("WEATHER_POLL_INTERVAL_MINUTES", "15")) * 60

        # Weather monitoring locations (Hanoi + HCM districts)
        self.locations = [
            {"city": "Hanoi", "lat": 21.0285, "lon": 105.8542},
            {"city": "HCMC", "lat": 10.7769, "lon": 106.7009},
        ]

    def fetch_weather(self, lat: float, lon: float, city: str) -> Optional[dict]:
        """Fetch weather data from OpenWeatherMap API."""
        try:
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric",
            }
            logger.info(f"Fetching weather for {city} ({lat}, {lon})")
            response = requests.get(
                self.base_url,
                params=params,
                timeout=settings.HTTP_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"OWM API error for {city}: {e}")
            return None

    def process_weather(self, data: dict, city: str) -> dict:
        """Process weather data into Kafka message format."""
        try:
            weather_data = data.get("main", {})
            wind_data = data.get("wind", {})
            rain_data = data.get("rain", {})
            clouds_data = data.get("clouds", {})

            return {
                "city": city,
                "latitude": data.get("coord", {}).get("lat"),
                "longitude": data.get("coord", {}).get("lon"),
                "temperature": weather_data.get("temp"),
                "feels_like": weather_data.get("feels_like"),
                "humidity": weather_data.get("humidity"),
                "pressure": weather_data.get("pressure"),
                "visibility": data.get("visibility"),
                "wind_speed": wind_data.get("speed"),
                "wind_degree": wind_data.get("deg"),
                "rain_1h": rain_data.get("1h", 0),
                "rain_3h": rain_data.get("3h", 0),
                "cloudiness": clouds_data.get("all"),
                "description": data.get("weather", [{}])[0].get("description"),
                "weather_main": data.get("weather", [{}])[0].get("main"),
                "source": "openweathermap",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error processing weather for {city}: {e}")
            return None

    def run(self, continuous: bool = True):
        """Run producer loop."""
        logger.info("Weather producer started")

        try:
            while True:
                for loc in self.locations:
                    data = self.fetch_weather(loc["lat"], loc["lon"], loc["city"])
                    if data:
                        msg = self.process_weather(data, loc["city"])
                        if msg:
                            self.send(
                                key=loc["city"],
                                value=msg,
                                timestamp_ms=int(time.time() * 1000),
                            )
                            logger.info(f"Sent weather data for {loc['city']}")

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

    producer = WeatherProducer()
    producer.run(continuous=True)
