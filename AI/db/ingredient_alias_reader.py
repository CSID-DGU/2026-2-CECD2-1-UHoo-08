"""성분 별칭 사전 조회. `rules/ingredient_normalize.py`와 짝을 이룬다.

`ingredient_alias.alias` 는 `normalize_key()`와 같은 규칙(소문자, 공백·하이픈·
가운뎃점 제거)으로 저장된 조회 키다(db/migrations/026_ingredient_rules.sql).
"""
from __future__ import annotations

from typing import Any

from db.supabase_client import get_supabase


def get_alias_map(keys: list[str]) -> dict[str, str]:
    """정규화된 키 목록 → {key: canonical}. 사전에 없는 키는 결과에서 빠진다."""
    if not keys:
        return {}

    sb = get_supabase()
    rows: list[dict[str, Any]] = (
        sb.table("ingredient_alias")
        .select("alias, canonical")
        .in_("alias", keys)
        .execute()
    ).data or []
    return {row["alias"]: row["canonical"] for row in rows}
