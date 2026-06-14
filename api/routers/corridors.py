"""Corridor risk ranking endpoints."""

from fastapi import APIRouter, HTTPException, Query

from api.services.local_data import DataUnavailableError, latest_by_segment, normalize_city, traffic_features
from intelligence.corridor_ranker import rank_corridors


router = APIRouter()


@router.get("/risk")
def get_corridor_risk(city: str = Query("hanoi"), limit: int = Query(10, ge=1, le=50)):
    """Rank corridors/districts by cognitive segment risk."""
    try:
        latest = latest_by_segment(traffic_features(), normalize_city(city))
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "city": normalize_city(city),
        "ranked_corridors": rank_corridors(latest, limit=limit),
        "source": "local_gold_prototype",
    }
