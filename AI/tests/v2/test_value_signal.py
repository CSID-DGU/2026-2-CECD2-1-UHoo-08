"""가성비 scorer — 0~100 변환 · 선호도 읽기 · explain · 기존 채점(services/scoring)과의 연동."""
import pytest

import scorers.value_signal as scorer
from contracts.query_spec import Budget, QuerySpec, RequestType
from contracts.score import ScoreContext
from rules.value_signal import DEFAULT_PREFERENCE, group_prices, value_score


def p(pid, sale, original=None, category="sun", kind="선크림"):
    return {"product_id": pid, "category": category, "feature_json": {"product_type": kind},
            "lowest_price": sale, "original_price": original}


# 멘토링 예시: 예산 3만 원. A 35,000 → 28,000 (20%), B 60,000 → 30,000 (50%)
A = p("A", 28000, 35000)
B = p("B", 30000, 60000)
MASTER = [p("c1", 12000), p("c2", 20000), A, B, p("c3", 45000)]
GROUPS = group_prices(MASTER)


# ── scorer ───────────────────────────────────────────────────────

def _ctx(budget=None) -> ScoreContext:
    return ScoreContext(job_id="j1", user_id="u1",
                        query_spec=QuerySpec(request_type=RequestType.SEARCH, budget=Budget(max=budget)))


@pytest.mark.asyncio
async def test_scorer_returns_0_100_and_none(monkeypatch):
    monkeypatch.setattr(scorer, "_load_master", lambda: MASTER)
    monkeypatch.setattr(scorer, "_load_preference_weight", lambda user_id: None)
    out = await scorer.value_signal([A, B, p("none", None)], _ctx(30000))

    assert out["none"] is None
    # 기록이 없으면 선호도 0.5 로 계산한 값을 0~100 으로
    assert out["A"] == round(value_score(A, GROUPS, 30000, u=DEFAULT_PREFERENCE).score * 100, 2)
    assert all(0 <= out[k] <= 100 for k in ("A", "B"))


@pytest.mark.asyncio
async def test_scorer_uses_preference_weight(monkeypatch):
    monkeypatch.setattr(scorer, "_load_master", lambda: MASTER)
    monkeypatch.setattr(scorer, "_load_preference_weight", lambda user_id: 0.3)   # 선호도 1
    out = await scorer.value_signal([A, B], _ctx(30000))
    assert out["B"] > out["A"]


@pytest.mark.asyncio
async def test_scorer_empty_products_reads_nothing(monkeypatch):
    def boom(*_):
        raise AssertionError("후보가 없으면 DB 를 읽지 않는다")
    monkeypatch.setattr(scorer, "_load_master", boom)
    assert await scorer.value_signal([], _ctx()) == {}


@pytest.mark.asyncio
async def test_explain_reads_no_db(monkeypatch):
    def boom(*_):
        raise AssertionError("explain 은 DB 를 읽지 않는다")
    monkeypatch.setattr(scorer, "_load_master", boom)
    monkeypatch.setattr(scorer, "_load_preference_weight", boom)
    assert await scorer.explain([A, p("x", 28000)], _ctx(30000)) == {"A": "정가보다 20% 저렴해요"}


# ── 기존 채점(services/scoring)과의 연동 ─────────────────────────────

def test_none_value_signal_is_dropped_by_build_score():
    from contracts.score import build_score

    weights = {"budget_fit": 0.5, "value_signal": 0.5}
    with_none = build_score("x", {"budget_fit": 80, "value_signal": None}, weights)
    alone = build_score("x", {"budget_fit": 80}, {"budget_fit": 0.5})
    # None 은 0점이 아니다. 빠지고 남은 항목으로 다시 나눈다 → 감점도 가점도 없다
    assert with_none.total == alone.total == 80
    assert [i.key for i in with_none.breakdown] == ["budget_fit"]


@pytest.mark.asyncio
async def test_value_signal_runs_inside_scoring_when_value_seeking(monkeypatch):
    from services import scoring

    monkeypatch.setattr(scorer, "_load_master", lambda: MASTER)
    monkeypatch.setattr(scorer, "_load_preference_weight", lambda user_id: None)
    ctx = ScoreContext(job_id="j1", user_id="u1", query_spec=QuerySpec(
        request_type=RequestType.SEARCH, budget=Budget(max=30000), value_seeking=True))
    products = [{**A, "price": 28000}, {**B, "price": 30000},
                {**p("eye1", 5000, 10000, category="eye", kind="아이라이너"), "price": 5000}]

    scored = await scoring.score_products(products, ctx, None, lite=True)
    by_id = {s["product_id"]: {i["key"]: i["score"] for i in s["breakdown"]} for s in scored}

    assert "value_signal" in by_id["A"] and "value_signal" in by_id["B"]
    assert "value_signal" not in by_id["eye1"]                 # 범위 밖은 None → 점수표에서 빠진다
