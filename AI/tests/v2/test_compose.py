"""결과 조립이 지켜야 할 성질.

BE 가 그대로 저장하고 FE 가 그대로 그리므로 계약 모양이 틀리면 화면이 깨진다.
꼭 필요한 부품 없이 빈 결과가 완료로 나가면 "추천 없음" 으로 읽힌다.
"""
import json
import sys
import types
from pathlib import Path

import pytest

from contracts.result import RecommendationResult
from graph.nodes import compose as 노드

_BE_예시 = Path(__file__).resolve().parents[3] / "BE/src/test/resources/ai-results/S2_SEARCH.json"


@pytest.fixture(autouse=True)
def 트렌드(monkeypatch):
    """트렌드 조회를 가짜로 둔다. 기본은 빈 테이블이다."""
    상태 = {"ids": set(), "터짐": False}

    def get_trending_product_ids():
        if 상태["터짐"]:
            raise RuntimeError("DB 끊김")
        return 상태["ids"]

    모듈 = types.SimpleNamespace(get_trending_product_ids=get_trending_product_ids)
    import db
    monkeypatch.setitem(sys.modules, "db.trend_reader", 모듈)
    monkeypatch.setattr(db, "trend_reader", 모듈, raising=False)
    return 상태


@pytest.fixture(autouse=True)
def LLM(monkeypatch):
    """이유 문장 LLM 을 가짜로 둔다. 기본은 응답 없음(규칙 문장)이다."""
    상태: dict = {"응답": None, "예외": None, "받은": []}

    class 가짜:
        async def chat_json(self, system, user, **_):
            상태["받은"].append(user)
            if 상태["예외"]:
                raise 상태["예외"]
            return 상태["응답"]

    모듈 = types.SimpleNamespace(LLMRole=types.SimpleNamespace(COMPOSE="compose"),
                                get_llm=lambda role: 가짜())
    import services
    monkeypatch.setitem(sys.modules, "services.llm", 모듈)
    monkeypatch.setattr(services, "llm", 모듈, raising=False)
    return 상태


@pytest.fixture
def 가성비_설명(monkeypatch):
    """C 의 가성비 항목에 설명 함수가 있는 경우."""
    받은: list = []

    async def explain(products, ctx):
        받은.append([p["product_id"] for p in products])
        return {p["product_id"]: "평소 쓰는 제품보다 약 30% 저렴해요" for p in products}

    async def value_signal(products, ctx):
        return {}

    모듈 = types.SimpleNamespace(explain=explain, value_signal=value_signal)
    import scorers
    monkeypatch.setitem(sys.modules, "scorers.value_signal", 모듈)
    monkeypatch.setattr(scorers, "value_signal", 모듈, raising=False)
    return 받은


def _점수표(pid, total, **항목):
    breakdown = [{"key": k, "label": k, "score": v, "weight": 0.25} for k, v in 항목.items()]
    return {"product_id": pid, "total": total, "breakdown": breakdown}


def _메타(pid, **값):
    return {"name": f"상품{pid}", "brand": "브랜드", "image_url": None, "price": 20000,
            "category": "base", "feature_json": {}, **값}


def _상태(**값):
    return {
        "scenario": "S2_SEARCH", "job_id": "j1", "user_id": "u1",
        "raw_query": "여름 매트 쿠션",
        "query_spec": {"request_type": "SEARCH", "category": "base",
                       "features": {"finish": "매트"}, "conditions": ["여름"]},
        "scored": [_점수표("p1", 85, personalization=93, budget_fit=87.5),
                   _점수표("p2", 72)],
        "product_meta": {"p1": _메타("p1"), "p2": _메타("p2"), "c1": _메타("c1"),
                         "o1": _메타("o1")},
        "excluded": [{"product_id": "o1", "name": None, "reason": "OWNED",
                      "detail": "이미 쓰고 계신 제품이에요"}],
        "collaborative": [{"product_id": "c1", "satisfaction_percent": 70}],
        "trace": ["retrieve", "inventory", "prefilter", "score", "collaborative"],
        **값,
    }


@pytest.mark.asyncio
async def test_조건_탐색_결과가_계약을_지키고_BE_예시와_키가_같다():
    결과 = (await 노드.compose(_상태()))["result"]

    RecommendationResult.model_validate(결과)
    예시 = json.loads(_BE_예시.read_text())
    assert set(결과) == set(예시)
    assert set(결과["items"][0]) == set(예시["items"][0])
    assert set(결과["query"]) == set(예시["query"])
    assert set(결과["excluded"][0]) == set(예시["excluded"][0])


