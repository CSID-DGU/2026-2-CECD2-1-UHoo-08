"""보유 제품 조회. Inventory 노드 전용.

`user_products`에는 보유 제품만 있는 게 아니다 — 조회 이력(VIEWED), 위시리스트
(INTERESTED)도 같은 테이블에 있다. 지금 보유한 것은 USING·ONBOARDING 뿐이다
(db/migrations/018_user_products_extend.sql). 다른 usage_type 을 섞어 읽으면
가지고 있지 않은 제품이 성분 충돌 판정에 끼어든다.
"""
from __future__ import annotations

from typing import Any

from db.supabase_client import get_supabase

OWNED_USAGE = ("USING", "ONBOARDING")

_COLUMNS = (
    "id, product_id, usage_type, opened_at, "
    "remaining_pct, expiry_date, pao_months"
)


def get_owned_user_products(user_id: str) -> list[dict[str, Any]]:
    """지금 보유 중인 제품만. 조회 이력·위시리스트는 빠진다."""
    if not user_id:
        return []

    sb = get_supabase()
    rows = (
        sb.table("user_products")
        .select(_COLUMNS)
        .eq("user_id", user_id)
        .in_("usage_type", list(OWNED_USAGE))
        .execute()
    ).data or []
    return rows
