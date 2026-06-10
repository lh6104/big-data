"""Application settings endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class AppSettings(BaseModel):
    """Application configuration."""
    selected_city: str
    city_toggles: Dict[str, bool]
    alert_threshold_critical: float
    alert_threshold_high: float
    refresh_interval_traffic_s: int
    refresh_interval_alerts_s: int
    map_zoom_level: int


@router.get("", response_model=AppSettings)
def get_settings():
    """Get current application settings.

    Returns:
        Current settings state
    """
    # In production, load from Redis or persistent storage
    return AppSettings(
        selected_city="hanoi",
        city_toggles={"hanoi": True, "hcmc": True},
        alert_threshold_critical=0.5,
        alert_threshold_high=0.7,
        refresh_interval_traffic_s=60,
        refresh_interval_alerts_s=30,
        map_zoom_level=13,
    )


@router.put("", response_model=AppSettings)
def update_settings(settings: AppSettings):
    """Update application settings.

    Args:
        settings: New settings

    Returns:
        Updated settings
    """
    # In production, save to Redis with TTL
    logger.info(f"Settings updated: {settings}")

    return settings
