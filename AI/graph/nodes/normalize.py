"""질의를 QuerySpec 으로 옮긴다.

READS:  raw_query, clarify_question, clarify_answer
WRITES: query_spec

LLM 은 빈칸만 채운다. 경로는 채워진 값을 보고 코드가 정한다(router).
그래야 같은 질문이 매번 같은 곳으로 가고, 흔들리는 자리가 여기 하나로
좁혀져 골든셋으로 잴 수 있다.

검증에 실패하면 한 번만 다시 묻는다. 두 번째도 실패하면 확신도 0 으로
비워 내보낸다. 라우터가 그것을 보고 되묻기로 넘긴다. 실패를 예외로 올리면
"무슨 말인지 모르겠다"가 서버 오류로 나간다.

제품 종류는 표준 이름으로 바꾼다(rules/product_types.py). "스킨"은 "토너"가 된다.
목록에 없거나 카테고리에 맞지 않는 종류는 특징에서 빼고 문장 조건으로 옮긴다.
필터는 목록의 이름으로만 비교하므로, 모르는 이름을 특징에 두면 맞는 상품이 하나도
남지 않는다. 문장 조건으로 옮기면 검색 문장에는 그대로 들어간다. 세트 단계의 종류도
같이 바꾸고, 모르면 비운다.

모델이 빈 값 자리에 문자열 "null" 을 넣는 일이 있다. 검증 전에 빈 값으로 읽는다. 그대로 두면
카테고리 검증에 두 번 실패해 되묻기로 넘어가고, 그 사이 예산과 세트 경로를 잃는다.

제품 종류는 문자열 하나다. ["토너"] 처럼 하나만 든 배열은 풀어서 같은 규칙을 적용한다.
그 밖의 모양(여럿 든 배열, 숫자 등)은 형식을 어긴 것으로 보고 다시 묻는다. 그냥 넘기면
종류가 필터와 검색 문장에서 모두 사라진 채 성공으로 나간다.

services.llm 은 함수 안에서 가져온다. 최상단에서 가져오면 config 를 타고
API 키를 요구해, 키 없는 곳에서는 이 노드를 불러오지도 못한다.
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from contracts.query_spec import QuerySpec, RequestType
from graph.state import GraphState
from prompts.query_normalize import QUERY_NORMALIZE_SYSTEM
from rules.product_types import canonical

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


def _카테고리(값) -> str | None:
    return 값.value if 값 is not None else None


_빈_값_글자 = frozenset({"null", "none"})


def _null_글자_비우기(값):
    """문자열 "null" 을 빈 값으로 읽는다. 목록에서는 빼고, 특징에서는 그 키를 뺀다."""
    if isinstance(값, str) and 값.strip().lower() in _빈_값_글자:
        return None
    if isinstance(값, list):
        return [x for x in map(_null_글자_비우기, 값) if x is not None]
    if isinstance(값, dict):
        return {키: _null_글자_비우기(v) for 키, v in 값.items()}
    return 값


def _null_만_든_목록(원래, 다듬은) -> bool:
    """원래 값이 있던 목록이 "null" 을 빼고 나니 비었다. 처음부터 빈 목록이면 아니다."""
    return isinstance(원래, list) and bool(원래) and 다듬은 == []


def _응답_다듬기(원본: dict) -> dict:
    다듬은 = _null_글자_비우기(원본)
    원래_특징 = 원본.get("features")
    if isinstance(원래_특징, dict) and isinstance(다듬은.get("features"), dict):
        # ["null"] 처럼 null 만 든 특징도 빈 값으로 보고 키를 뺀다. 빈 목록으로 남기면
        # 제품 종류 형식 오류로 다시 묻게 되고, 두 번 받으면 예산과 세트까지 잃는다.
        다듬은["features"] = {
            키: v for 키, v in 다듬은["features"].items()
            if v is not None and not _null_만_든_목록(원래_특징.get(키), v)
        }
    return 다듬은


class _종류_형식_오류(ValueError):
    """제품 종류가 문자열 하나로 오지 않았다."""


def _한_종류(값):
    """제품 종류 값을 문자열 하나(또는 None)로 맞춘다. 맞출 수 없으면 형식 오류다."""
    if 값 is None or isinstance(값, str):
        return 값
    if isinstance(값, list) and len(값) == 1 and isinstance(값[0], str):
        return 값[0]
    raise _종류_형식_오류(f"제품 종류는 문자열 하나여야 한다: {값!r}")


def _종류_다듬기(spec: QuerySpec) -> QuerySpec:
    """제품 종류를 표준 이름으로 바꾼다. 모르는 종류는 문장 조건으로 옮긴다."""
    특징 = dict(spec.features)
    조건 = list(spec.conditions)
    if "product_type" in 특징:
        값 = _한_종류(특징.pop("product_type"))
        표준 = canonical(값, _카테고리(spec.category))
        if 표준:
            특징["product_type"] = 표준
        elif isinstance(값, str) and 값.strip():
            logger.info("normalize: 목록에 없는 종류를 문장 조건으로 옮긴다 %r", 값)
            if 값.strip() not in 조건:
                조건.append(값.strip())

    단계들 = [
        단계.model_copy(update={"product_type": canonical(단계.product_type, _카테고리(단계.category))})
        if 단계.product_type else 단계
        for 단계 in spec.bundle_steps
    ]
    return spec.model_copy(update={"features": 특징, "conditions": 조건, "bundle_steps": 단계들})


async def parse_query(
    사용자_말: str,
    raw: str,
    *,
    system: str = QUERY_NORMALIZE_SYSTEM,
    temperature: float = 0.0,
) -> QuerySpec | None:
    """LLM 에 물어 QuerySpec 을 만든다. 두 번 시도해도 읽지 못하면 None.

    프롬프트와 temperature 를 바꿔 부를 수 있게 노드에서 떼어 두었다. 평가 도구가
    같은 해석 과정을 다른 설정으로 태워 견준다. raw 는 로그에만 쓴다.
    """
    # 부를 일이 생긴 뒤에 가져온다. 최상단에 두면 설정과 SDK 를 통째로 불러온다.
    from services.llm import LLMRole, get_llm

    llm = get_llm(LLMRole.NORMALIZE)

    for 시도 in range(1, _최대_시도 + 1):
        원본 = await llm.chat_json(system=system, user=사용자_말, temperature=temperature)
        if 원본 is None:
            logger.warning("normalize: JSON 이 아니다 (%d/%d) %r", 시도, _최대_시도, raw)
            continue
        try:
            spec = QuerySpec.model_validate(
                _응답_다듬기(원본) if isinstance(원본, dict) else 원본
            )
        except ValidationError as e:
            # 어느 필드가 틀렸는지 남긴다. 골든셋을 만들 때 이 로그가 재료가 된다.
            logger.warning(
                "normalize: 스펙에 맞지 않다 (%d/%d) %r — %s",
                시도, _최대_시도, raw, e.errors()[:3],
            )
            continue
        try:
            다듬은 = _종류_다듬기(spec)
        except _종류_형식_오류 as e:
            logger.warning("normalize: %s (%d/%d) %r", e, 시도, _최대_시도, raw)
            continue
        return 다듬은

    return None


async def normalize(state: GraphState) -> dict:
    raw = (state.get("raw_query") or "").strip()
    if not raw:
        return {"query_spec": _빈_스펙("").model_dump(mode="json")}

    spec = await parse_query(_사용자_말(state, raw), raw)
    if spec is None:
        logger.warning("normalize: 해석 실패, 되묻기로 넘긴다 %r", raw)
        spec = _빈_스펙(raw)
    return {"query_spec": spec.model_dump(mode="json")}
