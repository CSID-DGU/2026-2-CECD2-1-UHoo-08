"""가성비 산식 (value-v1) — 요소 · 결측 · 개인화 · 서비스 범위 · 배지 문구. DB 없이 돈다."""
import pytest

from rules.value_signal import (
    ALPHA_BASE,
    ALPHA_RANGE,
    DEFAULT_PREFERENCE,
    DISCOUNT_FULL_AT,
    MIN_PEERS,
    budget_fit,
    discount_rate,
    discount_score,
    explain_text,
    group_of,
    group_prices,
    preference,
    relative_price,
    value_score,
)


def p(pid, sale, original=None, category="sun", kind="선크림"):
    return {"product_id": pid, "category": category, "feature_json": {"product_type": kind},
            "lowest_price": sale, "original_price": original}


# 멘토링 예시: 예산 3만 원. A 35,000 → 28,000 (20%), B 60,000 → 30,000 (50%)
A = p("A", 28000, 35000)
B = p("B", 30000, 60000)
MASTER = [p("c1", 12000), p("c2", 20000), A, B, p("c3", 45000)]
GROUPS = group_prices(MASTER)


# ── 요소 ──────────────────────────────────────────────────────────

def test_budget_fit_separates_products_within_budget():
    assert budget_fit(10000, 30000) == pytest.approx(2 / 3)
    assert budget_fit(30000, 30000) == 0.0
    assert budget_fit(20000, None) is None


def test_discount_rate():
    assert discount_rate(28000, 35000) == pytest.approx(0.2)
    assert discount_rate(25000, 25000) == 0.0
    assert discount_rate(30000, 25000) == 0.0        # 판매가 > 정가
    assert discount_rate(25000, None) is None        # 정가 없음은 할인 0 이 아니다
    assert discount_rate(25000, 0) is None


@pytest.mark.parametrize("sale, original, rate, score", [
    (20000, 20000, 0.0, 0.0),      # 할인 0%
    (15000, 20000, 0.25, 0.5),     # 25%
    (10000, 20000, 0.5, 1.0),      # 50% → 만점
    (6000, 20000, 0.7, 1.0),       # 50% 초과도 만점
])
def test_discount_score_is_normalized_at_50_percent(sale, original, rate, score):
    assert discount_rate(sale, original) == rate
    assert discount_score(rate) == score
    b = value_score(p("x", sale, original), GROUPS, None)
    assert (b.discount_rate, b.discount_score) == (rate, score)


def test_discount_full_at_is_named_constant():
    assert DISCOUNT_FULL_AT == 0.5
    assert discount_score(None) is None


def test_missing_original_has_no_discount_rate_or_score():
    b = value_score(p("x", 12000), GROUPS, None)
    assert (b.discount_rate, b.discount_score) == (None, None)


def test_relative_price_is_rank_within_group_with_average_ties():
    peers = {"a": 10, "b": 20, "c": 20, "d": 30, "e": 40}
    assert relative_price("e", 40, peers) == (0.0, 5)
    assert relative_price("a", 10, peers)[0] == 1.0
    assert relative_price("b", 20, peers)[0] == pytest.approx(1 - (2.5 - 1) / 4)   # 20 · 20 은 평균 순위 2.5
    assert relative_price("new", 50, peers) == (0.0, 6)                             # 마스터에 없으면 넣어서 센다


def test_relative_price_needs_min_peers():
    peers = {f"x{i}": 1000 * i for i in range(MIN_PEERS - 2)}
    assert relative_price("me", 500, peers) == (None, MIN_PEERS - 1)


def test_groups_are_category_and_product_type():
    assert group_of(p("x", 1, kind="선크림")) == ("sun", "선크림")
    assert group_of({"product_id": "x", "category": "sun", "feature_json": {}}) is None
    assert set(group_prices([p("x", 1000), p("y", None), p("z", 1000, category="lip", kind="틴트")])) == {
        ("sun", "선크림"), ("lip", "틴트")}


