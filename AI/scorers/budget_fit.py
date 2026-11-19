"""예산 적합. 가격이 원하는 예산에 얼마나 들어오는지.

제품 하나의 상한(budget.max)이 있으면 그 상한과 비교한다. 없으면 같은
카테고리 가격의 중앙값과 비교한다. 예산을 말하지 않았어도 너무 비싼 제품은
덜 맞는다고 본다.

가격이 없거나, 예산이 없는데 카테고리 중앙값도 없으면 None 이다.
"""
from __future__ import annotations

from typing import Any

from contracts.score import ScoreContext

# 상한의 이 배수 이상이면 0점
상한_초과_끝 = 1.5
# 중앙값 대비 비율. 이하면 100점, 이상이면 바닥 점수
중앙값_싼_끝 = 0.7
중앙값_비싼_끝 = 1.5
중앙값_바닥_점수 = 20


def _선형(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """x0 에서 y0, x1 에서 y1 인 직선. 범위 밖은 끝값으로 자른다."""
    if x <= x0:
        return y0
    if x >= x1:
        return y1
    return y0 + (x - x0) / (x1 - x0) * (y1 - y0)


def _한_상품(가격: float | None, 상한: int | None, 중앙값: float | None) -> float | None:
    if 가격 is None:
        return None
    if 상한:
        return round(_선형(가격, 상한, 상한 * 상한_초과_끝, 100, 0), 2)
    if not 중앙값:
        return None
    return round(_선형(가격 / 중앙값, 중앙값_싼_끝, 중앙값_비싼_끝, 100, 중앙값_바닥_점수), 2)


async def budget_fit(products: list[dict[str, Any]], ctx: ScoreContext) -> dict[str, float | None]:
    상한 = ctx.query_spec.budget.max
    return {
        p["product_id"]: _한_상품(
            p.get("price"),
            상한,
            (ctx.category_stats.get(p.get("category")) or {}).get("median_price"),
        )
        for p in products
    }
