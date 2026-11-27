"""보유 제품을 불러오고 성분을 표준명으로 맞춘다.

READS:  user_id, query_spec
WRITES: inventory

항목 하나는 user_products 한 줄이다. 상품 정보(product_meta 와 같은 모양)에 보유 정보와
성분을 붙인다.

    user_product_id, product_id, name, brand, category, price, image_url, feature_json,
    rating, opened_at, remaining_pct, expiry_date, pao_months, ingredients

    PreFilter     product_id 로 보유 제품을 빼고, ingredients 로 성분 충돌을 본다
    Coverage      category, feature_json 으로 환경에 필요한 기능을 채우는지 본다
    Score         category, price 로 평소 쓰는 가격대를 잡는다
    Alternative   rating, opened_at 으로 바꿀 제품을 고른다

다른 사람 기준(target=OTHER)이면 빈 목록이다. 받을 사람의 보유 제품은 모른다.
요청한 사람 것을 넣으면 PreFilter 가 엉뚱한 제품을 뺀다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 config 를 타고 API 키를
요구해, 키 없는 CI(tests/v2)에서는 이 노드를 불러오지도 못한다.
"""
from __future__ import annotations

import asyncio
import logging

from contracts.query_spec import Target
from graph.state import GraphState

logger = logging.getLogger(__name__)

_보유_칸 = ("rating", "opened_at", "remaining_pct", "expiry_date", "pao_months")


def _owned(user_id: str) -> list[dict]:
    from db.user_product_reader import get_owned_user_products
    return get_owned_user_products(user_id)


async def _metas(product_ids: list[str]) -> dict[str, dict]:
    from services.product_meta import ensure
    return await ensure({}, product_ids)


async def _canonicalize(raw_by_product: dict[str, list[str]]) -> dict[str, list[str]]:
    from services.ingredient_store import canonicalize
    return await canonicalize(raw_by_product)


def build_items(owned: list[dict], metas: dict[str, dict],
                ingredients: dict[str, list[str]]) -> list[dict]:
    """보유 행 + 상품 정보 + 표준 성분 → inventory 항목. 상품이 DB 에 없는 행은 뺀다."""
    항목들 = []
    for 행 in owned:
        pid = 행.get("product_id")
        메타 = metas.get(pid)
        if 메타 is None:
            continue
        항목들.append({
            "user_product_id": 행.get("id"),
            "product_id": pid,
            "name": 메타.get("name"),
            "brand": 메타.get("brand"),
            "category": 메타.get("category"),
            "price": 메타.get("price"),
            "image_url": 메타.get("image_url"),
            "feature_json": 메타.get("feature_json") or {},
            **{칸: 행.get(칸) for 칸 in _보유_칸},
            "ingredients": ingredients.get(pid) or [],
        })
    return 항목들


async def inventory(state: GraphState) -> dict:
    user_id = state.get("user_id")
    if not user_id:
        return {"inventory": []}
    if (state.get("query_spec") or {}).get("target") == Target.OTHER.value:
        return {"inventory": []}

    owned = await asyncio.to_thread(_owned, user_id)
    if not owned:
        return {"inventory": []}

    from services.ingredient_store import raw_ingredients

    ids = list(dict.fromkeys(행["product_id"] for 행 in owned if 행.get("product_id")))
    metas = await _metas(ids)
    성분 = await _canonicalize({pid: raw_ingredients(m.get("feature_json")) for pid, m in metas.items()})

    항목들 = build_items(owned, metas, 성분)
    if len(항목들) < len(owned):
        logger.warning("inventory: 상품 정보가 없는 보유 제품 %d개를 뺐다", len(owned) - len(항목들))
    return {"inventory": 항목들}
