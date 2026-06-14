"""Graph reasoning endpoints backed by local demo data or Neo4j later."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.services.local_data import DataUnavailableError, latest_by_segment, traffic_features
from intelligence.risk_scoring import score_segment_risk


router = APIRouter()


@router.get("/propagation/{segment_id}")
def get_congestion_propagation(segment_id: str, depth: int = Query(3, ge=1, le=5)) -> dict[str, Any]:
    """Return a prototype congestion propagation path for a segment."""
    try:
        latest = latest_by_segment(traffic_features())
    except DataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if latest[latest["segment_id"].astype(str) == str(segment_id)].empty:
        raise HTTPException(status_code=404, detail=f"Segment '{segment_id}' was not found in local data")

    candidates = latest.sort_values("jamFactor", ascending=False).head(depth + 1)
    path = []
    for idx, row in enumerate(candidates.itertuples(index=False)):
        risk = score_segment_risk(row)
        path.append(
            {
                "segment_id": str(row.segment_id),
                "distance_m": idx * 500,
                "jam_factor": round(float(row.jamFactor), 2),
                "current_speed": round(float(row.currentSpeed), 2),
                "risk_score": risk.risk_score,
                "risk_level": risk.risk_level,
            }
        )

    propagation_score = round(sum(item["risk_score"] for item in path) / len(path), 3) if path else 0.0
    return {
        "segment_id": segment_id,
        "depth": depth,
        "propagation_score": propagation_score,
        "path": path,
        "source": "local_gold_prototype",
        "updated_at": datetime.utcnow().isoformat(),
    }
