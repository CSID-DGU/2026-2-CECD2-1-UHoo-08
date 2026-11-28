"""상품 성분(표준명)과 성분 충돌 규칙을 읽는다.

PreFilter, Retrieve(제외 성분), Inventory, 루틴 점검이 모두 이 모듈로 성분을 읽는다.
읽는 곳마다 정규화를 따로 하면 한쪽만 고쳤을 때 판정이 어긋난다.

    성분 원문     products.feature_json.key_ingredient
    표준명        ingredient_alias (rules/ingredient_normalize.py 의 키 규칙)
    충돌 규칙     ingredient_conflict_rules (성분 쌍 → AVOID | SEPARATE)

사전에 없는 성분은 원문 그대로 쓴다. 모르는 성분을 빼면 "이 성분은 없다"로 잘못 읽힌다.

규칙은 몇십 줄이고 거의 안 바뀐다. 요청마다 읽지 않고 10분 동안 들고 있는다.

DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키 없는 CI 에서 이 모듈을
불러오지도 못한다.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Iterable

from rules.ingredient_normalize import normalize_key, resolve_canonical

RULES_TTL_S = 600.0
_rules_cache: tuple[float, list[dict]] | None = None


def raw_ingredients(feature_json: dict | None) -> list[str]:
    """feature_json 의 key_ingredient 원문. 없거나 목록이 아니면 빈 목록."""
    값 = (feature_json or {}).get("key_ingredient")
    if isinstance(값, str):
        값 = [값]
    return [str(x) for x in 값 or [] if x] if isinstance(값, list) else []


async def canonicalize(raw_by_key: dict[str, list[str]]) -> dict[str, list[str]]:
    """{아무 키: 원문 성분 목록} → {같은 키: 표준명 목록}. 별칭 사전은 한 번에 읽는다."""
    from db.ingredient_alias_reader import get_alias_map

    키들 = sorted({normalize_key(n) for names in raw_by_key.values() for n in names if n})
    별칭 = await asyncio.to_thread(get_alias_map, 키들) if 키들 else {}
    return {k: resolve_canonical(names, 별칭) for k, names in raw_by_key.items()}


async def load_product_ingredients(product_ids: Iterable[str]) -> dict[str, list[str]]:
    """{상품 id: 표준명 성분 목록}. DB 에 없는 상품은 빠진다. 성분이 없는 상품은 빈 목록."""
    ids = list(dict.fromkeys(p for p in product_ids if p))
    if not ids:
        return {}

    from db.product_reader import get_product_features
    특징들 = await asyncio.to_thread(get_product_features, ids)
    return await canonicalize({pid: raw_ingredients(f) for pid, f in 특징들.items()})


async def load_rules() -> list[dict[str, Any]]:
    """충돌 규칙 전부. [{ingredient_a, ingredient_b, level, advice}]"""
    global _rules_cache
    now = time.monotonic()
    if _rules_cache is not None and now - _rules_cache[0] < RULES_TTL_S:
        return _rules_cache[1]

    from db.supabase_client import get_supabase

    def _읽기() -> list[dict]:
        return (get_supabase().table("ingredient_conflict_rules")
                .select("ingredient_a, ingredient_b, level, advice")
                .execute()).data or []

    규칙들 = await asyncio.to_thread(_읽기)
    _rules_cache = (now, 규칙들)
    return 규칙들
