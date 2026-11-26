"""가성비. 예산 대비 판매가 · 같은 제품군 안 가격 · 할인율을 사용자의 가성비 선호도에 맞춰 섞는다.

계산은 rules/value_signal.py 가 한다. 여기서는 비교 기준이 되는 상품 마스터와 사용자의
선호 가중치를 읽어 넘긴다. 상대 가격은 검색 후보가 아니라 마스터 전체에서 비교한다.

가성비 선호도는 user_preference_weights 의 value_signal 값으로 정한다("너무 비싸요" ·
"더 저렴하게" 피드백이 올린다). 기록이 없으면 0.5 다.

판매가(최저가)가 없는 상품은 None 이다.

DB 는 함수 안에서 import 한다. 키 없이도 이 모듈을 불러올 수 있어야 한다.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from contracts.score import ScoreContext
from rules.value_signal import group_prices, preference, value_score

_MASTER_COLUMNS = "product_id, category, feature_json, lowest_price, original_price"
_PAGE = 1000


def _load_master() -> list[dict[str, Any]]:
    from db.supabase_client import get_supabase

    sb = get_supabase()
    rows, start = [], 0
    while True:
        batch = (sb.table("products").select(_MASTER_COLUMNS).order("product_id")
                 .range(start, start + _PAGE - 1).execute()).data or []
        rows += batch
        if len(batch) < _PAGE:
            break
        start += _PAGE
    for r in rows:
        if isinstance(r.get("feature_json"), str):
            try:
                r["feature_json"] = json.loads(r["feature_json"])
            except ValueError:
                r["feature_json"] = {}
    return rows


def _load_preference_weight(user_id: str) -> Any:
    """선호 가중치의 value_signal 값. 기록이 없으면 None."""
    from db.supabase_client import get_supabase

    rows = (get_supabase().table("user_preference_weights").select("weights")
            .eq("user_id", user_id).limit(1).execute()).data or []
    return ((rows[0].get("weights") or {}) if rows else {}).get("value_signal")


async def value_signal(products: list[dict[str, Any]], ctx: ScoreContext) -> dict[str, float | None]:
    if not products:
        return {}
    master, weight = await asyncio.gather(
        asyncio.to_thread(_load_master), asyncio.to_thread(_load_preference_weight, ctx.user_id))
    groups = group_prices(master)
    u = preference(weight)
    budget = ctx.query_spec.budget.max
    out: dict[str, float | None] = {}
    for p in products:
        v = value_score(p, groups, budget, u).score
        out[p["product_id"]] = None if v is None else round(v * 100, 2)
    return out
