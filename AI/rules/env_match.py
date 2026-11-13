"""상품이 요즘 환경에 필요한 기능 하나를 채우는지 본다.

추천 결과의 ENV 배지와 홈 환경 카드가 쓴다. 환경 점수가 높다는 것만으로 배지를 달면
어떤 기능 때문에 맞는지 말할 수 없다. 기능 하나를 정해 그 이유 문장을 붙이려고 쓴다.

    카테고리   기능에 카테고리가 있으면 같아야 한다
    특징       기능의 특징 조건이 상품 특징과 모두 같아야 한다. 목록이면 모두 들어 있어야 한다
               상품에 그 특징이 없으면 채운다고 보지 않는다
"""
from __future__ import annotations

from typing import Any


def _같은_값(원하는: Any, 상품값: Any) -> bool:
    if 상품값 is None:
        return False
    if isinstance(원하는, list):
        상품_목록 = 상품값 if isinstance(상품값, list) else [상품값]
        return set(map(str, 원하는)) <= set(map(str, 상품_목록))
    if isinstance(원하는, bool) or isinstance(상품값, bool):
        return 원하는 == 상품값
    return str(원하는) == str(상품값)


def meets(need: dict[str, Any], product: dict[str, Any]) -> bool:
    """need 는 env_summary.needs 의 항목, product 는 product_meta 의 항목이다."""
    카테고리 = need.get("category")
    if 카테고리 and product.get("category") != 카테고리:
        return False
    특징 = product.get("feature_json") or {}
    return all(_같은_값(값, 특징.get(키)) for 키, 값 in (need.get("features") or {}).items())
