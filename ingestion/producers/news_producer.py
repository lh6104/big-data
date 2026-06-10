"""
Main entry point for NewsCrawler ingestion pipeline
Runs RSS fetcher and HTML scraper based on sources.yaml
"""

import asyncio
import logging
import json
import time
from pathlib import Path
import sys

from .rss_fetcher import RSSFetcher
from .html_scraper import HTMLScraper
from .base_producer import BaseProducer

logger = logging.getLogger(__name__)


class NewsKafkaProducer(BaseProducer):
    """Kafka producer for news events."""

    def __init__(self):
        super().__init__(
            topic="events.news",
            dlq_topic="events.news.dlq",
            schema_subject="events-news-value",
        )

    def send_event(self, event: dict) -> bool:
        """Send news event to Kafka."""
        return self.send(
            key=event.get("source_url", "unknown"),
            value=event,
            timestamp_ms=int(time.time() * 1000),
        )


async def run_crawlers():
    """Run all crawlers from sources.yaml"""
    # Load configuration
    config_path = Path(__file__).parent.parent.parent / "sources.yaml"
    if not config_path.exists():
        logger.error(f"sources.yaml not found at {config_path}")
        logger.info(f"Expected at: {config_path}")
        sys.exit(1)

    # Initialize producer
    kafka_producer = NewsKafkaProducer()

    # Initialize crawlers
    rss_fetcher = RSSFetcher(kafka_producer=kafka_producer)
    html_scraper = HTMLScraper(kafka_producer=kafka_producer)

    try:
        # Run crawlers in parallel
        tasks = [
            rss_fetcher.run(),
            html_scraper.run(),
        ]
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Crawlers interrupted by user")
    except Exception as e:
        logger.error(f"Error in crawlers: {e}", exc_info=True)
        sys.exit(1)
    finally:
        kafka_producer.close()
        logger.info(f"Producer stats: {kafka_producer.get_stats()}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    asyncio.run(run_crawlers())
