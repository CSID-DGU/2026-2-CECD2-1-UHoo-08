"""후기 일치. 질의 문장과 가까운 후기가 얼마나 있는지.

상품마다 질의 벡터와 가장 가까운 후기 몇 개의 유사도 평균을 0~100 으로 바꾼다.
질의 벡터가 없거나 후기가 없는 상품은 None 이다.

상품마다 DB 를 한 번씩 부르므로 동시에 부르는 수를 묶어 둔다. 후보가 30개일 때
한꺼번에 부르면 DB 연결이 모자란다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없이는 이 모듈을
불러오지도 못한다.
"""
from __future__ import annotations

import asyncio
from typing import Any

from contracts.score import ScoreContext

# 상품 하나에서 비교할 후기 수
비교_후기_수 = 10
# 동시에 부르는 DB 조회 수
동시_조회_상한 = 8


async def review(products: list[dict[str, Any]], ctx: ScoreContext) -> dict[str, float | None]:
    if not ctx.intent_vector:
        return {p["product_id"]: None for p in products}

    from db.vector_search import match_reviews

    문 = asyncio.Semaphore(동시_조회_상한)

    async def _한_상품(pid: str) -> float | None:
        async with 문:
            후기들 = await asyncio.to_thread(match_reviews, ctx.intent_vector, pid, 비교_후기_수)
        if not 후기들:
            return None
        평균 = sum(h["similarity"] for h in 후기들) / len(후기들)
        return round(max(0.0, min(1.0, 평균)) * 100, 2)

    아이디 = [p["product_id"] for p in products]
    점수들 = await asyncio.gather(*(_한_상품(pid) for pid in 아이디))
    return dict(zip(아이디, 점수들))
