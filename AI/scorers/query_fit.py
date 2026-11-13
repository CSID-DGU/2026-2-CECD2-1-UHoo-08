"""조건 일치. 질의에서 읽은 특징(제형, 커버력 등)과 상품 특징이 맞는 정도.

질의에 특징 조건이 없으면 따질 것이 없으므로 None 이다.
"""
from __future__ import annotations

from typing import Any

from contracts.score import ScoreContext
from rules.product_match import feature_match_ratio


async def query_fit(products: list[dict[str, Any]], ctx: ScoreContext) -> dict[str, float | None]:
    조건 = ctx.query_spec.features
    if not 조건:
        return {p["product_id"]: None for p in products}
    return {
        p["product_id"]: round(feature_match_ratio(조건, p.get("feature_json") or {}) * 100, 2)
        for p in products
    }
