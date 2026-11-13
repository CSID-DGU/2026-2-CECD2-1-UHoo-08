"""인기. 전체 인기 기준일 때 평점과 후기 수로 매기는 점수.

후기가 몇 개뿐인 5점 상품이 후기 수천 개인 4.7점 상품을 이기지 않도록
베이지안 평균을 쓴다. 후기 수가 적을수록 이번 후보들의 평균 평점 쪽으로 당긴다.
평점 1~5 를 0~100 으로 바꾼다.

전체 인기 기준이 아니면 None 이다. 평점이 없는 상품도 None 이다.
"""
from __future__ import annotations

from typing import Any

from contracts.query_spec import Target
from contracts.score import ScoreContext

# 평균 쪽으로 당기는 힘. 후기가 이만큼 있으면 자기 평점과 평균이 반반이다.
기준_후기_수 = 20
평점_최저, 평점_최고 = 1.0, 5.0


async def popularity(products: list[dict[str, Any]], ctx: ScoreContext) -> dict[str, float | None]:
    if ctx.query_spec.target is not Target.POPULAR:
        return {p["product_id"]: None for p in products}

    평점들 = [p["average_score"] for p in products if p.get("average_score") is not None]
    if not 평점들:
        return {p["product_id"]: None for p in products}
    전체_평균 = sum(평점들) / len(평점들)

    결과: dict[str, float | None] = {}
    for p in products:
        평점 = p.get("average_score")
        if 평점 is None:
            결과[p["product_id"]] = None
            continue
        후기_수 = max(p.get("review_count") or 0, 0)
        보정 = (후기_수 * 평점 + 기준_후기_수 * 전체_평균) / (후기_수 + 기준_후기_수)
        비율 = (보정 - 평점_최저) / (평점_최고 - 평점_최저)
        결과[p["product_id"]] = round(max(0.0, min(1.0, 비율)) * 100, 2)
    return 결과
