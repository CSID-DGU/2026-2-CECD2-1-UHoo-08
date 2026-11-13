"""
products.feature_json 기반 상품 유사도 검색.

1차: category로 필터
2차: feature_json 필드별 유사도 점수화 → 내림차순 정렬
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from db.supabase_client import get_supabase
from rules.product_match import feature_match_ratio


def _parse_feature_json(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def search_by_features(
    category: str,
    query_features: Dict[str, Any],
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """category 1차 필터 → feature 유사도 2차 정렬."""
    sb = get_supabase()

    products_res = (
        sb.table("products")
        .select("product_id, name, brand, category, image_url, original_price, feature_json")
        .eq("category", category)
        .execute()
    )
    products = products_res.data or []
    if not products:
        return []

    results = []
    for p in products:
        pid = p["product_id"]
        feat = _parse_feature_json(p.get("feature_json"))
        score = feature_match_ratio(query_features, feat) if query_features else 0.0
        results.append({
            "productId": pid,
            "name": p["name"],
            "brand": p["brand"],
            "category": p["category"],
            "imageUrl": p.get("image_url"),
            "originalPrice": p.get("original_price"),
            "matchScore": round(score * 100),
        })

    results.sort(key=lambda x: x["matchScore"], reverse=True)
    return results[:top_k]
