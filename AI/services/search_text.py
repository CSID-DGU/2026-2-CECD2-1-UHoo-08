"""후보를 찾을 검색 문장과 그 임베딩을 만든다.

상품 임베딩은 상품 특징을 문장으로 풀어 만들었다(feature_text_builder). 질의도
같은 말투로 풀어 붙여야 가까운 상품이 잡힌다. "매트 쿠션" 보다 "매트한 마무리의
쿠션 제품" 이 상품 문장과 더 가깝다.

순서는 이렇다.
    질의 원문 + 특징 조건을 상품 문장 말투로 푼 것 + 문장으로 남은 조건 + 더할 조건

본인 기준이면 사용자의 과거 조회 맥락 중 이번 질의와 가까운 것을 찾아 문장 끝에
붙이고 한 번 더 임베딩한다. 다른 사람 기준, 전체 인기 기준에서는 요청한 사람의
맥락이 오히려 결과를 흐린다.

임베딩, DB 모듈은 함수 안에서 가져온다. 최상단에서 가져오면 키와 모델 없이는 이
모듈을 불러오지도 못한다.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from contracts.query_spec import QuerySpec, Target

logger = logging.getLogger(__name__)

# 검색 문장에 붙일 과거 조회 맥락 수
맥락_수 = 3


def _특징_문장(spec: QuerySpec) -> str:
    """특징 조건을 상품 문장 말투로 푼다. 풀 수 없으면 빈 문자열."""
    if not spec.category or not spec.features:
        return ""
    from services.feature_text_builder import build_product_text

    try:
        return build_product_text(spec.category, spec.features).strip()
    except Exception:
        # 특징 문장은 검색을 돕는 덤이다. 못 만들어도 원문으로 찾을 수 있다.
        logger.warning("검색 문장: 특징 조건을 문장으로 풀지 못했다 %s", spec.features, exc_info=True)
        return ""


def build(spec: QuerySpec, raw_query: str | None, extra_conditions: Iterable[str] = ()) -> str:
    """검색 문장. 빈 조각과 겹치는 조각은 뺀다."""
    조각들 = [raw_query or "", _특징_문장(spec), *spec.conditions, *extra_conditions]
    return " ".join(dict.fromkeys(c.strip() for c in 조각들 if c and c.strip()))


async def embed(text: str) -> list[float]:
    from services.embedding_service import EmbeddingService

    return await asyncio.to_thread(EmbeddingService.get().embed, text)


async def _맥락(user_id: str, 벡터: list[float], category: str | None) -> list[str]:
    from db.vector_search import match_user_contexts

    찾은 = await asyncio.to_thread(match_user_contexts, user_id, 벡터, category, 맥락_수)
    return [m["context_text"] for m in 찾은 if m.get("context_text")]


async def query_vector(
    spec: QuerySpec,
    raw_query: str | None,
    *,
    user_id: str | None,
    extra_conditions: Iterable[str] = (),
) -> tuple[str, list[float] | None]:
    """(검색 문장, 임베딩). 검색할 말이 하나도 없으면 임베딩은 None 이다."""
    문장 = build(spec, raw_query, extra_conditions)
    if not 문장:
        return "", None

    벡터 = await embed(문장)
    if spec.target is not Target.SELF or not user_id:
        return 문장, 벡터

    맥락 = await _맥락(user_id, 벡터, spec.category)
    if not 맥락:
        return 문장, 벡터
    합친 = " ".join([문장, *맥락])
    return 합친, await embed(합친)
