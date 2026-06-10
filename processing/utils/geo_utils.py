"""Geospatial utility functions."""

from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Hanoi bounding box
HANOI_BBOX = {
    "south": 20.9,
    "north": 21.1,
    "west": 105.7,
    "east": 106.0,
}

# HCM bounding box
HCMC_BBOX = {
    "south": 10.5,
    "north": 10.9,
    "west": 106.5,
    "east": 107.0,
}


def is_valid_coordinate(lat: float, lon: float, bbox: dict = None) -> bool:
    """Check if coordinate is within valid bounds."""
    if lat is None or lon is None:
        return False

    if bbox is None:
        # Check both cities
        hanoi_valid = (
            HANOI_BBOX["south"] <= lat <= HANOI_BBOX["north"]
            and HANOI_BBOX["west"] <= lon <= HANOI_BBOX["east"]
        )
        hcmc_valid = (
            HCMC_BBOX["south"] <= lat <= HCMC_BBOX["north"]
            and HCMC_BBOX["west"] <= lon <= HCMC_BBOX["east"]
        )
        return hanoi_valid or hcmc_valid

    return (
        bbox["south"] <= lat <= bbox["north"]
        and bbox["west"] <= lon <= bbox["east"]
    )


def detect_city(lat: float, lon: float) -> Optional[str]:
    """Detect city from coordinates."""
    if is_valid_coordinate(lat, lon, HANOI_BBOX):
        return "Hanoi"
    elif is_valid_coordinate(lat, lon, HCMC_BBOX):
        return "HCMC"
    return None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two coordinates in kilometers."""
    from math import radians, cos, sin, asin, sqrt

    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r
