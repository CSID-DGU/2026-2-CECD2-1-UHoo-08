"""가성비 산식 (value-v1) — 요소 · 결측 · 개인화 · 서비스 범위 · 배지 문구. DB 없이 돈다."""
import pytest

from rules.value_signal import (
    DEFAULT_PREFERENCE,
    DISCOUNT_FULL_AT,
    MIN_PEERS,
    budget_fit,
    discount_rate,
    discount_score,
    group_of,
    group_prices,
    preference,
    relative_price,
)


def p(pid, sale, original=None, category="sun", kind="선크림"):
    return {"product_id": pid, "category": category, "feature_json": {"product_type": kind},
            "lowest_price": sale, "original_price": original}


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


def test_discount_full_at_is_named_constant():
    assert DISCOUNT_FULL_AT == 0.5
    assert discount_score(None) is None


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




def test_out_of_scope_products_are_not_peers():
    cheeks = [p(f"c{i}", 1000 * (i + 1), category="cheek", kind="블러셔") for i in range(6)]
    assert group_prices(cheeks) == {}