def test_preference_from_weight():
    assert preference(None) == DEFAULT_PREFERENCE
    assert preference(0) == DEFAULT_PREFERENCE
    assert preference(0.15) == pytest.approx(0.75)
    assert preference(0.3) == 1.0 and preference(0.9) == 1.0
    assert preference("높음") == DEFAULT_PREFERENCE


# ── 산식 · 시나리오 ────────────────────────────────────────────────

def test_mentor_example_flips_with_preference():
    price_first = (value_score(A, GROUPS, 30000, u=0.0).score, value_score(B, GROUPS, 30000, u=0.0).score)
    value_first = (value_score(A, GROUPS, 30000, u=1.0).score, value_score(B, GROUPS, 30000, u=1.0).score)
    assert price_first[0] > price_first[1]           # 가격 우선 사용자 → A
    assert value_first[1] > value_first[0]           # 가성비 중시 사용자 → B


def test_breakdown_values_for_mentor_example():
    b = value_score(A, GROUPS, 30000, u=0.0)
    assert b.budget_fit == pytest.approx(1 - 28000 / 30000, abs=1e-4)
    assert b.relative_price == 0.5
    assert (b.discount_rate, b.discount_score) == (0.2, 0.4)    # 실제 할인율과 정규화 점수를 따로 낸다
    assert b.weights == {"current_price": 1 - ALPHA_BASE, "discount": ALPHA_BASE}
    price = 0.7 * (1 - 28000 / 30000) + 0.3 * 0.5
    assert b.score == pytest.approx((1 - ALPHA_BASE) * price + ALPHA_BASE * 0.4, abs=1e-4)
    assert "WITHIN_BUDGET" in b.reason_codes and "HIGH_DISCOUNT" in b.reason_codes


def test_alpha_is_final_plan_b():
    assert (ALPHA_BASE, ALPHA_RANGE) == (0.05, 0.35)
    assert value_score(A, GROUPS, 30000, u=1.0).weights == {"current_price": 0.6, "discount": 0.4}
    assert value_score(A, GROUPS, 30000, u=DEFAULT_PREFERENCE).weights == {"current_price": 0.775, "discount": 0.225}


def test_mentor_flip_point_is_between_0_3_and_0_4():
    # 실데이터 실험에서 B안의 역전 시점은 0.34 였다. 기본 사용자(0.5)는 할인 폭이 큰 B 쪽
    assert value_score(A, GROUPS, 30000, u=0.3).score > value_score(B, GROUPS, 30000, u=0.3).score
    assert value_score(B, GROUPS, 30000, u=0.4).score > value_score(A, GROUPS, 30000, u=0.4).score


def test_same_discount_cheaper_wins():
    x, y = p("x", 10000, 20000), p("y", 15000, 30000)
    g = group_prices([x, y, *MASTER])
    assert value_score(x, g, 30000).score > value_score(y, g, 30000).score


def test_same_price_higher_discount_wins():
    x, y = p("x", 20000, 25000), p("y", 20000, 40000)
    g = group_prices([x, y, *MASTER])
    assert value_score(y, g, 30000).score > value_score(x, g, 30000).score


def test_no_budget_uses_relative_price_only():
    b = value_score(A, GROUPS, None, u=0.0)
    assert b.budget_fit is None and b.price_score == 0.5


def test_missing_original_price_uses_price_only():
    item = p("x", 12000)
    b = value_score(item, GROUPS, 30000)
    assert b.discount_rate is None and "NO_ORIGINAL_PRICE" in b.reason_codes
    assert b.score == b.price_score


def test_missing_sale_price_has_no_score():
    assert value_score(p("x", None, 30000), GROUPS, 30000).score is None


def test_small_group_skips_relative_price():
    item = p("x", 9000, 10000, category="lip", kind="립라이너")
    b = value_score(item, GROUPS, 30000)
    assert b.relative_price is None and "SMALL_GROUP" in b.reason_codes
    assert b.price_score == b.budget_fit


