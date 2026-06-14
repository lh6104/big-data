"""Corridor ranking utilities for cognitive risk summaries."""

from __future__ import annotations

from typing import Any

import pandas as pd

from intelligence.risk_scoring import score_segment_risk


def rank_corridors(rows: pd.DataFrame, corridor_column: str = "district", limit: int = 10) -> list[dict[str, Any]]:
    if rows.empty:
        return []
    column = corridor_column if corridor_column in rows.columns else "city"
    scored = rows.copy()
    scored["_risk_score"] = [score_segment_risk(row).risk_score for _, row in scored.iterrows()]
    grouped = scored.groupby(column, dropna=False).agg(
        risk_score=("_risk_score", "mean"),
        max_jam_factor=("jamFactor", "max"),
        segment_count=("segment_id", "nunique"),
    )
    grouped = grouped.reset_index().sort_values("risk_score", ascending=False).head(limit)
    return [
        {
            "corridor_id": str(row[column]),
            "risk_score": round(float(row["risk_score"]), 3),
            "risk_level": score_segment_risk({"jamFactor": float(row["max_jam_factor"]), "currentSpeed": 1, "freeFlowSpeed": 1}).risk_level,
            "max_jam_factor": round(float(row["max_jam_factor"]), 2),
            "segment_count": int(row["segment_count"]),
        }
        for _, row in grouped.iterrows()
    ]
