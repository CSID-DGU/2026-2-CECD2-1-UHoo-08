"""상품 평가의 기준 상품, 또는 홈 루틴에서 바꿀 보유 제품과 비슷한 대체 후보를 찾는다.

READS:  scenario, base_product_id, inventory, product_meta, query_spec, conflict_marks,
        routine_check
WRITES: alternatives, conflict_marks, product_meta, replace_target, candidates

    상품 평가   아래와 같다. 찾은 후보를 alternatives 에 쓴다
    홈 루틴     함께 쓰지 않는 게 좋은 조합(AVOID)에 가장 많이 나온 보유 제품을 바꿀 제품으로
                고르고, 그 제품과 비슷한 상품을 보유 상품을 모두 빼고 찾아 candidates 에 쓴다.
                남은 보유 제품과의 충돌은 다음 PreFilter 가 본다(바꿀 제품은 판정에서 빠진다)

바꿀 제품은 AVOID 쌍에 나온 횟수가 많은 것이다. 같으면 별점이 낮은 것(별점이 없으면 3점),
먼저 연 것, user_product_id 순으로 고른다. AVOID 쌍이 없으면 바꿀 제품도 후보도 없다.

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
# 홈 루틴에서 바꿀 제품 하나에 찾는 대체 후보 수
루틴_찾을_수 = 20
# 별점이 없는 보유 제품의 별점
별점_없음 = 3
별점_문구 = "별점이 낮은 쪽을 바꾸는 걸 먼저 권해요"
횟수_문구 = "함께 쓰지 않는 게 좋은 조합이 {n}개라 이 제품을 바꾸는 걸 권해요"

_상품_평가 = "S1_EVALUATE"
_홈_루틴 = "HOME_ROUTINE"
_함께_쓰지_않음 = "AVOID"


async def _비슷한_상품(기준: str) -> list[dict]:
    from db.vector_search import match_alternatives

    return await asyncio.to_thread(match_alternatives, 기준, 찾을_수, [기준])


def pick_replace_target(pairs: list[dict], inventory: list[dict]) -> dict | None:
    """AVOID 쌍을 보고 바꿀 보유 제품 하나를 고른다. AVOID 쌍이 없으면 None."""
    횟수: dict[str, int] = {}
    이름: dict[str, str] = {}
    for 쌍 in pairs:
        if 쌍.get("level") != _함께_쓰지_않음:
            continue
        for 쪽 in (쌍["a"], 쌍["b"]):
            횟수[쪽["user_product_id"]] = 횟수.get(쪽["user_product_id"], 0) + 1
            이름.setdefault(쪽["user_product_id"], 쪽.get("name") or "")
    if not 횟수:
        return None

    보유 = {항목.get("user_product_id"): 항목 for 항목 in inventory}

    def 별점(upid: str) -> int:
        값 = (보유.get(upid) or {}).get("rating")
        return 별점_없음 if 값 is None else 값

    def 연_날(upid: str) -> str:
        # 연 날을 모르면 가장 늦게 연 것으로 본다
        return (보유.get(upid) or {}).get("opened_at") or "9999-12-31"

    순서 = sorted(횟수, key=lambda upid: (-횟수[upid], 별점(upid), 연_날(upid), upid))
    고른 = 순서[0]
    같은_횟수 = [upid for upid in 순서 if 횟수[upid] == 횟수[고른]]
    별점으로_갈림 = len(같은_횟수) > 1 and 별점(같은_횟수[1]) != 별점(고른)
    return {
        "user_product_id": 고른,
        "product_id": (보유.get(고른) or {}).get("product_id"),
        "name": (보유.get(고른) or {}).get("name") or 이름[고른],
        "reason": 별점_문구 if 별점으로_갈림 else 횟수_문구.format(n=횟수[고른]),
    }


async def _루틴(state: GraphState) -> dict:
    보유 = state.get("inventory") or []
    바꿀 = pick_replace_target((state.get("routine_check") or {}).get("pairs") or [], 보유)
    if 바꿀 is None:
        return {"replace_target": None, "candidates": []}
    if not 바꿀["product_id"]:
        logger.warning("alternative: 바꿀 제품 %s 의 상품 id 를 보유 제품에서 찾지 못했다. "
                       "대체 후보 없이 넘긴다.", 바꿀["user_product_id"])
        return {"replace_target": 바꿀, "candidates": []}

    from db.vector_search import match_alternatives

    보유_상품 = list(dict.fromkeys(항목["product_id"] for 항목 in 보유 if 항목.get("product_id")))
    찾은 = await asyncio.to_thread(
        match_alternatives, 바꿀["product_id"], 루틴_찾을_수, 보유_상품,
    )
    찾은 = [m for m in 찾은 if m["product_id"] not in 보유_상품]
    메타 = await product_meta.ensure(
        state.get("product_meta") or {}, list(dict.fromkeys(m["product_id"] for m in 찾은)),
    )
    return {
        "replace_target": 바꿀,
        "candidates": [
            {"product_id": m["product_id"], "source": "replace", "similarity": m.get("similarity")}
            for m in 찾은 if m["product_id"] in 메타
        ],
        "product_meta": 메타,
    }


async def alternative(state: GraphState) -> dict:
    if state.get("scenario") == _홈_루틴:
        return await _루틴(state)
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
