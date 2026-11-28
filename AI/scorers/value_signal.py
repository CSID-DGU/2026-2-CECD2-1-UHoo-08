"""가성비. 예산 대비 판매가 · 같은 제품군 안 가격 · 할인율을 사용자의 가성비 선호도에 맞춰 섞는다.

계산은 rules/value_signal.py 가 한다. 여기서는 비교 기준이 되는 상품 마스터와 사용자의
선호 가중치를 읽어 넘긴다. 상대 가격은 검색 후보가 아니라 마스터 전체에서 비교한다.

가성비 선호도는 user_preference_weights 의 value_signal 값으로 정한다("너무 비싸요" ·
"더 저렴하게" 피드백이 올린다). 기록이 없으면 0.5 다.

판매가(최저가)가 없는 상품은 None 이다.

explain 은 가성비 배지 문구다. Compose 가 이 항목 점수가 높은 상품에만 부른다. DB 를 읽지
않고 상품 정보(판매가 · 정가)와 이번 질의의 예산만으로 문구를 만든다.

DB 는 함수 안에서 import 한다. 키 없이도 이 모듈을 불러올 수 있어야 한다.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from contracts.score import ScoreContext
from rules.value_signal import explain_text, group_prices, preference, value_score

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
        r["feature_json"] = _feature_dict(r.get("feature_json"))
    return rows


def _feature_dict(f: Any) -> dict[str, Any]:
    """feature_json → dict. 문자열이면 풀고, 풀 수 없거나 dict 가 아니면 {}.

    한 행이라도 리스트 · 숫자가 섞이면 제품군을 나눌 때 .get 에서 터져, 가성비를 켠
    요청 전체가 실패한다. 그런 행은 정보가 없는 상품으로 본다.
    """
    if isinstance(f, str):
        try:
            f = json.loads(f)
        except ValueError:
            return {}
    return f if isinstance(f, dict) else {}


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


async def explain(products: list[dict[str, Any]], ctx: ScoreContext) -> dict[str, str]:
    budget = ctx.query_spec.budget.max
    out = {}
    for p in products:
        text = explain_text(p, budget)
        if text:
            out[p["product_id"]] = text
    return out
