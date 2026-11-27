"""성분 쌍을 규칙 표로 판정한다. 입력이 같으면 결과가 같다. DB 와 LLM 을 부르지 않는다.

    AVOID     함께 쓰지 않는다
    SEPARATE  아침·저녁으로 나눠 쓴다
    (규칙에 없는 쌍은 괜찮다)

규칙 표(ingredient_conflict_rules)는 쌍을 (작은 이름, 큰 이름) 순서로 한 번만 적는다.
여기서도 같은 순서로 찾는다. 성분 이름은 모두 표준명이어야 한다(services/ingredient_store).
"""
from __future__ import annotations

from typing import Any

AVOID = "AVOID"
SEPARATE = "SEPARATE"
OK = "OK"

_세기 = {OK: 0, SEPARATE: 1, AVOID: 2}

SEPARATE_SCHEDULE = "아침과 저녁으로 나눠 쓰세요"


def rule_index(rules: list[dict[str, Any]]) -> dict[tuple[str, str], dict]:
    """{(작은 이름, 큰 이름): 규칙}."""
    return {tuple(sorted((r["ingredient_a"], r["ingredient_b"]))): r for r in rules}


def find_pairs(ingredients_a: list[str], ingredients_b: list[str],
               rules: list[dict[str, Any]] | dict) -> list[dict[str, Any]]:
    """두 성분 목록 사이에서 규칙에 걸린 쌍. 센 것 먼저, 같은 세기면 이름 순.

    같은 성분끼리는 판정하지 않는다(같은 성분을 두 제품에서 쓰는 것은 충돌이 아니다).
    """
    표 = rules if isinstance(rules, dict) else rule_index(rules)
    본: set[tuple[str, str]] = set()
    쌍들 = []
    for x in ingredients_a or []:
        for y in ingredients_b or []:
            if x == y:
                continue
            키 = tuple(sorted((x, y)))
            if 키 in 본 or 키 not in 표:
                continue
            본.add(키)
            규칙 = 표[키]
            쌍들.append({
                "ingredient_a": 키[0], "ingredient_b": 키[1],
                "level": 규칙["level"], "advice": 규칙.get("advice"),
                "schedule": SEPARATE_SCHEDULE if 규칙["level"] == SEPARATE else None,
            })
    return sorted(쌍들, key=lambda p: (-_세기[p["level"]], p["ingredient_a"], p["ingredient_b"]))


def check_compatibility(inventory: list[dict[str, Any]], product: dict[str, Any],
                        rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """상품 하나를 보유 제품 전부와 견준다. 걸린 쌍마다 한 줄, 보유 제품 id 가 붙는다.

    inventory 항목: {user_product_id, product_id, ingredients}
    product:        {product_id, ingredients}
    같은 상품을 이미 가지고 있으면 그 보유 제품과는 견주지 않는다(PreFilter 가 보유로 뺀다).
    """
    표 = rule_index(rules)
    결과 = []
    for 항목 in inventory or []:
        if 항목.get("product_id") and 항목.get("product_id") == product.get("product_id"):
            continue
        for 쌍 in find_pairs(항목.get("ingredients") or [], product.get("ingredients") or [], 표):
            결과.append({"user_product_id": 항목.get("user_product_id"), **쌍})
    return sorted(결과, key=lambda p: -_세기[p["level"]])


def strongest(levels: list[str]) -> str:
    """가장 센 단계. 비어 있으면 OK."""
    return max(levels, key=lambda l: _세기.get(l, 0), default=OK)
