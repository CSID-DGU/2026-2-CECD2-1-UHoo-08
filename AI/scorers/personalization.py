"""내 피부 적합. 추천 기준이 되는 사람의 프로필과 상품 특징이 맞는 정도.

퍼스널 컬러, 피부 타입, 피부 고민 중 양쪽에 값이 있는 항목만 비교해 맞은 비율을
0~100 으로 바꾼다.

전체 인기 기준이면 개인 프로필을 따지지 않으므로 None 이다. 상품 특징이 없거나
비교할 항목이 하나도 없어도 None 이다.
"""
from __future__ import annotations

from typing import Any

from contracts.query_spec import Target
from contracts.score import ScoreContext
from rules.product_match import profile_checks


def _한_상품(프로필: dict[str, Any], 특징: dict[str, Any] | None) -> float | None:
    맞음 = profile_checks(프로필, 특징)
    if not 맞음:
        return None
    return round(sum(맞음) / len(맞음) * 100, 2)


async def personalization(products: list[dict[str, Any]], ctx: ScoreContext) -> dict[str, float | None]:
    if ctx.query_spec.target is Target.POPULAR:
        return {p["product_id"]: None for p in products}
    return {
        p["product_id"]: _한_상품(ctx.user_profile, p.get("feature_json"))
        for p in products
    }
