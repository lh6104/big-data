"""FastAPI backend for Cognitive Traffic Analytics Platform.

Endpoints:
- GET /traffic/current/{city} — Real-time traffic status (from Redis)
- GET /traffic/predict/{segment_id}?horizon=15 — Speed forecast
- GET /alerts/active — Active traffic alerts
- GET /hotspots — Congestion hotspots from DBSCAN
- GET /predictions/{id}/explain — SHAP explanation
- And 9+ more endpoints...
"""

import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import uvicorn

from api.routers import alerts, explain, hotspots, monitoring, routing, segments, settings, traffic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Cognitive Traffic Analytics API",
    description="Traffic forecasting, alerts, and analytics",
    version="1.0.0",
)

allowed_origins = os.getenv(
    "API_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000",
).split(",")

# CORS middleware for local frontend development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
@app.get("/")
def read_root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Cognitive Traffic Analytics API",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "service": "traffic-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Register routers with prefixes
app.include_router(
    traffic.router,
    prefix="/traffic",
    tags=["traffic"],
    responses={404: {"description": "Not found"}},
)

app.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["alerts"],
)

app.include_router(
    explain.router,
    prefix="/predictions",
    tags=["explainability"],
)

app.include_router(
    hotspots.router,
    prefix="/hotspots",
    tags=["hotspots"],
)

app.include_router(
    segments.router,
    prefix="/segments",
    tags=["segments"],
)

app.include_router(
    monitoring.router,
    prefix="/monitoring",
    tags=["monitoring"],
)

app.include_router(
    settings.router,
    prefix="/settings",
    tags=["settings"],
)

app.include_router(
    routing.router,
    prefix="/routing",
    tags=["routing"],
)


# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all exception handler."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


if __name__ == "__main__":
    # Run with: uvicorn api.main:app --reload --port 8000
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
