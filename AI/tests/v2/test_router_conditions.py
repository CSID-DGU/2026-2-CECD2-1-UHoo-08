"""시나리오 결정 실험 조건 가운데 LLM 없이 도는 규칙을 본다."""
import pytest

from eval.router_conditions import (
    CONDITIONS,
    is_underspecified,
    keyword_request_type,
    majority_vote,
    structural_clarify,
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


_빈_양식 = {
    "request_type": "SEARCH", "category": None, "features": {}, "conditions": [],
    "budget": {"max": None, "total": None}, "base_product_ref": None,
}


def test_단서가_하나도_없으면_막연한_질문이다():
    assert is_underspecified(_빈_양식)


@pytest.mark.parametrize("채운", [
    {"category": "base"},
    {"features": {"finish": "매트"}},
    {"conditions": ["여름"]},
    {"budget": {"max": 30000, "total": None}},
    {"budget": {"max": None, "total": 100000}},
    {"base_product_ref": "어떤 쿠션"},
])
def test_단서가_하나라도_있으면_막연한_질문이_아니다(채운):
    assert not is_underspecified({**_빈_양식, **채운})


def test_구조_규칙은_세_경우에_되묻는다():
    채운 = {**_빈_양식, "category": "base"}
    assert structural_clarify(None, ())                       # 답을 읽지 못했다
    assert structural_clarify(채운, ("budget.total",))        # 필수 값이 비었다
    assert structural_clarify(_빈_양식, ())                   # 단서가 없다
    assert not structural_clarify(채운, ())


def test_가장_많이_나온_답과_그_비율을_낸다():
    assert majority_vote(["S2", "S1", "S2", "S2", "S1"]) == ("S2", 0.6)
    assert majority_vote(["S1"] * 5) == ("S1", 1.0)


def test_같은_수면_먼저_나온_답을_고른다():
    assert majority_vote(["S1", "S2", "S2", "S1"]) == ("S1", 0.5)


@pytest.mark.parametrize("말, 알려_주나", [
    ("라운드랩 독도 토너", True),
    ("독도 토너", True),
    ("이거", False),
    ("그 선크림", False),
    ("이 제품", False),
    ("방금 그거", False),
    ("", False),
    (None, False),
])
def test_가리키는_말과_종류_이름뿐이면_어떤_제품인지_알_수_없다(말, 알려_주나):
    from eval.router_conditions import names_a_product

    assert names_a_product(말) is 알려_주나


def test_평가_요청인데_제품을_알_수_없으면_되묻는다():
    평가 = {**_빈_양식, "request_type": "EVALUATE", "category": "sun"}
    assert structural_clarify({**평가, "base_product_ref": "그 선크림"}, ())
    assert not structural_clarify({**평가, "base_product_ref": "달바 워터풀 선크림"}, ())
