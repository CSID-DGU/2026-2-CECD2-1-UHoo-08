"""총예산과 세트 구성을 칸별 금액으로 나눈다. 규칙은 rules/budget_split.py.

READS:  query_spec
WRITES: budget_plan

    [{slot_key, label, category, product_type, amount}]

Retrieve 가 칸마다 따로 찾고, Bundle 이 칸 금액으로 세트의 핵심 단계를 정한다.
라우터가 예산 세트로 보냈다면 총예산과 구성 단계는 이미 있다(없으면 되묻는다).
"""
from __future__ import annotations

import logging

from graph.state import GraphState
from rules.budget_split import split

logger = logging.getLogger(__name__)


async def budget(state: GraphState) -> dict:
    spec = state.get("query_spec") or {}
    총액 = (spec.get("budget") or {}).get("total")
    단계들 = spec.get("bundle_steps") or []
    계획 = split(총액, 단계들)
    if not 계획:
        logger.warning("budget: 총예산(%s)이나 구성 단계(%d개)가 없어 칸을 나누지 못했다.", 총액, len(단계들))
    return {"budget_plan": 계획}
