"""상품 평가의 기준 상품을 읽고 의도 벡터를 만든다.

READS:  base_product_id, user_id, user_profile, raw_query, query_spec, product_meta
WRITES: candidates, product_meta, intent_vector, query_spec

후보는 기준 상품 하나다. 기준 상품을 평가하는 경로라서 새로 찾지 않는다. 비슷한 상품은
대체 후보 노드가 따로 찾는다.

의도 벡터는 리뷰 점수가 쓴다. 사용자 프로필, 과거 조회 맥락, 기준 상품, 질의 원문을 한
문장으로 묶어 임베딩한다. 과거 맥락은 본인 기준일 때만 기준 상품의 특징 벡터로 찾는다.
다른 사람, 전체 인기 기준에서는 요청한 사람의 맥락이 오히려 결과를 흐린다.

기준 상품이 DB 에 없으면 예외다. BE 가 없는 상품을 미리 막고, 상품 이름은 관문이 이미
id 로 바꿨으므로 여기서 없으면 데이터 문제다.

임베딩, DB 모듈은 함수 안에서 가져온다.
"""
from __future__ import annotations

import asyncio
import logging

from contracts.query_spec import Target
from graph.state import GraphState
from services import product_meta, search_text

logger = logging.getLogger(__name__)

# 문장에 붙일 과거 조회 맥락 수
맥락_수 = 5


def _기준_id(state: GraphState) -> str | None:
    return state.get("base_product_id") or (state.get("query_spec") or {}).get("base_product_ref")


def _본인_기준(state: GraphState) -> bool:
    기준 = (state.get("query_spec") or {}).get("target") or state.get("basis") or Target.SELF.value
    return 기준 == Target.SELF.value


async def _맥락(user_id: str, 기준: str, category: str | None) -> list[str]:
    """기준 상품의 특징 벡터와 가까운 과거 조회 맥락. 특징 벡터가 없으면 빈 목록."""
    from db.product_reader import get_product_meta_with_vec
    from db.vector_search import match_user_contexts

    try:
        정보 = await asyncio.to_thread(get_product_meta_with_vec, 기준)
    except ValueError:
        # 임베딩이 아직 없는 상품이다. 맥락 없이도 평가는 할 수 있다
        logger.warning("discovery: 기준 상품의 특징 벡터가 없다. 과거 맥락 없이 간다 %s", 기준)
        return []
    if not 정보:
        return []
    찾은 = await asyncio.to_thread(
        match_user_contexts, user_id, 정보["feature_vec"], category, 맥락_수,
    )
    return [m["context_text"] for m in 찾은 if m.get("context_text")]


def _문장(state: GraphState, 정보: dict, 맥락: list[str]) -> str:
    from models.agent_context import UserProfile
    from models.extracted_product import ExtractedProduct
    from services.unified_text_builder import build_unified_text

    프로필 = state.get("user_profile") or {}
    return build_unified_text(
        user_profile=UserProfile(
            user_id=state.get("user_id") or "",
            skin_type=프로필.get("skin_type"),
            personal_color=프로필.get("personal_color"),
            skin_concerns=프로필.get("skin_concerns") or [],
        ),
        base_product=ExtractedProduct(
            product_name=정보.get("name"),
            brand=정보.get("brand"),
            category={"main": 정보.get("category"), "sub": None},
        ),
        rag_contexts=맥락,
        query=state.get("raw_query") or None,
    )


async def discovery(state: GraphState) -> dict:
    기준 = _기준_id(state)
    if not 기준:
        raise ValueError("discovery: 기준 상품 id 가 없다")

    메타 = await product_meta.ensure(state.get("product_meta") or {}, [기준])
    정보 = 메타.get(기준)
    if not 정보:
        raise ValueError(f"discovery: 기준 상품을 찾지 못했다 {기준}")

    맥락: list[str] = []
    user_id = state.get("user_id")
    if user_id and _본인_기준(state):
        맥락 = await _맥락(user_id, 기준, 정보.get("category"))

    스펙 = dict(state.get("query_spec") or {})
    if not 스펙.get("category") and 정보.get("category"):
        스펙["category"] = 정보["category"]

    return {
        "candidates": [{"product_id": 기준, "source": "base", "similarity": 1.0}],
        "product_meta": 메타,
        "intent_vector": await search_text.embed(_문장(state, 정보, 맥락)),
        "query_spec": 스펙,
    }
