"""평가 러너의 비교 규칙을 본다.

러너 자체는 실제 LLM 을 부르므로 CI 에서 돌리지 않는다. 대신 "무엇을
맞다고 볼 것인가"만 여기서 고정한다. 이 규칙이 틀리면 리포트 숫자가
전부 틀린 값이 되는데, 숫자만 봐서는 알아챌 수 없다.
"""
import pytest

from eval.run_router_eval import compare, evaluate, to_markdown

_스펙 = {
    "request_type": "SEARCH", "category": "base",
    "budget": {"max": 30000, "total": None},
    "use_env": False, "value_seeking": True, "target": "SELF",
    "base_product_ref": None,
}


def test_기대값에_적힌_키만_본다():
    """모든 필드를 고정하면 프롬프트를 조금 고쳐도 골든셋이 통째로 깨진다."""
    판정 = compare({"scenario": "S2_SEARCH"}, _스펙, "S2_SEARCH", False)
    assert 판정 == {"scenario": True}


def test_중첩된_값도_꺼내_본다():
    판정 = compare({"budget_max": 30000, "budget_total": None}, _스펙, "S2_SEARCH", False)
    assert 판정 == {"budget_max": True, "budget_total": True}


def test_기준_상품은_있는지만_본다():
    """상품 표현은 모델마다 조금씩 다르게 적는다. 문자열을 맞추게 하면
    "라네즈 네오쿠션 21호"와 "네오쿠션 21호"가 오답이 된다."""
    스펙 = dict(_스펙, base_product_ref="라네즈 네오쿠션 21호")
    assert compare({"base_product_ref_present": True}, 스펙, "S1_EVALUATE", False)


def test_쓸_수_없는_키는_바로_알린다():
    """조용히 무시하면 골든셋에 오타가 난 항목이 영영 검사되지 않는다."""
    with pytest.raises(KeyError, match="skin_type"):
        compare({"skin_type": "DRY"}, _스펙, "S2_SEARCH", False)


@pytest.mark.asyncio
async def test_항목별로_맞은_수를_센다():
    기록 = [
        {"id": "router-g-0001", "input": {"raw_query": "쿠션"},
         "expected": {"scenario": "S2_SEARCH", "category": "base"}},
        {"id": "router-g-0002", "input": {"raw_query": "세트"},
         "expected": {"scenario": "S6_BUNDLE", "category": "base"}},
    ]

    async def 한_건(질의):
        return _스펙, "S2_SEARCH", False

    결과 = await evaluate(기록, 한_건)
    assert 결과["전체"]["scenario"] == 2 and 결과["맞음"]["scenario"] == 1
    assert 결과["맞음"]["category"] == 2
    assert len(결과["틀림"]) == 1
    assert 결과["틀림"][0]["틀린_항목"]["scenario"] == {"기대": "S6_BUNDLE", "실제": "S2_SEARCH"}


@pytest.mark.asyncio
async def test_한_건이_터져도_나머지를_잰다():
    """한 질의에서 LLM 이 죽었다고 평가를 처음부터 다시 돌리면, 매번
    돈을 내고 처음부터 시작하게 된다."""
    기록 = [
        {"id": "router-g-0001", "input": {"raw_query": "터짐"}, "expected": {"scenario": "S2_SEARCH"}},
        {"id": "router-g-0002", "input": {"raw_query": "쿠션"}, "expected": {"scenario": "S2_SEARCH"}},
    ]

    async def 한_건(질의):
        if 질의 == "터짐":
            raise RuntimeError("타임아웃")
        return _스펙, "S2_SEARCH", False

    결과 = await evaluate(기록, 한_건)
    assert 결과["맞음"]["scenario"] == 1
    assert any("타임아웃" in (사례.get("error") or "") for 사례 in 결과["틀림"])


@pytest.mark.asyncio
async def test_리포트에_틀린_사례가_들어간다():
    """숫자만 있으면 무엇을 고쳐야 할지 알 수 없다."""
    기록 = [{"id": "router-g-0002", "input": {"raw_query": "세트 짜줘"},
            "tags": ["ambiguous"], "expected": {"scenario": "S6_BUNDLE"}}]

    async def 한_건(질의):
        return _스펙, "S2_SEARCH", False

    글 = to_markdown(await evaluate(기록, 한_건), "test")
    assert "router-g-0002" in 글 and "세트 짜줘" in 글 and "ambiguous" in 글