@pytest.mark.asyncio
async def test_카드와_요약과_제외와_비슷한_사람들을_채운다():
    결과 = (await 노드.compose(_상태()))["result"]

    assert [i["productId"] for i in 결과["items"]] == ["p1", "p2"]
    카드 = 결과["items"][0]
    assert (카드["name"], 카드["price"], 카드["totalScore"]) == ("상품p1", 20000, 85)
    assert [b["key"] for b in 카드["breakdown"]] == ["personalization", "budget_fit"]
    assert 카드["reason"] == "내 피부 적합, 예산 적합 점수가 높아요"
    assert 결과["items"][1]["reason"] is None
    assert 결과["query"]["conditions"] == ["매트", "여름"]
    # 이름이 비어 있으면 상품 정보에서 채운다
    assert 결과["excluded"][0]["name"] == "상품o1"
    assert 결과["similarUserProducts"][0]["totalScore"] == 70
    assert 결과["similarUserProducts"][0]["breakdown"] == []


@pytest.mark.asyncio
async def test_카드는_10개까지고_상품_정보가_없으면_뺀다():
    점수들 = [_점수표(f"p{i}", 90 - i) for i in range(12)]
    메타 = {f"p{i}": _메타(f"p{i}") for i in range(12) if i != 3}
    결과 = (await 노드.compose(_상태(scored=점수들, product_meta=메타)))["result"]
    ids = [i["productId"] for i in 결과["items"]]
    assert len(ids) == 10 and "p3" not in ids and ids[-1] == "p10"


@pytest.mark.asyncio
async def test_배지는_정한_순서로_두_개까지_단다(트렌드, 가성비_설명):
    트렌드["ids"] = {"p1"}
    필요 = {"key": "UV", "reason_text": "요즘 자외선이 강해요", "category": "base", "features": {}}
    결과 = (await 노드.compose(_상태(
        scored=[_점수표("p1", 90, env_fit=80, value_signal=75)],
        conflict_marks={"p1": [{"user_product_id": "u1", "name": "레티놀 세럼",
                                "level": "SEPARATE", "advice": "레티놀 세럼과 시간대를 나눠 쓰세요"}]},
        env_summary={"needs": [필요]},
    )))["result"]
    assert [b["type"] for b in 결과["items"][0]["badges"]] == ["CONFLICT_SEPARATE", "ENV"]


@pytest.mark.asyncio
async def test_가성비와_요즘_언급_배지(트렌드, 가성비_설명):
    트렌드["ids"] = {"p1", "p2"}
    결과 = (await 노드.compose(_상태(
        scored=[_점수표("p1", 90, value_signal=75), _점수표("p2", 80, value_signal=60)],
    )))["result"]
    assert [(b["type"], b["text"]) for b in 결과["items"][0]["badges"]] == [
        ("VALUE", "평소 쓰는 제품보다 약 30% 저렴해요"), ("TREND", "요즘 언급이 늘고 있어요")]
    # 가성비 점수가 기준보다 낮으면 설명을 묻지 않는다
    assert 가성비_설명 == [["p1"]]
    assert [b["type"] for b in 결과["items"][1]["badges"]] == ["TREND"]


@pytest.mark.asyncio
async def test_가성비_설명_함수가_없으면_가성비_배지가_없다():
    결과 = (await 노드.compose(_상태(scored=[_점수표("p1", 90, value_signal=95)])))["result"]
    assert 결과["items"][0]["badges"] == []


@pytest.mark.asyncio
async def test_환경_점수가_높아도_채우는_기능이_없으면_환경_배지가_없다():
    필요 = {"key": "UV", "reason_text": "요즘 자외선이 강해요", "category": "sun", "features": {}}
    결과 = (await 노드.compose(_상태(
        scored=[_점수표("p1", 90, env_fit=95)], env_summary={"needs": [필요]},
    )))["result"]
    assert 결과["items"][0]["badges"] == []


@pytest.mark.asyncio
async def test_트렌드를_읽지_못해도_결과는_만든다(트렌드):
    트렌드["터짐"] = True
    결과 = (await 노드.compose(_상태()))["result"]
    assert [i["productId"] for i in 결과["items"]] == ["p1", "p2"]


