"""조건 수정. 이전 job 의 질의에 이번에 고친 조건을 합친다.

READS:  job_id, parent_job_id, raw_query
WRITES: query_spec, refine_mode, parent_result, candidates

BE 는 고른 선택지의 문장과 직접 쓴 문장을 쉼표로 이어 raw_query 로 보내고, 고른 선택지
키는 이번 job 의 refine_presets 에 저장한다. 관문이 raw_query 전체를 해석한 질의는 선택지
문장이 섞여 있어 쓰지 않는다.

    1. 이전 job 의 결과, 질의 해석, 스냅샷과 이번 job 의 선택지를 읽는다
    2. 이전 job 이 상품 검색, 상품 평가, 조건 수정이 아니면 고칠 결과가 없으므로 예외다
    3. 선택지 문장을 지운 나머지(직접 쓴 문장)가 있으면 그것만 다시 해석한다
    4. 이전 질의 → 선택지 → 직접 쓴 문장 순서로 합친다
         카테고리, 예산 칸   새 값이 있으면 바꾼다
         특징               키 단위로 덮어쓴다
         문장 조건, 제외 성분 합친다
         환경, 가성비        하나라도 켜져 있으면 켠다
         추천 기준           이전 그대로다
       이전이 상품 평가였으면 기준 상품의 카테고리와 제품 종류를 조건으로 옮겨 검색으로 바꾼다.
       종류는 묶음 이름으로 넓힌다. 젤크림을 평가했으면 크림으로 찾는다. 종류가 잘게
       나뉘어 있어 그대로 쓰면 결과가 지나치게 좁아진다
    5. 찾는 방식을 정한다. 예산을 낮추거나 제외 성분을 더한 것뿐이고 이전 후보가 남아
       있으면 이전 후보를 다시 줄 세운다(RERANK). 아니면 새로 찾는다(RESEARCH)

DB 모듈은 함수 안에서 가져온다.
"""
from __future__ import annotations

import logging
from typing import Any

from contracts.query_spec import QuerySpec, RequestType
from graph.state import GraphState
from rules import refine_presets
from rules.product_types import broader, category_mentioned, mentioned, product_types
from services import product_meta, product_resolver

logger = logging.getLogger(__name__)

재정렬 = "RERANK"
재탐색 = "RESEARCH"

# 조건을 고칠 수 있는 이전 경로
_고칠_수_있는_경로 = frozenset({"S1_EVALUATE", "S2_SEARCH", "S7_REFINE"})
_상품_평가 = "S1_EVALUATE"

_이전_컬럼 = "id, scenario, result, query_spec, state_snapshot"
_이번_컬럼 = "id, refine_presets"

# 바뀌었는지 볼 때 빼는 칸. 조건 수정이면 늘 바뀌는 값이다
_비교_제외 = frozenset({"request_type", "base_product_ref", "confidence"})


async def _읽기(job_id: str | None, columns: str) -> dict[str, Any] | None:
    from services import job_store

    if not job_id:
        return None
    return await job_store.load_job(job_id, columns=columns)


async def _직접_쓴_스펙(state: GraphState, 문장: str) -> QuerySpec | None:
    """직접 쓴 문장만 다시 해석한다. 해석하지 못하면 문장 그대로 조건에 둔다.

    "더 촉촉한 걸로" 처럼 종류나 카테고리를 말하지 않은 문장에도 질의 해석이 그 값을
    채우는 일이 있다. 그대로 합치면 이전 검색의 값을 덮어써 다른 종류의 상품이 나온다.
    문장에 그 종류의 이름이 없으면 종류를 버린다. 카테고리는 남은 종류가 있거나, 문장에
    그 카테고리를 가리키는 말이 있을 때만 받는다.
    """
    if not 문장:
        return None
    from graph.nodes.normalize import normalize

    나옴 = await normalize({**state, "raw_query": 문장, "clarify_answer": None})
    스펙 = QuerySpec.model_validate(나옴["query_spec"])
    특징 = dict(스펙.features)
    종류 = 특징.get("product_type")
    if 종류 is not None and not mentioned(종류, 문장):
        logger.info("refine: 문장에 없는 종류를 버린다 %r (%r)", 종류, 문장)
        특징.pop("product_type")
    카테고리 = 스펙.category
    if (
        카테고리 is not None and "product_type" not in 특징
        and not category_mentioned(카테고리.value, 문장)
    ):
        logger.info("refine: 문장에 근거가 없는 카테고리를 버린다 %r (%r)", 카테고리.value, 문장)
        카테고리 = None
    return 스펙.model_copy(update={"features": 특징, "category": 카테고리})


def _합치기(바탕: QuerySpec, 새: QuerySpec | None) -> QuerySpec:
    if 새 is None:
        return 바탕
    값 = 바탕.model_dump()
    if 새.category:
        값["category"] = 새.category
    값["features"] = {**값["features"], **새.features}
    값["conditions"] = [*값["conditions"], *새.conditions]
    값["exclude_ingredients"] = [*값["exclude_ingredients"], *새.exclude_ingredients]
    if 새.budget.max:
        값["budget"]["max"] = 새.budget.max
    if 새.budget.total:
        값["budget"]["total"] = 새.budget.total
    값["use_env"] = 바탕.use_env or 새.use_env
    값["value_seeking"] = 바탕.value_seeking or 새.value_seeking
    return QuerySpec.model_validate(값)


