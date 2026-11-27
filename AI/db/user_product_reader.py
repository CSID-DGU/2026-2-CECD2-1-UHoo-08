"""보유 제품 조회. Inventory 노드 전용.

034·035 에서 조회(product_views)와 좋아요(wishlists)가 각자 테이블로 나갔다.
user_products 에는 산 제품 한 통마다 한 줄이 남고, usage_type 은 사용 상태다.

    USING      지금 쓰는 중   ← 보유 제품
    USED       다 썼다
    DISCARDED  버렸다

다 쓰거나 버린 제품을 섞어 읽으면 가지고 있지 않은 제품이 성분 충돌 판정에 끼어든다.
"""
from __future__ import annotations

from typing import Any

from db.supabase_client import get_supabase

OWNED_USAGE = "USING"

_COLUMNS = (
    "id, product_id, usage_type, rating, opened_at, "
    "remaining_pct, expiry_date, pao_months"
)


def get_owned_user_products(user_id: str) -> list[dict[str, Any]]:
    """지금 쓰는 제품만. 연 순서(오래된 것 먼저)로 준다."""
    if not user_id:
        return []

    sb = get_supabase()
    rows = (
        sb.table("user_products")
        .select(_COLUMNS)
        .eq("user_id", user_id)
        .eq("usage_type", OWNED_USAGE)
        .order("created_at")
        .execute()
    ).data or []
    return rows
