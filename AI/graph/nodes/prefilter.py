"""보유 제품과 견줘 후보를 거른다. 판정 규칙은 rules/prefilter.py 에 있다.

READS:  candidates, inventory, product_meta, query_spec, scenario, base_product_id, replace_target
WRITES: candidates, excluded, conflict_marks, base_conflicts, product_meta

거르지 않고 그대로 두는 경우
    다른 사람 기준   받을 사람의 보유 제품은 모른다. 요청한 사람 것으로 거르면 틀린다
    보유 제품 없음   보유 제품 노드가 아직 없을 때다. 경고만 남긴다

성분 충돌은 B 의 성분 부품(services.ingredient_store, rules.compatibility)으로
판정한다. 그 모듈이 아직 없으면 충돌 판정만 건너뛰고 보유 제품은 그대로 거른다.
모듈은 있는데 그 안에서 import 가 실패하면 숨기지 않고 올린다. 의존성이 빠진
것을 "아직 없는 부품"으로 덮으면 충돌 판정이 조용히 꺼진다.

상품 평가의 기준 상품은 사용자가 물은 것이라 빼지 않는다. 판정은 base_conflicts 로
남겨 추천 이유에서 알린다.

루틴 점검에서 바꿀 보유 제품은 충돌 판정에서 뺀다. 곧 안 쓸 제품과 충돌하는 것은
문제가 아니다.
"""
from __future__ import annotations

import importlib
import logging
from types import ModuleType

from contracts.query_spec import Target
from graph.state import GraphState
from rules import prefilter as 규칙

logger = logging.getLogger(__name__)

_성분_모듈 = "services.ingredient_store"
_궁합_모듈 = "rules.compatibility"

# 성분 부품이 없다는 경고를 이미 남겼는지. 요청마다 남기면 로그가 묻힌다.
_부품_없음_알림 = False


def _불러오기(이름: str) -> ModuleType | None:
    """모듈 자체가 없을 때만 None. 그 밖의 import 실패는 올린다."""
    try:
        return importlib.import_module(이름)
    except ModuleNotFoundError as e:
        if e.name != 이름:
            raise
        return None


def _성분_부품() -> tuple[ModuleType, ModuleType] | None:
    global _부품_없음_알림
    성분, 궁합 = _불러오기(_성분_모듈), _불러오기(_궁합_모듈)
    if 성분 is None or 궁합 is None:
        if not _부품_없음_알림:
            logger.warning("prefilter: 성분 부품이 아직 없다. 성분 충돌 판정을 건너뛴다.")
            _부품_없음_알림 = True
        return None
    return 성분, 궁합


async def _충돌_쌍(
    상품_ids: list[str], 보유: list[dict], 메타: dict,
) -> tuple[dict[str, list[dict]], dict]:
    """상품마다 보유 제품과 걸린 성분 쌍, 그리고 성분을 채운 상품 정보."""
    부품 = _성분_부품()
    if 부품 is None:
        return {}, 메타
    성분_모듈, 궁합_모듈 = 부품

    성분들 = await 성분_모듈.load_product_ingredients(상품_ids)
    규칙들 = await 성분_모듈.load_rules()

    # 성분은 뒤 단계(추천 이유, 대체 후보)도 쓴다. 상품 정보가 있는 상품에만 채운다.
    # 정보가 없는 상품에 성분만 넣으면 뒤 단계가 정보를 다 읽은 것으로 착각한다.
    새_메타 = {
        pid: ({**값, "ingredients": 성분들.get(pid) or []} if pid in 성분들 else 값)
        for pid, 값 in 메타.items()
    }

    쌍들: dict[str, list[dict]] = {}
    if 보유:
        for pid in 상품_ids:
            성분 = 성분들.get(pid) or []
            if 성분:
                쌍들[pid] = 궁합_모듈.check_compatibility(
                    보유, {"product_id": pid, "ingredients": 성분}, 규칙들,
                )
    return 쌍들, 새_메타


async def prefilter(state: GraphState) -> dict:
    후보들 = state.get("candidates") or []
    if not 후보들:
        return {}

    if (state.get("query_spec") or {}).get("target") == Target.OTHER.value:
        logger.info("prefilter: 다른 사람 기준이라 거르지 않는다.")
        return {}

    if "inventory" not in state or state.get("inventory") is None:
        logger.warning("prefilter: 보유 제품 정보가 없다. 거르지 않는다.")
        return {}
    보유 = state["inventory"]

    바꿀 = (state.get("replace_target") or {}).get("user_product_id")
    판정_보유 = [항목 for 항목 in 보유 if not 바꿀 or 항목.get("user_product_id") != 바꿀]

    상품_ids = list(dict.fromkeys(후보["product_id"] for 후보 in 후보들))
    메타 = state.get("product_meta") or {}
    쌍들, 메타 = await _충돌_쌍(상품_ids, 판정_보유, 메타)

    기준_id = state.get("base_product_id")
    결과 = 규칙.apply(
        후보들, 보유, 쌍들,
        {pid: (메타.get(pid) or {}).get("name") for pid in 상품_ids},
        keep_ids={기준_id} if 기준_id else frozenset(),
    )
    if 결과.excluded:
        logger.info("prefilter: 후보 %d개를 뺐다.", len(결과.excluded))

    return {
        "candidates": 결과.candidates,
        "excluded": [*(state.get("excluded") or []), *결과.excluded],
        "conflict_marks": {**(state.get("conflict_marks") or {}), **결과.conflict_marks},
        "base_conflicts": {**(state.get("base_conflicts") or {}), **결과.base_conflicts},
        "product_meta": 메타,
    }
