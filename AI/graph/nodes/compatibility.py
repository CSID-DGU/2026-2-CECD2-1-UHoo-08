"""보유 제품끼리의 성분 궁합을 점검한다. 홈 루틴 점검 카드의 내용이다.

READS:  inventory
WRITES: routine_check

    {pairs, counts, schedule, uncompared_count, checked_user_product_ids}

    pairs       궁합이 걸린 보유 제품 쌍. 센 것 먼저
                {a: {user_product_id, name}, b: {...}, level, title, reason}
                한 쌍에 성분 조합이 여럿 걸리면 가장 센 것 하나로 적는다
    counts      견준 쌍의 수. 괜찮음(ok) · 시간대 분리(separate) · 함께 쓰지 않음(avoid)
    schedule    아침 · 저녁 순서 (rules/routine_schedule.py)
    uncompared  성분 정보가 없어 견주지 못한 보유 제품 수. 모르는 것을 "괜찮음"으로 세지 않는다

판정은 PreFilter 와 같은 규칙이다(rules/compatibility.find_pairs, services/ingredient_store).
Alternative(루틴 모드)가 AVOID 쌍에서 바꿀 제품을 고른다.
"""
from __future__ import annotations

import logging
from itertools import combinations

from graph.state import GraphState
from rules.compatibility import AVOID, SEPARATE, find_pairs, rule_index
from rules.routine_schedule import build_schedule

logger = logging.getLogger(__name__)

_세기 = {AVOID: 2, SEPARATE: 1}


async def _rules() -> list[dict]:
    from services.ingredient_store import load_rules
    return await load_rules()


def check_routine(items: list[dict], rules: list[dict]) -> dict:
    """보유 제품 목록 → routine_check. 순수 함수."""
    견줄 = [i for i in items if i.get("ingredients")]
    표 = rule_index(rules)

    쌍들, 일정용 = [], []
    개수 = {"ok": 0, "separate": 0, "avoid": 0}
    for a, b in combinations(견줄, 2):
        걸린 = find_pairs(a["ingredients"], b["ingredients"], 표)
        if not 걸린:
            개수["ok"] += 1
            continue
        센 = 걸린[0]
        개수[센["level"].lower()] += 1
        # find_pairs 는 성분 이름 순으로 적는다. 어느 성분이 어느 제품 것인지 되찾는다
        a_성분 = 센["ingredient_a"] if 센["ingredient_a"] in a["ingredients"] else 센["ingredient_b"]
        b_성분 = 센["ingredient_b"] if a_성분 == 센["ingredient_a"] else 센["ingredient_a"]
        쌍들.append({
            "a": {"user_product_id": a["user_product_id"], "name": a.get("name") or ""},
            "b": {"user_product_id": b["user_product_id"], "name": b.get("name") or ""},
            "level": 센["level"],
            "title": f"{a_성분} + {b_성분}",
            "reason": 센.get("advice"),
        })
        일정용.append({"a_id": a["user_product_id"], "b_id": b["user_product_id"], "level": 센["level"],
                     "ingredient_a": a_성분, "ingredient_b": b_성분})

    쌍들.sort(key=lambda p: (-_세기[p["level"]], p["a"]["name"], p["b"]["name"]))
    return {
        "pairs": 쌍들,
        "counts": 개수,
        "schedule": build_schedule(items, 일정용),
        "uncompared_count": len(items) - len(견줄),
        "checked_user_product_ids": [i["user_product_id"] for i in 견줄],
    }


async def compatibility(state: GraphState) -> dict:
    보유 = state.get("inventory") or []
    점검 = check_routine(보유, await _rules() if len(보유) >= 2 else [])
    logger.info("compatibility: 보유 %d개, 견줌 %d개, %s",
                len(보유), len(점검["checked_user_product_ids"]), 점검["counts"])
    return {"routine_check": 점검}
