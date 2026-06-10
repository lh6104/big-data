"""Kafka producer for publishing events."""

import json
import logging
from typing import Optional

from confluent_kafka import Producer
from infra.settings import settings

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Produces messages to Kafka topics."""

    def __init__(self, topic: str = "news.raw"):
        self.topic = topic
        self.producer = Producer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        })

    def send(self, event: dict) -> bool:
        """Send event to Kafka topic."""
        try:
            self.producer.produce(
                self.topic,
                value=json.dumps(event).encode("utf-8"),
                callback=self._delivery_report
            )
            self.producer.flush()
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def _delivery_report(self, err, msg):
        """Delivery report callback."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")

    def close(self):
        """Close the producer."""
        self.producer.flush()
