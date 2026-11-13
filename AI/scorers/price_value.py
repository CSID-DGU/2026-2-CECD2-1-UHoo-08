"""할인율. 정가보다 얼마나 싸게 살 수 있는지.

할인 0% 는 50점, 50% 이상은 100점, 사이는 선형이다. 최저가나 정가가 없으면 None 이다.
"""
from __future__ import annotations

from typing import Any

from contracts.score import ScoreContext
from rules.product_match import discount_score


async def price_value(products: list[dict[str, Any]], ctx: ScoreContext) -> dict[str, float | None]:
    return {
        p["product_id"]: discount_score(p.get("lowest_price"), p.get("original_price"))
        for p in products
    }