def test_nothing_to_score_is_none():
    item = {"product_id": "x", "category": "sun", "feature_json": {}, "lowest_price": 9000}
    assert value_score(item, GROUPS, None).score is None


# ── 결측: 현재 가격 점수가 없으면 할인율이 있어도 None ──────────────────

def test_discount_alone_does_not_make_a_score():
    item = p("x", 5000, 10000, category="skincare", kind="앰플")      # 50% 할인 · 제품군 1개 · 예산 없음
    b = value_score(item, group_prices([item]), None)
    assert b.discount_rate == 0.5 and b.price_score is None
    assert b.score is None and "NO_PRICE_BASIS" in b.reason_codes


def test_unknown_type_with_discount_and_no_budget_is_none():
    item = {"product_id": "x", "category": "sun", "feature_json": {}, "lowest_price": 5000, "original_price": 10000}
    assert value_score(item, GROUPS, None).score is None


def test_budget_alone_is_enough_price_basis():
    item = p("x", 5000, 10000, category="skincare", kind="앰플")
    b = value_score(item, group_prices([item]), 30000)
    assert b.relative_price is None and b.price_score == b.budget_fit
    assert b.score is not None


def test_relative_price_alone_is_enough_price_basis():
    b = value_score(A, GROUPS, None)
    assert b.budget_fit is None and b.price_score == b.relative_price and b.score is not None


def test_no_discount_with_price_basis_uses_price_only():
    item = p("x", 12000)                                               # 정가 없음
    assert value_score(item, GROUPS, 30000).score == value_score(item, GROUPS, 30000).price_score


# ── 서비스 범위 ──────────────────────────────────────────────────

@pytest.mark.parametrize("category, kind", [("eye", "아이라이너"), ("cheek", "블러셔"), (None, "선크림")])
def test_out_of_scope_category_is_not_scored(category, kind):
    item = p("x", 5000, 10000, category=category, kind=kind)
    b = value_score(item, GROUPS, 30000)
    assert b.score is None and b.reason_codes == ["OUT_OF_SCOPE"]
    assert explain_text(item, 30000) is None


def test_out_of_scope_products_are_not_peers():
    cheeks = [p(f"c{i}", 1000 * (i + 1), category="cheek", kind="블러셔") for i in range(6)]
    assert group_prices(cheeks) == {}


def test_other_category_is_compared_within_its_own_group():
    lips = [p(f"l{i}", 5000 + 1000 * i, category="lip", kind="틴트") for i in range(5)]
    g = group_prices([*MASTER, *lips])
    # 립 중 가장 비싼 9,000원은 선크림보다 싸도 립 안에서는 0점
    assert value_score(lips[-1], g, None).relative_price == 0.0
    assert value_score(p("c1", 12000), g, None).relative_price == 1.0


def test_relative_price_does_not_depend_on_candidates():
    # 같은 마스터면 후보 목록과 상관없이 같은 값
    assert value_score(A, GROUPS, None).relative_price == value_score(A, group_prices(MASTER), None).relative_price


def test_over_budget_is_flagged_not_rewarded():
    b = value_score(p("x", 35000, 70000), GROUPS, 30000)
    assert b.budget_fit == 0.0 and "OVER_BUDGET" in b.reason_codes


# ── 배지 문구 ─────────────────────────────────────────────────────

def test_explain_text():
    assert explain_text(A, None) == "정가보다 20% 저렴해요"     # 정규화 점수(40)가 아니라 실제 할인율
    assert explain_text(p("x", 6000, 20000), None) == "정가보다 70% 저렴해요"
    assert explain_text(p("x", 12000), 30000) == "예산보다 60% 저렴해요"
    assert explain_text(p("x", 28000), 30000) is None
    assert explain_text({"product_id": "x", "price": 20000}, None) is None
