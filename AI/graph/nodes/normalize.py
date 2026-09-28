"""질의를 QuerySpec 으로 옮긴다.

READS:  raw_query, clarify_question, clarify_answer
WRITES: query_spec

LLM 은 빈칸만 채운다. 경로는 채워진 값을 보고 코드가 정한다(router).
그래야 같은 질문이 매번 같은 곳으로 가고, 흔들리는 자리가 여기 하나로
좁혀져 골든셋으로 잴 수 있다.

검증에 실패하면 한 번만 다시 묻는다. 두 번째도 실패하면 확신도 0 으로
비워 내보낸다. 라우터가 그것을 보고 되묻기로 넘긴다. 실패를 예외로 올리면
"무슨 말인지 모르겠다"가 서버 오류로 나간다.

services.llm 은 함수 안에서 가져온다. 최상단에서 가져오면 config 를 타고
API 키를 요구해, 키 없는 곳에서는 이 노드를 불러오지도 못한다.
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from contracts.query_spec import QuerySpec, RequestType
from graph.state import GraphState
from prompts.query_normalize import QUERY_NORMALIZE_SYSTEM

logger = logging.getLogger(__name__)

# 두 번 시도한다. 형식을 한 번 어긴 모델이 세 번째에 지킬 가능성은 낮고,
# 그동안 사용자는 계속 기다린다.
_최대_시도 = 2


def _빈_스펙(raw_query: str) -> QuerySpec:
    """해석하지 못했을 때 내보내는 값. 확신도 0 이라 라우터가 되묻기로 보낸다."""
    return QuerySpec(request_type=RequestType.SEARCH, conditions=[raw_query], confidence=0.0)


def _사용자_말(state: GraphState, raw: str) -> str:
    """되물었다면 무엇을 물었고 뭐라 답했는지까지 같이 넘긴다.

    답만 주면 "10만원" 같은 말이 무슨 뜻인지 알 수 없다. 원래 질의에 이어
    붙이면 화면에 보여줄 질의가 뒤섞인다. 그래서 따로 적어 함께 준다.
    """
    답 = (state.get("clarify_answer") or "").strip()
    if not 답:
        return raw
    질문 = (state.get("clarify_question") or "").strip()
    return f"원래 질의: {raw}\n되물은 것: {질문}\n사용자의 답: {답}"


async def normalize(state: GraphState) -> dict:
    raw = (state.get("raw_query") or "").strip()
    if not raw:
        return {"query_spec": _빈_스펙("").model_dump(mode="json")}

    # 부를 일이 생긴 뒤에 가져온다. 함수 첫 줄에 두면 질의가 비어 돌려보낼
    # 때에도 설정과 SDK 를 통째로 불러오게 된다.
    from services.llm import LLMRole, get_llm

    llm = get_llm(LLMRole.NORMALIZE)
    사용자_말 = _사용자_말(state, raw)

    for 시도 in range(1, _최대_시도 + 1):
        원본 = await llm.chat_json(system=QUERY_NORMALIZE_SYSTEM, user=사용자_말)
        if 원본 is None:
            logger.warning("normalize: JSON 이 아니다 (%d/%d) %r", 시도, _최대_시도, raw)
            continue
        try:
            spec = QuerySpec.model_validate(원본)
        except ValidationError as e:
            # 어느 필드가 틀렸는지 남긴다. 골든셋을 만들 때 이 로그가 재료가 된다.
            logger.warning(
                "normalize: 스펙에 맞지 않다 (%d/%d) %r — %s",
                시도, _최대_시도, raw, e.errors()[:3],
            )
            continue
        return {"query_spec": spec.model_dump(mode="json")}

    logger.warning("normalize: 해석 실패, 되묻기로 넘긴다 %r", raw)
    return {"query_spec": _빈_스펙(raw).model_dump(mode="json")}
