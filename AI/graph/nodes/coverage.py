"""요즘 환경에 필요한 기능 중 보유 제품이 채우지 못한 것을 찾는다.

READS:  env_summary, inventory, query_spec
WRITES: env_conditions, query_spec

필요한 기능마다 보유 제품 중 그 기능을 채우는 첫 제품을 찾는다(rules/env_match.py).
채운 제품이 있으면 덮인 기능이다. 홈 환경 카드는 덮이지 않은 기능만 채울 제품을 찾는다.

질의 조건도 여기서 고친다. 홈 추천은 질의 문장이 없으므로 덮이지 않은 기능마다
"기능 이름(카테고리)" 조건 하나를 만든다. 기능마다 채울 제품의 카테고리가 다르므로
둘을 짝지어 둔다. 결과의 질의 요약이 이 조건을 보여 준다. 질의의 카테고리는 덮이지
않은 기능이 모두 같은 카테고리일 때만 그 값이고, 섞여 있으면 비운다.

상품은 기능마다 따로 찾고 따로 추천한다(retrieve 홈 모드, compose).
"""
from __future__ import annotations

import logging

from graph.state import GraphState
from rules.env_match import meets

logger = logging.getLogger(__name__)

# 조건에 기능 이름과 짝지어 적는 카테고리 이름
카테고리_이름: dict[str, str] = {
    "base": "베이스",
    "sun": "선케어",
    "lip": "립",
    "skincare": "스킨케어",
    "eye": "아이",
    "cheek": "치크",
}


def need_condition(필요: dict) -> str:
    """덮이지 않은 기능 하나의 검색 조건. 예: "자외선 차단(선케어)"."""
    이름 = 필요.get("label") or 필요["key"]
    카테고리 = 카테고리_이름.get(필요.get("category") or "")
    return f"{이름}({카테고리})" if 카테고리 else 이름


def _조건(필요: dict, 보유: list[dict]) -> dict:
    채운 = next((제품 for 제품 in 보유 if meets(필요, 제품)), None)
    return {
        "key": 필요["key"],
        "label": 필요.get("label") or 필요["key"],
        "basis": 필요.get("basis"),
        "covered": 채운 is not None,
        "covered_by": (채운 or {}).get("name") or None,
    }


async def coverage(state: GraphState) -> dict:
    필요들 = (state.get("env_summary") or {}).get("needs") or []
    보유 = state.get("inventory")
    if 보유 is None:
        logger.warning("coverage: 보유 제품 단계가 아직 없다. 모든 기능을 덮이지 않은 것으로 본다.")
        보유 = []

    조건들 = [_조건(필요, 보유) for 필요 in 필요들]
    덮이지_않은 = [
        필요 for 필요, 조건 in zip(필요들, 조건들) if not 조건["covered"]
    ]

    spec = dict(state.get("query_spec") or {})
    spec["use_env"] = True
    if 덮이지_않은:
        카테고리들 = {필요.get("category") for 필요 in 덮이지_않은}
        spec["category"] = 카테고리들.pop() if len(카테고리들) == 1 else None
    spec["conditions"] = [need_condition(필요) for 필요 in 덮이지_않은]
    return {"env_conditions": 조건들, "query_spec": spec}