@pytest.mark.asyncio
async def test_예산_세트는_조합을_그대로_싣고_단계를_조건으로_쓴다():
    조합 = {
        "label": "균형형", "total_price": 50000, "over_budget_reason": None,
        "items": [{"product_id": "p1", "name": "토너", "brand": "b", "total_score": 80,
                   "slot_key": "toner", "slot_label": "토너"}],
    }
    결과 = (await 노드.compose(_상태(
        scenario="S6_BUNDLE",
        query_spec={"request_type": "BUNDLE", "budget": {"total": 100000},
                    "bundle_steps": [{"label": "토너"}, {"label": "크림"}]},
        bundles=[조합],
        trace=["budget", "retrieve", "inventory", "prefilter", "score", "bundle"],
    )))["result"]
    RecommendationResult.model_validate(결과)
    assert 결과["items"] == []
    assert 결과["bundles"][0]["items"][0]["slotKey"] == "toner"
    assert 결과["query"]["conditions"] == ["토너", "크림"]
    assert 결과["query"]["budgetTotal"] == 100000


@pytest.mark.asyncio
@pytest.mark.parametrize("시나리오, 빈_단계", [
    ("S6_BUNDLE", "bundle"), ("S6_BUNDLE", "budget"),
    ("HOME_ENV", "env_history"), ("HOME_ROUTINE", "compatibility"),
])
async def test_꼭_필요한_단계가_없으면_결과를_만들지_않는다(시나리오, 빈_단계):
    with pytest.raises(노드.부품_없음):
        await 노드.compose(_상태(scenario=시나리오, trace=[f"{빈_단계}(stub)"]))


@pytest.mark.asyncio
@pytest.mark.parametrize("시나리오", ["HOME_ENV", "HOME_ROUTINE"])
async def test_홈_결과는_분석_칸_없이_내보내지_않는다(시나리오):
    """분석 칸이 비어 있으면 BE 가 카드를 계속 분석 전으로 내려보낸다."""
    with pytest.raises(노드.부품_없음):
        await 노드.compose(_상태(scenario=시나리오, trace=["env_history", "compatibility"]))


@pytest.mark.asyncio
async def test_보유_제품_단계가_없으면_경고만_남긴다(caplog):
    결과 = await 노드.compose(_상태(trace=["retrieve", "inventory(stub)", "prefilter"]))
    assert 결과["result"]["items"]
    assert "보유 제품 단계가 아직 없다" in caplog.text


def test_이유_문장은_점수가_높은_두_항목으로_만든다():
    assert 노드.rule_reason(_점수표("p", 80, review=60, budget_fit=90, personalization=70)) == \
        "예산 적합, 내 피부 적합 점수가 높아요"
    assert 노드.rule_reason(_점수표("p", 80, review=60)) == "후기 일치 점수가 높아요"
    assert 노드.rule_reason(_점수표("p", 80)) is None


# 추천 이유 LLM

@pytest.mark.asyncio
async def test_LLM이_쓴_이유_문장을_쓴다(LLM):
    LLM["응답"] = {"p1": "건성 피부에 맞고 원하신 매트한 마무리예요"}
    결과 = (await 노드.compose(_상태()))["result"]
    assert 결과["items"][0]["reason"] == "건성 피부에 맞고 원하신 매트한 마무리예요"
    # 한 번에 부르고, 점수 항목이 없는 카드는 LLM 에 넘기지 않는다
    assert len(LLM["받은"]) == 1
    assert '"p2"' not in LLM["받은"][0]
    assert '"내 피부 적합"' in LLM["받은"][0] and '"매트"' in LLM["받은"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("응답", [
    None, "문장", ["p1"],
    {"p1": ""}, {"p1": 3}, {"p1": "가" * 41}, {"다른": "좋아요"},
])
async def test_이유_문장이_이상하면_규칙_문장으로_채운다(LLM, 응답):
    LLM["응답"] = 응답
    결과 = (await 노드.compose(_상태()))["result"]
    assert 결과["items"][0]["reason"] == "내 피부 적합, 예산 적합 점수가 높아요"


@pytest.mark.asyncio
async def test_LLM_호출이_실패하면_규칙_문장으로_채운다(LLM):
    LLM["예외"] = TimeoutError("느림")
    결과 = (await 노드.compose(_상태()))["result"]
    assert 결과["items"][0]["reason"] == "내 피부 적합, 예산 적합 점수가 높아요"


@pytest.mark.asyncio
async def test_빠진_카드만_규칙_문장으로_채운다(LLM):
    LLM["응답"] = {"p1": "가볍게 잘 맞는 쿠션이에요"}
    결과 = (await 노드.compose(_상태(
        scored=[_점수표("p1", 85, review=80), _점수표("p2", 72, budget_fit=90)],
    )))["result"]
    assert [i["reason"] for i in 결과["items"]] == ["가볍게 잘 맞는 쿠션이에요", "예산 적합 점수가 높아요"]


@pytest.mark.asyncio
async def test_점수_항목이_없으면_LLM을_부르지_않는다(LLM):
    await 노드.compose(_상태(scored=[_점수표("p1", 70)]))
    assert LLM["받은"] == []
