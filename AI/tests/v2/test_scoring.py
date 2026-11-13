"""공통 채점이 지켜야 할 성질.

점수 항목 파일을 넣기만 하면 쓰여야 하고, 데이터가 빈 상품 하나 때문에 추천
전체가 멈추면 안 된다. 반대로 모든 상품이 점수를 못 내면 설정 문제이므로 멈춘다.
"""
import sys
import types
import uuid

import pytest

from contracts.query_spec import QuerySpec, RequestType
from contracts.score import ScoreContext
from services import scoring


def _맥락(**값) -> ScoreContext:
    스펙 = {"request_type": RequestType.SEARCH, **값.pop("spec", {})}
    return ScoreContext(job_id="j1", user_id="u1", query_spec=QuerySpec(**스펙), **값)


def _상품(pid, **값):
    return {"product_id": pid, "category": "base", "price": 10000, "similarity": 0.5, **값}


def _항목(점수표: dict):
    async def 항목(products, ctx):
        return {p["product_id"]: 점수표.get(p["product_id"]) for p in products}
    return 항목


@pytest.fixture
def 항목들(monkeypatch):
    """불러올 점수 항목을 정해 둔다."""
    def 세우기(**항목):
        monkeypatch.setattr(scoring, "load_scorers", lambda *a, **k: 항목)
    return 세우기


# 가짜 LLM 이 마지막으로 받은 호출 옵션
받은_옵션: list[dict] = []


@pytest.fixture
def LLM(monkeypatch):
    """가중치 보정 LLM 을 가짜로 둔다. 부른 횟수를 남긴다."""
    def 세우기(응답=None, 예외=None):
        불린: list[str] = []
        받은_옵션.clear()

        class 가짜:
            async def chat_json(self, system, user, **옵션):
                불린.append(user)
                받은_옵션.append(옵션)
                if 예외:
                    raise 예외
                return 응답

        모듈 = types.SimpleNamespace(LLMRole=types.SimpleNamespace(WEIGHT="weight"),
                                    get_llm=lambda role: 가짜())
        import services
        monkeypatch.setitem(sys.modules, "services.llm", 모듈)
        monkeypatch.setattr(services, "llm", 모듈, raising=False)
        return 불린
    return 세우기


# 불러오기

def test_기본_점수_항목을_모두_불러온다():
    항목 = scoring.load_scorers()
    assert {"budget_fit", "price_value", "review", "personalization",
            "query_fit", "popularity"} <= set(항목)


