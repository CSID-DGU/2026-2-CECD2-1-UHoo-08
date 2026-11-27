"""사려는 제품이 쓰고 있는 제품과 잘 맞는지 확인한다. 화면이 바로 기다리는 호출이다.

판정은 추천의 PreFilter 와 같다(rules/compatibility.check_compatibility). 상품 상세에서
"보유 제품과 함께 쓰지 않는 게 좋아요"가 뜨는 제품이 추천에서는 멀쩡히 나오는 일이 없게
같은 함수를 쓴다.

성분 정보가 없는 상품은 판정할 수 없다. OK 로 답하면 "괜찮다"로 읽히므로 stub=True 로
판정하지 않았다고 알린다. DB 에 없는 상품은 404 다.
"""
import logging
import uuid

from fastapi import APIRouter, HTTPException

from contracts.internal_api import (
    CompatibilityCheckRequest,
    CompatibilityCheckResponse,
    CompatibilityPairDetail,
)
from contracts.result import CompatibilityLevel

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/compatibility/check")
async def compatibility_check(req: CompatibilityCheckRequest) -> CompatibilityCheckResponse:
    # 키와 DB 가 있어야 하는 모듈이라 함수 안에서 가져온다(패키지 규칙)
    from graph.nodes.inventory import inventory
    from rules.compatibility import check_compatibility, strongest
    from services.ingredient_store import load_product_ingredients, load_rules

    # 상품 id 는 uuid 다. 형식이 틀린 id 를 DB 에 보내면 조회 자체가 실패해 500 이 된다
    try:
        uuid.UUID(req.product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")

    성분 = await load_product_ingredients([req.product_id])
    if req.product_id not in 성분:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    if not 성분[req.product_id]:
        logger.info("compatibility/check: 성분 정보가 없는 상품 %s", req.product_id)
        return CompatibilityCheckResponse(level=CompatibilityLevel.OK, stub=True)

    보유 = (await inventory({"user_id": req.user_id}))["inventory"]
    쌍들 = check_compatibility(
        보유, {"product_id": req.product_id, "ingredients": 성분[req.product_id]}, await load_rules(),
    )
    return CompatibilityCheckResponse(
        level=CompatibilityLevel(strongest([p["level"] for p in 쌍들])),
        pairs=[CompatibilityPairDetail(**p) for p in 쌍들],
    )
