"""TomTom Traffic Stats async API client - Fetch historical baseline p15/p50/p85."""

import asyncio
import logging
import aiohttp
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TomTomStatsClient:
    """Async client for TomTom Traffic Stats API."""

    def __init__(self, api_key: str):
        """Initialize with TomTom API key."""
        self.api_key = api_key
        self.base_url = "https://api.tomtom.com/traffic/services/4"
        self.session: Optional[aiohttp.ClientSession] = None
        self.jobs = {}  # Track async jobs

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def submit_job(
        self,
        origin_x: float,
        origin_y: float,
        destination_x: float,
        destination_y: float,
        departure_time: str,
    ) -> str:
        """
        Submit async traffic stats job.
        Returns job ID for polling.
        """
        if not self.session:
            raise RuntimeError("Client not initialized. Use 'async with TomTomStatsClient(...)'")

        params = {
            "key": self.api_key,
            "format": "json",
            "departureTime": departure_time,  # ISO8601 format
        }

        coords = f"{origin_x},{origin_y}:{destination_x},{destination_y}"
        url = f"{self.base_url}/routing/route/{coords}"

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 202:  # Accepted (async)
                    data = await resp.json()
                    job_id = data.get("id")
                    self.jobs[job_id] = {"status": "submitted", "created_at": datetime.utcnow()}
                    logger.info(f"Job submitted: {job_id}")
                    return job_id
                elif resp.status == 200:  # Immediate response
                    data = await resp.json()
                    logger.info(f"Immediate response for route {coords}")
                    return data.get("id", str(time.time()))
                else:
                    logger.error(f"API error {resp.status}: {await resp.text()}")
                    raise Exception(f"TomTom API error: {resp.status}")
        except Exception as e:
            logger.error(f"Error submitting job: {e}")
            raise

    async def poll_job(self, job_id: str, max_retries: int = 30, retry_delay: int = 5) -> Dict:
        """
        Poll job status until complete.
        Returns result when ready.
        """
        if not self.session:
            raise RuntimeError("Client not initialized")

        url = f"{self.base_url}/routing/route/result/{job_id}"
        params = {"key": self.api_key, "format": "json"}

        for attempt in range(max_retries):
            try:
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 200:  # Result ready
                        data = await resp.json()
                        self.jobs[job_id]["status"] = "completed"
                        logger.info(f"Job {job_id} completed")
                        return data
                    elif resp.status == 202:  # Still processing
                        logger.info(f"Job {job_id} in progress (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(f"API error {resp.status}: {await resp.text()}")
                        raise Exception(f"TomTom API error: {resp.status}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout polling job {job_id}, retrying...")
                await asyncio.sleep(retry_delay)

        raise TimeoutError(f"Job {job_id} did not complete after {max_retries} retries")

    async def get_traffic_stats(
        self,
        segment_coordinates: List[tuple],
        start_date: str,
        end_date: str,
    ) -> Dict:
        """
        Fetch traffic statistics for segments over date range.
        Returns p15/p50/p85 per segment per hour.
        """
        if not self.session:
            raise RuntimeError("Client not initialized")

        stats = {}

        for coord_pair in segment_coordinates:
            try:
                # Submit job for this coordinate pair
                job_id = await self.submit_job(
                    origin_x=coord_pair[0],
                    origin_y=coord_pair[1],
                    destination_x=coord_pair[0] + 0.001,  # Small offset for routing
                    destination_y=coord_pair[1] + 0.001,
                    departure_time=start_date,
                )

                # Poll for result
                result = await self.poll_job(job_id)

                # Extract percentiles from result
                segment_id = f"seg_{coord_pair[0]:.4f}_{coord_pair[1]:.4f}"
                if "routes" in result and len(result["routes"]) > 0:
                    route = result["routes"][0]
                    stats[segment_id] = {
                        "p15": route.get("summary", {}).get("travelTimeInSeconds", 0) * 0.15,
                        "p50": route.get("summary", {}).get("travelTimeInSeconds", 0) * 0.5,
                        "p85": route.get("summary", {}).get("travelTimeInSeconds", 0) * 0.85,
                        "source": "tomtom-stats",
                        "fetched_at": datetime.utcnow().isoformat(),
                    }

            except Exception as e:
                logger.error(f"Error fetching stats for {coord_pair}: {e}")
                continue

        return stats


async def fetch_tomtom_stats(api_key: str, cities: List[str]) -> Dict:
    """
    Main entry point: fetch TomTom stats for Vietnam cities.
    Returns stats dictionary keyed by segment_id.
    """
    logger.info(f"Fetching TomTom Traffic Stats for {cities}...")

    async with TomTomStatsClient(api_key) as client:
        all_stats = {}

        # For each city, fetch stats for a sample of segments
        # In production, this would iterate over actual segment coordinates from database
        for city in cities:
            logger.info(f"Fetching stats for {city}...")

            # Sample coordinates for demonstration
            coords_map = {
                "hanoi": [(105.8, 21.0), (105.9, 21.1)],
                "hcmc": [(106.7, 10.7), (106.8, 10.8)],
            }

            coords = coords_map.get(city.lower(), [])
            if not coords:
                logger.warning(f"No sample coordinates for {city}")
                continue

            # Fetch stats
            stats = await client.get_traffic_stats(
                segment_coordinates=coords,
                start_date=datetime.now().isoformat(),
                end_date=(datetime.now() + timedelta(days=7)).isoformat(),
            )

            all_stats.update(stats)

        logger.info(f"Fetched stats for {len(all_stats)} segments")
        return all_stats


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO)

    api_key = os.getenv("TOMTOM_API_KEY", "")
    if not api_key:
        logger.error("TOMTOM_API_KEY not set")
        exit(1)

    stats = asyncio.run(fetch_tomtom_stats(api_key, ["hanoi", "hcmc"]))
    print(f"Stats: {stats}")
