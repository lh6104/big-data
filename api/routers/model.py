"""Model readiness endpoints."""

from fastapi import APIRouter, Query

from api.services.model_inference import model_status


router = APIRouter()


@router.get("/status")
def get_model_status(load_models: bool = Query(False, description="Attempt to load model artifacts")):
    """Get model artifact readiness and feature-schema status."""
    return model_status(load_models=load_models)
