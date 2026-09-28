"""채워진 QuerySpec 을 보고 어느 경로로 갈지 정한다.

READS:  query_spec, parent_job_id, clarify_count
WRITES: scenario, clarify_question

LLM 을 부르지 않는다. 같은 값이면 언제나 같은 경로로 가야 하고, 그 보장이
이 단계의 존재 이유다. 흔들릴 수 있는 자리는 Normalize 하나로 좁혀 둔다.

되물을지도 여기서 정한다. 무엇이 비었는지는 QuerySpec 이 알고 있으므로
질문도 규칙으로 만든다. 문장을 LLM 에 맡기면 같은 상황에서 매번 다른 것을
묻게 되고, 골든셋으로 잴 수 없다.
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from contracts.query_spec import (
    CONFIDENCE_THRESHOLD,
    QuerySpec,
    RequestType,
    needs_clarification,
)
from graph.registry import ROUTE
from graph.state import GraphState

logger = logging.getLogger(__name__)

# 조건이 하나도 없을 때 갈 곳. 조건 탐색은 빈손으로도 돌아간다.
기본_시나리오 = ROUTE[RequestType.SEARCH]

# 비어 있는 필드별로 무엇을 되물을지. 문장이 코드에 있으므로 같은 상황에서
# 항상 같은 것을 묻는다.
_질문 = {
    "base_product_ref": "어떤 제품을 말씀하시는지 알려주세요.",
    "budget.total": "전체 예산이 얼마인가요?",
    "bundle_steps": "어떤 단계로 세트를 짤까요? 예를 들어 토너, 세럼, 크림처럼요.",
}
_막연할_때 = "어떤 제품을 찾으시는지 조금 더 알려주세요. 카테고리나 가격대를 말씀해 주시면 좋아요."


async def router(state: GraphState) -> dict:
    try:
        spec = QuerySpec.model_validate(state.get("query_spec") or {})
    except ValidationError:
        # Normalize 가 내보낸 값이라 여기까지 오면 스펙이 깨진 것이다.
        # 경로를 못 정하면 아무것도 못 하므로 조건 탐색으로 두고 되묻는다.
        logger.warning("router: query_spec 을 읽지 못했다. 되묻는다.")
        return {"scenario": 기본_시나리오, "clarify_question": _막연할_때}

    시나리오 = ROUTE[spec.request_type]

    # 조건 수정은 직전 job 의 스냅샷에서 후보와 조건을 꺼내 쓴다. 그게 없으면
    # 수정할 대상이 없으므로 새 검색으로 본다. 사용자에게 물어볼 일은 아니다.
    if spec.request_type is RequestType.REFINE and not state.get("parent_job_id"):
        logger.info("router: 수정할 직전 결과가 없다. 새 검색으로 돈다.")
        시나리오 = 기본_시나리오

    나감: dict = {"scenario": 시나리오}

    if not needs_clarification(spec):
        return 나감

    # 되묻기는 한 번까지다. 답을 받고도 모자라면 있는 값으로 진행한다.
    # 계속 물으면 사용자는 결과를 영영 못 본다.
    if (state.get("clarify_count") or 0) >= 1:
        logger.info("router: 이미 한 번 물었다. 있는 값으로 진행한다.")
        return 나감

    빠진 = spec.missing_required()
    if 빠진:
        나감["clarify_question"] = _질문.get(빠진[0], _막연할_때)
    else:
        # 필수 값은 다 있는데 무엇을 원하는지가 막연한 경우다.
        assert spec.confidence < CONFIDENCE_THRESHOLD
        나감["clarify_question"] = _막연할_때
    return 나감
