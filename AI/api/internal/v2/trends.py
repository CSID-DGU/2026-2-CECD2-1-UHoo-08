"""요즘 뜨는 제품. 사용자와 무관한 전체 공통 값이다."""
import logging

from fastapi import APIRouter

from contracts.internal_api import TrendsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/trends")
async def trends(limit: int = 10) -> TrendsResponse:
    # TODO: product_trend_daily 의 최신 날짜에서 상위 N개를 읽는다.
    logger.warning("stub: /trends limit=%s", limit)
    return TrendsResponse(stub=True)