async def _기준_상품_id(spec: QuerySpec, 이전: dict) -> str | None:
    """이전 상품 평가의 기준 상품 id.

    질의 해석의 base_product_ref 는 사용자가 쓴 상품 이름일 수 있어 그대로 쓰지 않는다.
    해석한 id 를 남긴 스냅샷을 먼저 보고, 없으면(스냅샷에 남기기 전 job) 결과 카드를 본다.
    상품 평가의 결과 카드는 기준 상품 하나뿐이다(대체 후보는 alternatives 에 있다).
    둘 다 없으면 이름을 평가 경로와 같은 방식으로 다시 찾는다.
    """
    남긴 = (이전.get("state_snapshot") or {}).get("base_product_id")
    if 남긴:
        return 남긴
    카드 = next(iter((이전.get("result") or {}).get("items") or []), None)
    if 카드 and 카드.get("productId"):
        return 카드["productId"]
    return await product_resolver.resolve(spec.base_product_ref)


async def _평가를_검색으로(spec: QuerySpec, 이전: dict) -> QuerySpec:
    """이전이 상품 평가였으면 기준 상품의 카테고리와 제품 종류를 조건으로 옮긴다."""
    기준 = await _기준_상품_id(spec, 이전)
    if not 기준:
        return spec
    정보 = (await product_meta.ensure({}, [기준])).get(기준) or {}
    값 = spec.model_dump()
    if not 값["category"] and 정보.get("category"):
        값["category"] = 정보["category"]
    # 종류가 여럿인 상품은 앞의 것이 주 종류다
    종류들 = product_types(정보.get("feature_json"), 정보.get("category"))
    if 종류들:
        종류 = broader(종류들[0], 정보.get("category"))
        값["features"] = {"product_type": 종류, **값["features"]}
    return QuerySpec.model_validate(값)


def _찾는_방식(이전: QuerySpec, 합친: QuerySpec, 이전_후보: list[dict]) -> str:
    """예산을 낮추거나 제외 성분을 더한 것뿐이면 재정렬이다. 이전 후보가 없으면 재탐색이다."""
    if not 이전_후보:
        return 재탐색
    전 = 이전.model_dump(mode="json", exclude=_비교_제외)
    후 = 합친.model_dump(mode="json", exclude=_비교_제외)
    for 칸 in 전.keys() | 후.keys():
        if 전.get(칸) == 후.get(칸):
            continue
        if 칸 == "budget":
            전_상한, 후_상한 = 전[칸]["max"], 후[칸]["max"]
            낮아짐 = 후_상한 is not None and (전_상한 is None or 후_상한 < 전_상한)
            if 낮아짐 and 전[칸]["total"] == 후[칸]["total"]:
                continue
        if 칸 == "exclude_ingredients" and set(전[칸]) <= set(후[칸]):
            continue
        return 재탐색
    return 재정렬


async def refine(state: GraphState) -> dict:
    이전 = await _읽기(state.get("parent_job_id"), _이전_컬럼)
    if not 이전:
        raise ValueError(f"refine: 이전 job 을 찾지 못했다 {state.get('parent_job_id')}")
    이전_경로 = 이전.get("scenario")
    if 이전_경로 not in _고칠_수_있는_경로:
        raise ValueError(f"refine: 조건 수정은 검색 결과에서만 할 수 있다 (이전 경로 {이전_경로})")

    이번 = await _읽기(state.get("job_id"), _이번_컬럼) or {}
    선택지 = list(이번.get("refine_presets") or [])
    이전_스펙 = QuerySpec.model_validate(이전.get("query_spec") or {"request_type": "SEARCH"})
    이전_결과 = 이전.get("result") or {}

    합친 = 이전_스펙
    if 이전_경로 == _상품_평가:
        합친 = await _평가를_검색으로(합친, 이전)
    합친 = refine_presets.apply(합친, 선택지, 이전_스펙, 이전_결과)
    직접 = await _직접_쓴_스펙(state, refine_presets.strip_sentences(state.get("raw_query")))
    합친 = _합치기(합친, 직접).model_copy(update={
        "request_type": RequestType.REFINE, "base_product_ref": None, "confidence": 1.0,
        "target": 이전_스펙.target,
    })
    # 합친 뒤 같은 값이 겹치지 않게 다시 검증한다
    합친 = QuerySpec.model_validate(합친.model_dump())

    이전_후보 = [] if 이전_경로 == _상품_평가 else ((이전.get("state_snapshot") or {}).get("candidates") or [])
    방식 = _찾는_방식(이전_스펙, 합친, 이전_후보)
    logger.info("refine: 선택지 %s, 직접 쓴 문장 %s, %s", 선택지, bool(직접), 방식)

    나감: dict[str, Any] = {
        "query_spec": 합친.model_dump(mode="json"),
        "refine_mode": 방식,
        "parent_result": 이전_결과,
    }
    if 방식 == 재정렬:
        나감["candidates"] = 이전_후보
    return 나감