def test_폴더의_파일을_자동으로_불러온다(tmp_path, monkeypatch):
    패키지 = f"fake_scorers_{uuid.uuid4().hex}"
    폴더 = tmp_path / 패키지
    폴더.mkdir()
    (폴더 / "__init__.py").write_text("")
    (폴더 / "freshness.py").write_text(
        "async def freshness(products, ctx):\n    return {}\n")
    (폴더 / "_helper.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))

    항목 = scoring.load_scorers(폴더, 패키지)
    assert list(항목) == ["freshness"]
    # 한 번 읽은 폴더는 다시 읽지 않는다
    assert scoring.load_scorers(폴더, 패키지) is 항목


def test_같은_이름_함수가_없으면_막는다(tmp_path, monkeypatch):
    패키지 = f"fake_scorers_{uuid.uuid4().hex}"
    폴더 = tmp_path / 패키지
    폴더.mkdir()
    (폴더 / "__init__.py").write_text("")
    (폴더 / "freshness.py").write_text("async def fresh(products, ctx):\n    return {}\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(AttributeError):
        scoring.load_scorers(폴더, 패키지)


# 카테고리 통계

def test_카테고리_중앙값에_보유_제품_가격을_함께_쓴다():
    통계 = scoring.category_stats(
        [_상품("p1", price=10000), _상품("p2", price=30000), _상품("p3", price=None)],
        [{"category": "base", "price": 20000}, {"category": "lip", "price": 0}],
    )
    assert 통계 == {"base": {"median_price": 20000}}


# 채점

@pytest.mark.asyncio
async def test_총점_순으로_같으면_유사도_순으로_줄_세운다(항목들):
    항목들(review=_항목({"p1": 60, "p2": 90, "p3": 90}))
    결과 = await scoring.score_products(
        [_상품("p1"), _상품("p2", similarity=0.2), _상품("p3", similarity=0.9)],
        _맥락(), None, lite=True,
    )
    assert [r["product_id"] for r in 결과] == ["p3", "p2", "p1"]
    assert 결과[0]["total"] == 90
    assert 결과[0]["breakdown"][0]["key"] == "review"


@pytest.mark.asyncio
async def test_점수를_낼_수_없는_상품은_뺀다(항목들):
    # popularity 는 가중치가 0 이라 점수가 있어도 총점을 낼 수 없다
    항목들(review=_항목({"p1": 80}), popularity=_항목({"p2": 70}))
    결과 = await scoring.score_products([_상품("p1"), _상품("p2"), _상품("p3")],
                                       _맥락(), None, lite=True)
    assert [r["product_id"] for r in 결과] == ["p1"]


@pytest.mark.asyncio
async def test_모든_상품이_점수를_못_내면_예외다(항목들):
    항목들(review=_항목({}))
    with pytest.raises(ValueError):
        await scoring.score_products([_상품("p1")], _맥락(), None, lite=True)


@pytest.mark.asyncio
async def test_상품이_없으면_빈_목록이다(항목들):
    항목들(review=_항목({}))
    assert await scoring.score_products([], _맥락(), None, lite=False) == []


@pytest.mark.asyncio
async def test_점수_항목의_예외는_삼키지_않는다(항목들):
    async def 터짐(products, ctx):
        raise RuntimeError("DB 끊김")
    항목들(review=터짐, budget_fit=_항목({"p1": 50}))
    with pytest.raises(RuntimeError):
        await scoring.score_products([_상품("p1")], _맥락(), None, lite=True)


@pytest.mark.asyncio
async def test_점수_항목은_카테고리_통계를_받는다(항목들):
    받은: list = []

    async def 기록(products, ctx):
        받은.append(ctx.category_stats)
        return {p["product_id"]: 50 for p in products}
    항목들(budget_fit=기록)
    await scoring.score_products([_상품("p1", price=10000)],
                                 _맥락(inventory=[{"category": "base", "price": 30000}]),
                                 None, lite=True)
    assert 받은 == [{"base": {"median_price": 20000}}]


@pytest.mark.asyncio
async def test_선호_가중치로_비중을_정한다(항목들):
    항목들(review=_항목({"p1": 100}), budget_fit=_항목({"p1": 0}))
    결과 = await scoring.score_products(
        [_상품("p1")], _맥락(), {"review": 0.75, "budget_fit": 0.25}, lite=True,
    )
    assert 결과[0]["total"] == 75


@pytest.mark.asyncio
async def test_lite면_LLM을_부르지_않는다(항목들, LLM):
    불린 = LLM({"review": 2.0})
    항목들(review=_항목({"p1": 80}))
    await scoring.score_products([_상품("p1")], _맥락(), None, lite=True)
    assert 불린 == []


@pytest.mark.asyncio
async def test_full이면_LLM_배수를_곱한다(항목들, LLM):
    불린 = LLM({"review": 2.0, "budget_fit": 0.5})
    항목들(review=_항목({"p1": 100}), budget_fit=_항목({"p1": 0}))
    결과 = await scoring.score_products(
        [_상품("p1")], _맥락(), {"review": 0.25, "budget_fit": 0.25}, lite=False,
    )
    assert len(불린) == 1
    # 0.5 : 0.125 → review 비중 0.8
    assert 결과[0]["total"] == 80


@pytest.mark.asyncio
async def test_LLM_응답을_정해진_시간만_기다린다(항목들, LLM):
    """SDK 기본값(10분)에 맡기면 보정 단계가 추천 전체를 붙잡는다."""
    LLM({"review": 1.0})
    항목들(review=_항목({"p1": 100}))
    await scoring.score_products([_상품("p1")], _맥락(), {"review": 1.0}, lite=False)
    assert 받은_옵션 == [{"timeout": scoring.LLM_TIMEOUT_S}]


@pytest.mark.asyncio
async def test_LLM이_실패하면_보정_없이_진행한다(항목들, LLM):
    LLM(예외=TimeoutError("느림"))
    항목들(review=_항목({"p1": 100}), budget_fit=_항목({"p1": 0}))
    결과 = await scoring.score_products(
        [_상품("p1")], _맥락(), {"review": 0.25, "budget_fit": 0.25}, lite=False,
    )
    assert 결과[0]["total"] == 50


@pytest.mark.asyncio
async def test_실제_점수_항목으로_끝까지_채점한다():
    """질의 벡터가 없으면 후기 항목은 DB 를 부르지 않고 빠진다."""
    상품들 = [
        _상품("싼", price=8000, lowest_price=8000, original_price=16000,
              feature_json={"skin_type": "건성"}),
        _상품("비싼", price=40000, lowest_price=40000, original_price=40000,
              feature_json={"skin_type": "지성"}),
    ]
    결과 = await scoring.score_products(
        상품들, _맥락(user_profile={"skin_type": "DRY"}), None, lite=True,
    )
    assert [r["product_id"] for r in 결과] == ["싼", "비싼"]
    assert {i["key"] for i in 결과[0]["breakdown"]} == {"budget_fit", "price_value", "personalization"}
