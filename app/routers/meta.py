from fastapi import APIRouter

from app.core.config import AVAILABLE_HOURS, LEVELS, LIBRARY_NAME, OPERATING_HOURS
from app.models.schemas import MetaResponse

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/meta", response_model=MetaResponse)
def get_meta():
    return {
        "library_name": LIBRARY_NAME,
        "available_hours": AVAILABLE_HOURS,
        "operating_hours": OPERATING_HOURS,
        "levels": LEVELS,
    }
