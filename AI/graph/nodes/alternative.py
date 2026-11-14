"""상품 평가의 기준 상품과 비슷한 대체 후보를 찾는다.

READS:  scenario, base_product_id, inventory, product_meta, query_spec, conflict_marks
WRITES: alternatives, conflict_marks, product_meta

기준 상품의 특징 벡터와 가까운 같은 카테고리 상품을 찾고, 보유 제품과 견줘 거른다.
거르는 규칙은 PreFilter 와 같다(rules/prefilter.py).
    이미 쓰고 있는 제품, 함께 쓰면 안 되는 성분 조합은 뺀다
    시간대를 나누면 되는 조합은 남기고 conflict_marks 에 더해 배지를 단다

다른 사람 기준이면 거르지 않는다. 받을 사람의 보유 제품은 모른다.
보유 제품 정보가 없으면(보유 제품 노드가 아직 없을 때) 거르지 않고 경고만 남긴다.

점수는 여기서 매기지 않는다. 다음 노드(score_lite)가 매기고 낮은 것을 뺀다.

DB 모듈은 함수 안에서 가져온다.
"""
from __future__ import annotations

import asyncio
import logging

from contracts.query_spec import Target
from graph.nodes.prefilter import conflict_pairs
from graph.state import GraphState
from rules import prefilter as 규칙
from services import product_meta

logger = logging.getLogger(__name__)

# 찾는 수와 거른 뒤 남기는 수
찾을_수 = 15
남길_수 = 10

_상품_평가 = "S1_EVALUATE"


async def _비슷한_상품(기준: str) -> list[dict]:
    from db.vector_search import match_alternatives

    return await asyncio.to_thread(match_alternatives, 기준, 찾을_수, [기준])


async def alternative(state: GraphState) -> dict:
    if state.get("scenario") != _상품_평가:
        return {}
    기준 = state.get("base_product_id")
    if not 기준:
        logger.warning("alternative: 기준 상품이 없다. 대체 후보 없이 넘긴다.")
        return {"alternatives": []}

    찾은 = [m for m in await _비슷한_상품(기준) if m["product_id"] != 기준]
    상품_ids = list(dict.fromkeys(m["product_id"] for m in 찾은))
    메타 = await product_meta.ensure(state.get("product_meta") or {}, 상품_ids)
    # 상품 정보가 없는 상품은 점수도 카드도 만들 수 없다
    후보들 = [
        {"product_id": m["product_id"], "similarity": m.get("similarity")}
        for m in 찾은 if m["product_id"] in 메타
    ]

    표시들: dict[str, list[dict]] = {}
    다른_사람 = (state.get("query_spec") or {}).get("target") == Target.OTHER.value
    보유 = state.get("inventory")
    if 후보들 and not 다른_사람:
        if 보유 is None:
            logger.warning("alternative: 보유 제품 정보가 없다. 거르지 않는다.")
        else:
            ids = [후보["product_id"] for 후보 in 후보들]
            쌍들, 메타 = await conflict_pairs(ids, 보유, 메타)
            결과 = 규칙.apply(
                후보들, 보유, 쌍들, {pid: (메타.get(pid) or {}).get("name") for pid in ids},
            )
            후보들, 표시들 = 결과.candidates, 결과.conflict_marks

    남긴 = 후보들[:남길_수]
    남긴_ids = {후보["product_id"] for 후보 in 남긴}
    return {
        "alternatives": 남긴,
        "conflict_marks": {
            **(state.get("conflict_marks") or {}),
            **{pid: 표시 for pid, 표시 in 표시들.items() if pid in 남긴_ids},
        },
        "product_meta": 메타,
    }
