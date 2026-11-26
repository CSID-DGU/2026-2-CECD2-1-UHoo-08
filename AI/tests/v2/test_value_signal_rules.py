"""가성비 산식 (value-v1) — 요소 · 결측 · 개인화 · 서비스 범위 · 배지 문구. DB 없이 돈다."""
import pytest

from rules.value_signal import DISCOUNT_FULL_AT, budget_fit, discount_rate, discount_score


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
