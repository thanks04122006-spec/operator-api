from datetime import datetime

from fastapi import APIRouter, Query

from app.core.errors import DataNotFoundError, InvalidDateError
from app.models.schemas import StatsResponse
from app.services.aggregation import stats_for_date

router = APIRouter(prefix="/api/v1", tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
def get_stats(date: str = Query(..., description="YYYY-MM-DD")):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise InvalidDateError()

    result = stats_for_date(date)
    if result is None:
        raise DataNotFoundError()
    return result
