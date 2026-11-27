"""피부 조건이 비슷한 사용자가 실제로 쓰고 만족한 제품을 찾는다.

READS:  user_id, user_profile, query_spec, scored, alternatives, inventory, base_product_id, product_meta
WRITES: collaborative, product_meta

찾는 방법은 예전 협업 추천(agents/collaborative_agent)을 그대로 쓴다. 여기서는
그래프 상태에서 조건을 꺼내고, 이미 화면에 나오는 상품을 빼는 일만 한다.

    빼는 것   이번 결과 상위, 대체 후보, 기준 상품, 보유 제품. 같은 화면에 두 번 나오거나
              이미 가진 제품을 권하지 않게 한다
    기준      본인 기준은 내 피부 조건으로, 다른 사람 기준은 받을 사람의 조건으로 찾는다.
              전체 인기 기준은 비운다. 전체 인기 탭과 같은 것을 보여 주게 된다

질의에 카테고리가 있으면 같은 카테고리만 남긴다. "쿠션 추천" 에 비슷한 사람이 쓰는
크림이 나오면 엉뚱해 보인다. 거르고 나면 모자랄 수 있어 넉넉히 받아 거른다.

협업 추천 모듈은 DB 모듈을 최상단에서 불러온다. 함수 안에서 가져온다.
"""
from __future__ import annotations

import logging

from contracts.query_spec import Target
from graph.state import GraphState
from services import product_meta

logger = logging.getLogger(__name__)

# 보여 줄 수
보여_줄_수 = 5
# 카테고리로 거를 때 넉넉히 받는 배수
카테고리_여유_배수 = 4
# 빼는 이번 결과 상위 수. 결과 카드에 보이는 수와 같다
결과_상위_수 = 10


def _뺄_상품(state: GraphState) -> list[str]:
    뺄 = [s["product_id"] for s in (state.get("scored") or [])[:결과_상위_수]]
    뺄 += [a["product_id"] for a in state.get("alternatives") or []]
    뺄 += [i["product_id"] for i in state.get("inventory") or [] if i.get("product_id")]
    if state.get("base_product_id"):
        뺄.append(state["base_product_id"])
    return list(dict.fromkeys(뺄))


async def collaborative(state: GraphState) -> dict:
    spec = state.get("query_spec") or {}
    if spec.get("target") == Target.POPULAR.value:
        return {"collaborative": []}
    if not state.get("user_id"):
        logger.warning("collaborative: 사용자가 없다. 비운다.")
        return {"collaborative": []}

    from agents.collaborative_agent import run_collaborative

    프로필 = state.get("user_profile") or {}
    카테고리 = spec.get("category")
    받을_수 = 보여_줄_수 * 카테고리_여유_배수 if 카테고리 else 보여_줄_수

    찾은 = await run_collaborative(
        state["user_id"],
        프로필.get("skin_type"),
        프로필.get("personal_color"),
        exclude_ids=_뺄_상품(state),
        top_k=받을_수,
    )
    if not 찾은:
        return {"collaborative": []}

    메타 = await product_meta.ensure(state.get("product_meta") or {}, [p.id for p in 찾은])
    결과 = [
        {"product_id": p.id, "satisfaction_percent": p.satisfaction_percent}
        for p in 찾은
        if not 카테고리 or (메타.get(p.id) or {}).get("category") == 카테고리
    ][:보여_줄_수]
    if 카테고리 and len(결과) < 보여_줄_수:
        logger.info("collaborative: %s 카테고리 상품이 %d개뿐이다.", 카테고리, len(결과))
    return {"collaborative": 결과, "product_meta": 메타}
