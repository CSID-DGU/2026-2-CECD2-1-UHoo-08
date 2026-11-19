"""결과를 내보내기 직전에 문장과 모양을 점검한다. 규칙은 rules/guard_rules.py 에 있다.

READS:  result
WRITES: result

금지 표현이 든 문장은 이렇게 다룬다.
    추천 이유(items, alternatives)   점수가 높은 두 항목으로 만든 규칙 문장으로 바꾼다
    배지                              뺀다. 배지는 없어도 카드가 성립한다
    바꿀 제품 안내, 루틴 팁, 쌍 설명   비운다. 모두 없어도 되는 칸이다

마지막에 결과 계약으로 검증한다. 통과하지 못하면 예외를 올려 job 을 실패로 남긴다.
모양이 틀린 결과가 저장되면 화면이 깨지고, 그때는 어느 단계가 틀렸는지 찾기 어렵다.
"""
from __future__ import annotations

import copy
import logging

from contracts.result import RecommendationResult
from graph.state import GraphState
from rules.guard_rules import fallback_reason, has_forbidden

logger = logging.getLogger(__name__)


def _카드들(카드들: list[dict]) -> int:
    """이유 문장과 배지를 점검한다. 바꾸거나 뺀 수를 돌려준다."""
    바꾼 = 0
    for 카드 in 카드들:
        if has_forbidden(카드.get("reason")):
            카드["reason"] = fallback_reason(카드.get("breakdown") or [])
            바꾼 += 1
        배지들 = 카드.get("badges") or []
        남은 = [배지 for 배지 in 배지들 if not has_forbidden(배지.get("text"))]
        바꾼 += len(배지들) - len(남은)
        if 배지들:
            카드["badges"] = 남은
    return 바꾼


def _비운다(칸: dict | None, 이름: str) -> int:
    if 칸 and has_forbidden(칸.get(이름)):
        칸[이름] = None
        return 1
    return 0


async def guard(state: GraphState) -> dict:
    결과 = copy.deepcopy(state.get("result") or {})

    바꾼 = _카드들(결과.get("items") or [])
    바꾼 += _카드들(결과.get("alternatives") or [])
    바꾼 += _비운다(결과.get("replacement"), "message")
    바꾼 += _비운다(결과.get("schedule"), "tip")
    for 쌍 in 결과.get("pairs") or []:
        바꾼 += _비운다(쌍, "reason")
    if 바꾼:
        logger.warning("guard: 금지 표현이 든 문장 %d개를 바꾸거나 뺐다. job=%s",
                       바꾼, 결과.get("jobId"))

    RecommendationResult.model_validate(결과)
    return {"result": 결과}
