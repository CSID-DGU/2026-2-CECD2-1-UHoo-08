"""Router 가 지켜야 할 성질.

라우터가 잘못 고르면 시나리오 전체가 오동작한다. 그래서 LLM 을 부르지 않고,
같은 값이면 언제나 같은 곳으로 가야 한다.
"""
import pytest

from contracts.query_spec import Budget, BundleStep, QuerySpec, RequestType
from graph.nodes.router import router


def _스펙(**덮어쓰기) -> dict:
    기본 = dict(request_type=RequestType.SEARCH, confidence=0.9)
    기본.update(덮어쓰기)
    return QuerySpec(**기본).model_dump(mode="json")


@pytest.mark.asyncio
@pytest.mark.parametrize("유형, 기대", [
    (RequestType.SEARCH, "S2_SEARCH"),
    (RequestType.EVALUATE, "S1_EVALUATE"),
    (RequestType.BUNDLE, "S6_BUNDLE"),
    (RequestType.REFINE, "S7_REFINE"),
])
async def test_요청_유형이_경로를_정한다(유형, 기대):
    채움 = {
        RequestType.EVALUATE: {"base_product_ref": "라네즈 네오쿠션"},
        RequestType.BUNDLE: {"budget": Budget(total=100_000),
                             "bundle_steps": [BundleStep(label="토너")]},
    }.get(유형, {})
    나옴 = await router({"query_spec": _스펙(request_type=유형, **채움),
                        "parent_job_id": "j0"})
    assert 나옴["scenario"] == 기대
    assert 나옴["clarify_question"] is None


@pytest.mark.asyncio
async def test_같은_값이면_항상_같은_곳으로_간다():
    스펙 = _스펙(category="base")
    나옴 = [await router({"query_spec": 스펙}) for _ in range(5)]
    assert {n["scenario"] for n in 나옴} == {"S2_SEARCH"}


@pytest.mark.asyncio
async def test_필수_값이_비면_그_값을_묻는다():
    나옴 = await router({"query_spec": _스펙(request_type=RequestType.EVALUATE)})
    assert 나옴["scenario"] == "S1_EVALUATE"
    assert "어떤 제품" in 나옴["clarify_question"]


@pytest.mark.asyncio
async def test_예산_세트는_예산부터_묻는다():
    나옴 = await router({"query_spec": _스펙(request_type=RequestType.BUNDLE)})
    assert "예산" in 나옴["clarify_question"]


@pytest.mark.asyncio
async def test_막연한_질의는_조건을_더_묻는다():
    """필수 값은 다 있는데 무엇을 원하는지가 분명하지 않은 경우다."""
    나옴 = await router({"query_spec": _스펙(confidence=0.2)})
    assert 나옴["scenario"] == "S2_SEARCH"
    assert "조금 더" in 나옴["clarify_question"]


@pytest.mark.asyncio
async def test_이미_한_번_물었으면_그냥_진행한다():
    """계속 물으면 사용자는 결과를 영영 보지 못한다."""
    나옴 = await router({"query_spec": _스펙(confidence=0.1), "clarify_count": 1})
    assert 나옴 == {"scenario": "S2_SEARCH", "clarify_question": None}


@pytest.mark.asyncio
async def test_수정할_직전_결과가_없으면_새_검색으로_돈다():
    """조건 수정은 직전 job 의 후보를 꺼내 쓴다. 그게 없으면 수정할 대상이
    없다. 사용자에게 물어볼 일은 아니다."""
    나옴 = await router({"query_spec": _스펙(request_type=RequestType.REFINE)})
    assert 나옴["scenario"] == "S2_SEARCH"
    assert 나옴["clarify_question"] is None


@pytest.mark.asyncio
async def test_스펙이_깨져_있으면_되묻는다():
    나옴 = await router({"query_spec": {"request_type": "NOPE"}})
    assert 나옴["scenario"] == "S2_SEARCH"
    assert 나옴["clarify_question"]


@pytest.mark.asyncio
async def test_해석하지_못한_질의는_되묻는다():
    """Normalize 가 두 번 실패하면 확신도 0 으로 내보낸다."""
    나옴 = await router({"query_spec": _스펙(confidence=0.0)})
    assert 나옴["clarify_question"]


@pytest.mark.asyncio
async def test_물을_것이_없으면_이전_질문을_지운다():
    """되물었다가 답을 받아 다시 도는 경우다. 남겨 두면 같은 자리에서 또 멈춘다."""
    나옴 = await router({
        "query_spec": _스펙(category="skincare"),
        "clarify_question": "전체 예산이 얼마인가요?",
    })
    assert 나옴["clarify_question"] is None
