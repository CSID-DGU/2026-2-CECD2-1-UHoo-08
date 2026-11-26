"""조건 수정 전후의 순위 변화를 낸다.

READS:  scored, parent_result
WRITES: rank_changes

이전 결과 카드의 순위(1부터)와 이번 점수 상위 몇 개의 순위를 비교한다.
    이전에 없던 상품    NEW, 순위 차이는 없다
    차이 = 이전 순위 - 이번 순위. 양수면 UP, 음수면 DOWN, 0 이면 SAME

순서는 바꾸지 않는다. 줄 세우기는 Score 가 이미 했다.
"""
from __future__ import annotations

from graph.state import GraphState

# 비교하는 이번 결과 수. 결과 카드 수와 같다
비교_수 = 10


def rank_changes(이전_카드: list[dict], 이번: list[dict]) -> dict[str, dict]:
    이전_순위 = {}
    for 순위, 카드 in enumerate(이전_카드, start=1):
        이전_순위.setdefault(카드.get("productId"), 순위)

    변화: dict[str, dict] = {}
    for 순위, 점수 in enumerate(이번[:비교_수], start=1):
        pid = 점수["product_id"]
        전 = 이전_순위.get(pid)
        if 전 is None:
            변화[pid] = {"change": "NEW", "rank_delta": None}
            continue
        차이 = 전 - 순위
        변화[pid] = {
            "change": "UP" if 차이 > 0 else "DOWN" if 차이 < 0 else "SAME",
            "rank_delta": 차이,
        }
    return 변화


async def rerank(state: GraphState) -> dict:
    이전_카드 = (state.get("parent_result") or {}).get("items") or []
    return {"rank_changes": rank_changes(이전_카드, state.get("scored") or [])}
