"""시나리오 결정 실험 조건 가운데 LLM 없이 도는 규칙을 본다."""
import pytest

from eval.router_conditions import (
    CONDITIONS,
    keyword_request_type,
    majority_vote,
)


@pytest.mark.parametrize("질문, 종류", [
    ("10만원으로 스킨케어 세트 짜줘", "BUNDLE"),
    ("6만원으로 토너랑 크림 골라줘", "BUNDLE"),          # 세트라는 말은 없지만 종류가 둘이다
    ("3만원 이하 선크림 추천", "SEARCH"),                # 금액은 있지만 하나만 찾는다
    ("스킨케어 세트 추천해줘", "SEARCH"),                # 금액이 없다
    ("라운드랩 독도 토너 어때?", "EVALUATE"),
    ("토너 어때?", "SEARCH"),                            # 제품 이름이 없다
    ("그 토너 어때?", "SEARCH"),                         # 가리키는 말뿐이다
    ("건성 피부에 좋은 수분 크림", "SEARCH"),
])
def test_단어_규칙으로_요청_종류를_정한다(질문, 종류):
    assert keyword_request_type(질문) == 종류


def test_선크림을_크림으로_또_세지_않는다():
    assert keyword_request_type("3만원으로 선크림 하나") == "SEARCH"


@pytest.mark.asyncio
async def test_규칙만_쓰는_조건은_직전_결과가_있으면_조건_수정으로_보낸다():
    나온 = await CONDITIONS["b0"].run({"raw_query": "수분크림 추천해줘", "parent_job_id": "prev"})
    assert 나온.scenario == "S7_REFINE"
    assert not 나온.clarify_rule
    assert not 나온.extracts_values


@pytest.mark.asyncio
async def test_규칙만_쓰는_조건은_되묻지_않고_확률도_내지_않는다():
    나온 = await CONDITIONS["b0"].run({"raw_query": "추천해줘"})
    assert 나온.scenario == "S2_SEARCH"
    assert not 나온.clarify_rule
    assert 나온.scenario_prob is None


def test_가장_많이_나온_답과_그_비율을_낸다():
    assert majority_vote(["S2", "S1", "S2", "S2", "S1"]) == ("S2", 0.6)
    assert majority_vote(["S1"] * 5) == ("S1", 1.0)


def test_같은_수면_먼저_나온_답을_고른다():
    assert majority_vote(["S1", "S2", "S2", "S1"]) == ("S1", 0.5)


@pytest.mark.asyncio
@pytest.mark.parametrize("답들, 확률", [
    ([None] * 5, 0.0),                                  # 다섯 번 모두 읽지 못했다
    ([None, None, None, "S2_SEARCH", "S2_SEARCH"], 0.4),  # 내보내는 시나리오에 두 표
])
async def test_해석_실패가_이기면_내보내는_시나리오에_준_표의_비율을_확률로_쓴다(monkeypatch, 답들, 확률):
    from eval import router_conditions

    차례 = iter(답들)

    async def 가짜_해석(입력, **_):
        시나리오 = next(차례)
        if 시나리오 is None:
            return None, "S2_SEARCH", True
        return {"request_type": "SEARCH"}, 시나리오, False

    monkeypatch.setattr(router_conditions, "_구조_규칙으로_해석", 가짜_해석)
    나온 = await CONDITIONS["a3"].run({"raw_query": "추천해줘"})
    assert 나온.scenario == "S2_SEARCH"
    assert 나온.clarify_rule
    assert 나온.scenario_prob == 확률


@pytest.mark.asyncio
@pytest.mark.parametrize("조건", ["a4", "a5"])
async def test_jev_가_먼저_실패해도_LLM_호출이_끝난_뒤에_예외를_낸다(monkeypatch, 조건):
    import asyncio

    from eval import router_conditions

    끝남 = []

    async def 느린_해석(입력, **_):
        await asyncio.sleep(0.01)
        끝남.append("llm")
        return {"request_type": "SEARCH"}, "S2_SEARCH", False

    async def 실패하는_jev(질문):
        raise RuntimeError("jev")

    monkeypatch.setattr(router_conditions, "_구조_규칙으로_해석", 느린_해석)
    monkeypatch.setattr(router_conditions, "_jev_판단", 실패하는_jev)
    with pytest.raises(RuntimeError, match="jev"):
        await CONDITIONS[조건].run({"raw_query": "선크림 추천"})
    assert 끝남 == ["llm"]
