"""후보에 점수를 매겨 총점 순으로 줄 세운다.

READS:  candidates, product_meta, query_spec, user_profile, inventory, env_summary,
        weight_prior, intent_vector, job_id, user_id
WRITES: scored, product_meta

후보는 검색 유사도 순 상위 몇 개만 채점한다. 후기 점수는 상품마다 DB 를 부르고
보정은 LLM 을 부르므로, 후보를 모두 채점하면 기다리는 시간이 후보 수만큼 늘어난다.

상품 정보는 후보를 찾은 노드가 채워 두지만, 빠진 상품이 있으면 여기서 읽어
채운다. 상품 정보가 없는 후보는 점수를 낼 수 없어 뺀다.

추천 기준(basis)은 query_spec.target 을 읽는다. 화면에서 고른 기준은 관문에서
이미 query_spec.target 에 맞춰 두었다.
"""
from __future__ import annotations

import logging

from contracts.query_spec import QuerySpec
from contracts.score import ScoreContext
from graph.state import GraphState
from services import product_meta, scoring

logger = logging.getLogger(__name__)

# 채점할 후보 수
채점_상한 = 30


async def score(state: GraphState) -> dict:
    후보들 = sorted(
        state.get("candidates") or [],
        key=lambda 후보: 후보.get("similarity") or 0.0,
        reverse=True,
    )[:채점_상한]
    if not 후보들:
        logger.info("score: 채점할 후보가 없다.")
        return {"scored": []}

    메타 = await product_meta.ensure(
        state.get("product_meta") or {}, [후보["product_id"] for 후보 in 후보들],
    )
    상품들 = [
        {**메타[후보["product_id"]], "product_id": 후보["product_id"],
         "similarity": 후보.get("similarity")}
        for 후보 in 후보들 if 후보["product_id"] in 메타
    ]
    if len(상품들) < len(후보들):
        logger.warning("score: 상품 정보가 없는 후보 %d개를 뺐다.", len(후보들) - len(상품들))

    ctx = ScoreContext(
        job_id=state["job_id"],
        user_id=state["user_id"],
        query_spec=QuerySpec.model_validate(state.get("query_spec") or {}),
        user_profile=state.get("user_profile") or {},
        inventory=state.get("inventory") or [],
        env_summary=state.get("env_summary"),
        intent_vector=state.get("intent_vector") or None,
    )
    매긴 = await scoring.score_products(상품들, ctx, state.get("weight_prior"), lite=False)
    return {"scored": 매긴, "product_meta": 메타}
