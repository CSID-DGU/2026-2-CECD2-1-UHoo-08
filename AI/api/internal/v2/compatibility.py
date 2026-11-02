"""사려는 제품이 쓰고 있는 제품과 잘 맞는지 확인한다. 화면이 바로 기다리는 호출이다."""
import logging

from fastapi import APIRouter

from contracts.internal_api import CompatibilityCheckRequest, CompatibilityCheckResponse
from contracts.result import CompatibilityLevel

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/compatibility/check")
async def compatibility_check(req: CompatibilityCheckRequest) -> CompatibilityCheckResponse:
    # TODO: 보유 제품과 이 제품의 성분을 표준명으로 맞추고
    #       ingredient_conflict_rules 와 대조해 쌍별 판정을 채운다.
    logger.warning("stub: /compatibility/check user=%s product=%s", req.user_id, req.product_id)
    return CompatibilityCheckResponse(level=CompatibilityLevel.OK, stub=True)
