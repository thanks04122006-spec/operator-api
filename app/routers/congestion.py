from fastapi import APIRouter

from app.models.schemas import TodayCongestionResponse
from app.services.aggregation import today_forecast

router = APIRouter(prefix="/api/v1", tags=["congestion"])


@router.get("/congestion/today", response_model=TodayCongestionResponse)
def get_today_congestion():
    return today_forecast()
