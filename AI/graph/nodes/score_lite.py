"""LLM 보정 없이 가볍게 채점한다.

READS:  scenario, alternatives, candidates, product_meta, query_spec, user_profile, inventory,
        env_summary, weight_prior, intent_vector, job_id, user_id
WRITES: alternatives, alternatives_dropped_count, scored, product_meta

    상품 평가   대체 후보를 채점한다. 점수 분해 맨 앞에 "비슷한 정도"를 둔다.
                총점이 하한보다 낮은 후보는 빼고 그 수를 남긴 뒤 상위 몇 개만 둔다
    그 밖       후보를 채점해 scored 에 쓴다(홈 추천)

대체 후보는 기준 상품 카드 옆에 붙는 덤이라 LLM 보정까지 기다릴 이유가 없다.

"비슷한 정도"는 가중치가 0 이라 총점에 들어가지 않는다. BE 가 이 키로 유사도를 읽어
화면에 보여 준다.
"""
from __future__ import annotations

import logging

from contracts.score import SCORE_LABELS
from graph.nodes.score import products_for, score_context
from graph.state import GraphState
from services import scoring

logger = logging.getLogger(__name__)

# 대체 후보로 남길 총점 하한과 개수
대체_점수_하한 = 50
대체_남길_수 = 5

_상품_평가 = "S1_EVALUATE"
_유사도_키 = "similarity"


def _유사도_항목(similarity: float | None) -> dict:
    점수 = round(min(1.0, max(0.0, similarity or 0.0)) * 100, 1)
    return {"key": _유사도_키, "label": SCORE_LABELS[_유사도_키], "score": 점수, "weight": 0.0}


async def _채점(state: GraphState, 후보들: list[dict]) -> tuple[list[dict], dict]:
    상품들, 메타 = await products_for(state, 후보들)
    매긴 = await scoring.score_products(
        상품들, score_context(state), state.get("weight_prior"), lite=True,
    )
    return 매긴, 메타


async def _대체_후보(state: GraphState) -> dict:
    후보들 = state.get("alternatives") or []
    if not 후보들:
        return {"alternatives": [], "alternatives_dropped_count": 0}

    매긴, 메타 = await _채점(state, 후보들)
    유사도 = {후보["product_id"]: 후보.get("similarity") for 후보 in 후보들}
    통과 = [점수 for 점수 in 매긴 if 점수["total"] >= 대체_점수_하한]
    뺀_수 = len(매긴) - len(통과)
    if 뺀_수:
        logger.info("score_lite: 총점 %d점 미만 대체 후보 %d개를 뺐다.", 대체_점수_하한, 뺀_수)

    return {
        "alternatives": [
            {
                **점수,
                "similarity": 유사도.get(점수["product_id"]),
                "breakdown": [_유사도_항목(유사도.get(점수["product_id"])), *점수["breakdown"]],
            }
            for 점수 in 통과[:대체_남길_수]
        ],
        "alternatives_dropped_count": 뺀_수,
        "product_meta": 메타,
    }


async def score_lite(state: GraphState) -> dict:
    if state.get("scenario") == _상품_평가:
        return await _대체_후보(state)

    후보들 = state.get("candidates") or []
    if not 후보들:
        return {"scored": []}
    매긴, 메타 = await _채점(state, 후보들)
    return {"scored": 매긴, "product_meta": 메타}
