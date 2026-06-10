"""Base producer with retry logic and error handling."""

import json
import logging
import time
from typing import Optional, Callable
from confluent_kafka import Producer
from confluent_kafka.error import KafkaError
from tenacity import retry, stop_after_attempt, wait_exponential
from infra.settings import settings

logger = logging.getLogger(__name__)


class BaseProducer:
    """Base Kafka producer with retry and dead letter queue support."""

    def __init__(
        self,
        topic: str,
        dlq_topic: Optional[str] = None,
        schema_subject: Optional[str] = None,
    ):
        self.topic = topic
        self.dlq_topic = dlq_topic or f"{topic}.dlq"
        self.schema_subject = schema_subject
        self.producer = Producer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": f"{topic}-producer",
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 100,
        })
        self.stats = {
            "sent": 0,
            "failed": 0,
            "dlq": 0,
        }

    def _delivery_report(self, err, msg):
        """Kafka delivery callback."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
            self.stats["failed"] += 1
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")
            self.stats["sent"] += 1

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def send(self, key: str, value: dict, timestamp_ms: Optional[int] = None) -> bool:
        """Send message to Kafka topic with retry."""
        try:
            msg_bytes = json.dumps(value).encode("utf-8")
            self.producer.produce(
                self.topic,
                key=key.encode("utf-8") if key else None,
                value=msg_bytes,
                timestamp=timestamp_ms,
                callback=self._delivery_report,
            )
            self.producer.poll(0)
            return True
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._send_to_dlq(key, value, str(e))
            return False

    def _send_to_dlq(self, key: str, value: dict, error: str) -> None:
        """Send failed message to DLQ."""
        try:
            dlq_msg = {
                "original_topic": self.topic,
                "original_key": key,
                "original_value": value,
                "error": error,
                "timestamp": int(time.time() * 1000),
            }
            self.producer.produce(
                self.dlq_topic,
                key=key.encode("utf-8") if key else None,
                value=json.dumps(dlq_msg).encode("utf-8"),
            )
            self.stats["dlq"] += 1
            logger.warning(f"Sent message to DLQ: {self.dlq_topic}")
        except Exception as dlq_err:
            logger.error(f"Failed to send to DLQ: {dlq_err}")

    def flush(self, timeout_ms: int = 5000) -> None:
        """Flush pending messages."""
        self.producer.flush(timeout_ms // 1000)

    def close(self) -> None:
        """Close producer."""
        self.flush()
        self.producer.close()
        logger.info(f"Producer closed. Stats: {self.stats}")

    def get_stats(self) -> dict:
        """Get producer statistics."""
        return self.stats.copy()
