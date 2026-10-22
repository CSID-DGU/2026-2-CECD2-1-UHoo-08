"""보유 제품을 불러오고 성분을 표준명으로 정규화한다.

READS:  user_id
WRITES: inventory

`user_products`는 조회 이력(VIEWED)·위시리스트(INTERESTED)까지 한 테이블에
있다. 지금 보유한 것은 USING·ONBOARDING 뿐이라 그 둘만 읽는다
(db/migrations/018_user_products_extend.sql).

성분은 `products.feature_json.key_ingredient`에 원문 그대로 들어 있다
("나이아신아마이드" / "니아신아마이드" / "Niacinamide"가 전부 다른 문자열).
`rules/ingredient_normalize.py`로 표준명으로 묶어 돌려준다. 여기서 정규화해
두지 않으면 PreFilter·Compatibility가 매번 같은 변환을 반복해야 하고, 한쪽만
고치면 둘이 어긋난다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 config 를 타고 API 키를
요구해, 키 없는 CI(tests/v2)에서는 이 노드를 불러오지도 못한다.
"""
from __future__ import annotations

from graph.state import GraphState
from rules.ingredient_normalize import normalize_key, resolve_canonical


def _fetch_owned(user_id: str) -> list[dict]:
    from db.user_product_reader import get_owned_user_products
    return get_owned_user_products(user_id)


def _fetch_product_metas(product_ids: list[str]) -> dict:
    from db.product_reader import get_products_meta
    return get_products_meta(product_ids)


def _fetch_product_features(product_ids: list[str]) -> dict:
    from db.product_reader import get_product_features
    return get_product_features(product_ids)


def _fetch_alias_map(keys: list[str]) -> dict[str, str]:
    from db.ingredient_alias_reader import get_alias_map
    return get_alias_map(keys)


async def inventory(state: GraphState) -> dict:
    user_id = state.get("user_id")
    if not user_id:
        return {"inventory": []}

    owned = _fetch_owned(user_id)
    if not owned:
        return {"inventory": []}

    product_ids = sorted({row["product_id"] for row in owned if row.get("product_id")})
    metas = _fetch_product_metas(product_ids)
    features = _fetch_product_features(product_ids)

    # 별칭 조회는 한 번에 한다. 보유 제품 수만큼 DB를 부르면 보유 제품이
    # 많은 사용자일수록 이 노드가 느려진다.
    raw_by_product: dict[str, list[str]] = {
        pid: list((features.get(pid) or {}).get("key_ingredient") or [])
        for pid in product_ids
    }
    all_keys = sorted({
        normalize_key(name)
        for names in raw_by_product.values()
        for name in names
        if name
    })
    alias_map = _fetch_alias_map(all_keys)

    result = []
    for row in owned:
        pid = row.get("product_id")
        meta = metas.get(pid, {})
        result.append({
            "user_product_id": row.get("id"),
            "product_id": pid,
            "name": meta.get("name"),
            "brand": meta.get("brand"),
            "category": meta.get("category"),
            "usage_type": row.get("usage_type"),
            "opened_at": row.get("opened_at"),
            "remaining_pct": row.get("remaining_pct"),
            "expiry_date": row.get("expiry_date"),
            "pao_months": row.get("pao_months"),
            "ingredients": resolve_canonical(raw_by_product.get(pid, []), alias_map),
        })

    return {"inventory": result}
