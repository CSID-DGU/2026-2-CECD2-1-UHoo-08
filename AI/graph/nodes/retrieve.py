"""질의로 추천 후보를 찾는다.

READS:  scenario, raw_query, query_spec, user_id, user_profile, env_summary, env_conditions,
        budget_plan, refine_mode, candidates, product_meta
WRITES: candidates, product_meta, intent_vector

경로와 상태를 보고 찾는 방법을 고른다.

    기본      질의 문장을 임베딩해 상품 임베딩과 가까운 것을 찾는다
    환경      기본과 같다. 요즘 환경에 필요한 기능을 검색 문장에 더한다(거르지는 않는다)
    재정렬    조건 수정에서 이전 후보를 다시 줄 세울 때다. 새로 찾지 않고 바뀐 질의로
              임베딩만 다시 만든 뒤 필터를 다시 건다
    칸별      예산 세트다. 칸마다 따로 찾는다. 칸 가격 상한은 걸지 않는다(조합은 Bundle 이 정한다)
    홈        홈 환경 추천이다. 보유 제품이 덮지 못한 기능마다 찾는다

찾은 뒤에는 질의 조건(제품 종류, 예산, 제외 성분)을 어긴 후보를 거른다(rules/retrieve_filter.py).
거르려면 가격과 특징이 필요해서 상품 정보를 여기서 읽고, 뒤 단계가 다시 읽지 않게 상태에 남긴다.

intent_vector 는 리뷰 점수가 쓴다. 칸별, 홈에서는 질의 전체를 임베딩한 것 하나를 쓴다.

임베딩, DB 모듈은 함수 안에서 가져온다.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any

from contracts.query_spec import QuerySpec, RequestType
from graph.state import GraphState
from rules import retrieve_filter
from services import product_meta, search_text

logger = logging.getLogger(__name__)

# 한 번에 찾는 수와 거른 뒤 남기는 수
기본_검색_수 = 60
기본_남길_수 = 40
칸_검색_수 = 20
칸_남길_수 = 15
홈_검색_수 = 15

_홈_경로 = "HOME_ENV"
_조건_수정_경로 = "S7_REFINE"
_재정렬_모드 = "RERANK"

_성분_모듈 = "services.ingredient_store"


def _스펙(state: GraphState) -> QuerySpec:
    """홈 추천처럼 질의가 없는 경로는 조건 탐색으로 본다."""
    return QuerySpec.model_validate(
        {"request_type": RequestType.SEARCH.value, **(state.get("query_spec") or {})}
    )


async def _찾기(벡터: list[float], category: str | None, 개수: int) -> list[dict]:
    from db.vector_search import match_products

    return await asyncio.to_thread(match_products, 벡터, category, 개수)


def _후보(찾은: list[dict], source: str, **더: Any) -> list[dict]:
    return [
        {"product_id": m["product_id"], "source": source, "similarity": m.get("similarity"), **더}
        for m in 찾은
    ]


async def _성분(상품_ids: list[str], spec: QuerySpec) -> dict[str, list[str]] | None:
    """제외 성분 조건이 있을 때만 읽는다. 성분 부품(B)이 아직 없으면 None."""
    if not spec.exclude_ingredients:
        return {}
    try:
        모듈 = importlib.import_module(_성분_모듈)
    except ModuleNotFoundError as e:
        if e.name != _성분_모듈:
            raise
        logger.warning("retrieve: 성분 부품이 아직 없다. 제외 성분 조건을 건너뛴다.")
        return None
    return await 모듈.load_product_ingredients(상품_ids)


async def _거르기(
    후보들: list[dict], 메타: dict, spec: QuerySpec, 남길_수: int,
) -> tuple[list[dict], dict]:
    상품_ids = list(dict.fromkeys(후보["product_id"] for 후보 in 후보들))
    메타 = await product_meta.ensure(메타, 상품_ids)
    성분 = await _성분(상품_ids, spec)
    return retrieve_filter.apply(후보들, 메타, spec, ingredients=성분, limit=남길_수), 메타


def _환경_조건(state: GraphState, spec: QuerySpec) -> list[str]:
    if not spec.use_env:
        return []
    필요들 = (state.get("env_summary") or {}).get("needs") or []
    return [조건 for 필요 in 필요들 for 조건 in 필요.get("conditions") or []]


async def _기본(state: GraphState, spec: QuerySpec) -> dict:
    _, 벡터 = await search_text.query_vector(
        spec, state.get("raw_query"),
        user_id=state.get("user_id"), extra_conditions=_환경_조건(state, spec),
    )
    if 벡터 is None:
        logger.warning("retrieve: 검색할 말이 없다. 후보 없이 넘긴다.")
        return {"candidates": [], "intent_vector": None}
    찾은 = await _찾기(벡터, spec.category, 기본_검색_수)
    후보들, 메타 = await _거르기(
        _후보(찾은, "retrieve"), state.get("product_meta") or {}, spec, 기본_남길_수,
    )
    return {"candidates": 후보들, "product_meta": 메타, "intent_vector": 벡터}


async def _재정렬(state: GraphState, spec: QuerySpec) -> dict:
    _, 벡터 = await search_text.query_vector(
        spec, state.get("raw_query"), user_id=state.get("user_id"),
    )
    이전 = [{**후보, "source": "rerank"} for 후보 in state.get("candidates") or []]
    후보들, 메타 = await _거르기(이전, state.get("product_meta") or {}, spec, 기본_남길_수)
    return {"candidates": 후보들, "product_meta": 메타, "intent_vector": 벡터}


async def _칸별(state: GraphState, spec: QuerySpec, 칸들: list[dict]) -> dict:
    _, 벡터 = await search_text.query_vector(
        spec, state.get("raw_query"), user_id=state.get("user_id"),
    )
    메타 = state.get("product_meta") or {}
    후보들: list[dict] = []
    for 칸 in 칸들:
        종류 = 칸.get("product_type")
        이름 = " ".join(w for w in (칸.get("label"), 종류) if w)
        # 질의 전체의 카테고리, 특징은 칸마다 다르므로 빼고 칸의 값으로 찾는다
        칸_스펙 = spec.model_copy(update={
            "category": 칸.get("category"),
            "features": {"product_type": 종류} if 종류 else {},
        })
        문장 = search_text.build(칸_스펙.model_copy(update={"features": {}}), 이름)
        if not 문장:
            continue
        찾은 = await _찾기(await search_text.embed(문장), 칸.get("category"), 칸_검색_수)
        칸_후보, 메타 = await _거르기(
            _후보(찾은, "retrieve", slot_key=칸.get("slot_key")), 메타, 칸_스펙, 칸_남길_수,
        )
        후보들.extend(칸_후보)
    return {"candidates": 후보들, "product_meta": 메타, "intent_vector": 벡터}


async def _홈(state: GraphState, spec: QuerySpec) -> dict:
    덮이지_않은 = {
        조건["key"] for 조건 in state.get("env_conditions") or [] if not 조건.get("covered")
    }
    필요들 = [
        필요 for 필요 in (state.get("env_summary") or {}).get("needs") or []
        if 필요.get("key") in 덮이지_않은
    ]
    if not 필요들:
        return {"candidates": [], "intent_vector": None}

    메타 = state.get("product_meta") or {}
    후보들: list[dict] = []
    본: set[str] = set()
    for 필요 in 필요들:
        필요_스펙 = QuerySpec(
            request_type=RequestType.SEARCH,
            category=필요.get("category"),
            features=필요.get("features") or {},
            conditions=필요.get("conditions") or [],
            exclude_ingredients=spec.exclude_ingredients,
        )
        문장 = search_text.build(필요_스펙, None)
        if not 문장:
            continue
        찾은 = await _찾기(await search_text.embed(문장), 필요.get("category"), 홈_검색_수)
        필요_후보, 메타 = await _거르기(
            _후보(찾은, f"env:{필요['key']}"), 메타, 필요_스펙, 홈_검색_수,
        )
        # 두 기능에 함께 걸린 상품은 먼저 찾은 기능의 후보로 둔다
        for 후보 in 필요_후보:
            if 후보["product_id"] not in 본:
                본.add(후보["product_id"])
                후보들.append(후보)

    이름들 = " ".join(필요.get("label") or 필요["key"] for 필요 in 필요들)
    return {"candidates": 후보들, "product_meta": 메타, "intent_vector": await search_text.embed(이름들)}


async def retrieve(state: GraphState) -> dict:
    spec = _스펙(state)
    시나리오 = state.get("scenario")

    if 시나리오 == _홈_경로:
        return await _홈(state, spec)
    if state.get("budget_plan"):
        return await _칸별(state, spec, state["budget_plan"])
    if (
        시나리오 == _조건_수정_경로
        and state.get("refine_mode") == _재정렬_모드
        and state.get("candidates")
    ):
        return await _재정렬(state, spec)
    return await _기본(state, spec)
