"""Pipeline and model monitoring endpoints."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class PipelineStatus(BaseModel):
    """Data pipeline health status."""
    component: str
    status: str  # healthy, degraded, unhealthy
    lag_messages: int
    last_update: datetime
    details: dict


class ModelMetrics(BaseModel):
    """Model performance metrics."""
    horizon_minutes: int
    mae_24h: float
    rmse_24h: float
    r2_score: float
    last_retrain: datetime
    next_retrain: datetime


@router.get("/pipeline", response_model=List[PipelineStatus])
def get_pipeline_status():
    """Get real-time pipeline health status.

    Returns:
        List of component statuses (Kafka, Spark, Feature Store, etc.)
    """
    # In production, query Prometheus metrics
    return [
        PipelineStatus(
            component="kafka",
            status="healthy",
            lag_messages=125,
            last_update=datetime.utcnow(),
            details={"lag_p95": 250, "throughput": "15K msg/s"},
        ),
        PipelineStatus(
            component="spark",
            status="healthy",
            lag_messages=0,
            last_update=datetime.utcnow(),
            details={"job_duration_min": 8, "success_rate": 0.99},
        ),
        PipelineStatus(
            component="feature_store",
            status="healthy",
            lag_messages=0,
            last_update=datetime.utcnow(),
            details={"total_records": 500000, "latest_update_mins_ago": 5},
        ),
        PipelineStatus(
            component="api",
            status="healthy",
            lag_messages=0,
            last_update=datetime.utcnow(),
            details={"uptime_pct": 99.98, "p95_latency_ms": 45},
        ),
    ]


@router.get("/model", response_model=Dict)
def get_model_metrics():
    """Get model performance and data quality metrics.

    Returns:
        Model metrics (MAE, RMSE, R²) and DQ tier information
    """
    # In production, query MLflow + DQ tables
    return {
        "models": [
            {
                "horizon_minutes": 15,
                "mae_24h": 5.2,
                "rmse_24h": 7.1,
                "r2_score": 0.88,
                "last_retrain": datetime.utcnow(),
                "next_retrain": datetime.utcnow(),
            },
            {
                "horizon_minutes": 60,
                "mae_24h": 7.8,
                "rmse_24h": 10.3,
                "r2_score": 0.82,
                "last_retrain": datetime.utcnow(),
                "next_retrain": datetime.utcnow(),
            },
        ],
        "data_quality": {
            "tier_gold": 0.92,
            "tier_silver": 0.88,
            "tier_bronze": 0.75,
            "null_rate": 0.02,
            "duplicate_rate": 0.001,
        },
    }
