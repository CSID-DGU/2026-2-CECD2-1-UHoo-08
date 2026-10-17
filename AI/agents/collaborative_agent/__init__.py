"""
collaborative_agent — 유사 사용자 협업 필터링.

흐름:
  1. user_skin_profiles에서 skinType + personalColor 일치 사용자 조회 (본인 제외)
  2. 해당 사용자들의 user_products를 (사용자, 상품)마다 한 번씩만 센 뒤 상품 단위 집계
     weighted_score = Σ(rating X usage_weight)
     usage_weight: USING=1.0, USED=0.7 (실제로 써 본 기록만. 좋아요는 넣지 않는다)
     같은 사람이 같은 상품을 여러 번 샀으면 평점이 있는 가장 최근 행 하나의 가중치와 평점을 쓴다
  3. weighted_score 내림차순으로 top_k 선택 (exclude_ids 제외)
  4. 결과 부족(MIN_VALID_RESULTS 미만)이면 fallback 실행
  5. 상품 메타 조인 후 SimilarUserProduct 리스트로 반환

LLM 미사용, SQL 집계만.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from agents.collaborative_agent.fallback import run_fallback
from db.product_reader import get_products_meta
from db.score_reader import get_similar_user_ids, get_user_products_by_users
from models.recommendation_result import SimilarUserProduct
from prompts.collaborative_strategy import MIN_VALID_RESULTS, USAGE_WEIGHTS


def _pick_row_per_user(
    rows: list,
    exclude_set: set,
) -> Dict[Tuple[str, str], dict]:
    """(user_id, product_id) → 그 사람이 그 상품에 남긴 행 하나.

    user_products 는 산 제품 한 통마다 한 줄이라, 같은 제품을 다시 산 사람은 여러 줄을 가진다.
    줄마다 더하면 한 사람의 평가가 여러 번 들어가므로 사람·상품마다 한 줄만 고른다.
    평점이 있는 줄 중 가장 최근 줄을 고르고, 가중치와 평점은 반드시 그 줄의 것을 함께 쓴다.
    다른 줄에서 따로 가져오면 "다 써 보고 준 평점"에 "쓰는 중" 가중치를 곱하는 식의 없는 조합이 생긴다.
    created_at 이 같으면 id 가 큰 줄을 고른다. 그러지 않으면 조회 순서에 따라 고르는 줄이 바뀌어 점수가 흔들린다.
    """
    picked: Dict[Tuple[str, str], dict] = {}
    for r in rows:
        pid = r["product_id"]
        if pid in exclude_set or r["rating"] is None:
            continue
        if USAGE_WEIGHTS.get(r["usage_type"], 0.0) == 0.0:
            continue
        key = (r["user_id"], pid)
        cur = picked.get(key)
        if cur is None or _recency(r) > _recency(cur):
            picked[key] = r
    return picked


def _recency(r: dict) -> Tuple[str, str]:
    """최근 순서를 정하는 키. created_at 이 같으면 id 로 갈라 항상 같은 줄을 고른다."""
    return (r.get("created_at") or "", str(r.get("id") or ""))


def _aggregate(
    rows: list,
    exclude_set: set,
) -> List[Tuple[str, float, int]]:
    """user_products rows → [(product_id, weighted_score, count)] 내림차순. count 는 평가한 사람 수."""
    agg: Dict[str, Dict[str, float]] = defaultdict(lambda: {"score": 0.0, "n": 0.0})
    for (_, pid), r in _pick_row_per_user(rows, exclude_set).items():
        a = agg[pid]
        a["score"] += r["rating"] * USAGE_WEIGHTS[r["usage_type"]]
        a["n"] += 1

    scored = [(pid, v["score"], int(v["n"])) for pid, v in agg.items()]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


async def run_collaborative(
    user_id: str,
    skin_type: Optional[str],
    personal_color: Optional[str],
    exclude_ids: Optional[List[str]] = None,
    top_k: int = 5,
) -> List[SimilarUserProduct]:
    """collaborative 핵심 로직."""
    exclude_set = set(exclude_ids or [])

    similar_user_ids = await asyncio.to_thread(
        get_similar_user_ids, skin_type, personal_color, user_id
    )

    if not similar_user_ids:
        # 유사 사용자 없으면 바로 폴백
        return await run_fallback(skin_type, top_k, list(exclude_set))

    rows = await asyncio.to_thread(get_user_products_by_users, similar_user_ids)
    scored = _aggregate(rows, exclude_set)

    if len(scored) < MIN_VALID_RESULTS:
        # 집계 결과 부족 → 콜드스타트 폴백
        return await run_fallback(skin_type, top_k, list(exclude_set))

    top = scored[:top_k]
    product_ids = [pid for pid, _, _ in top]
    metas = await asyncio.to_thread(get_products_meta, product_ids)

    results: List[SimilarUserProduct] = []
    n_users = len(similar_user_ids)
    for pid, score, n in top:
        meta = metas.get(pid)
        if meta is None:
            continue
        # 만족도 % = (평균 평점 / 5) × 100, 카운트가 적으면 보수적으로 감점
        avg_rating = score / max(n, 1) if n > 0 else 0.0
        confidence = min(1.0, n / max(n_users * 0.1, 1))  # 유사 사용자 10% 이상 응답 -> 충분히 신뢰할 수 있음 -> 1.0
        satisfaction = round(min(100, (avg_rating / 5) * 100 * confidence))
        results.append(
            SimilarUserProduct(
                id=meta["id"],
                name=meta["name"],
                brand=meta["brand"],
                image_url=meta["image_url"],
                price=meta["price"],
                satisfaction_percent=max(0, satisfaction),
            )
        )
    return results


# ── @tool 래퍼 ───────────────────────────────────────────────────────────

try:
    from langchain_core.tools import tool

    @tool
    async def call_collaborative_agent(
        user_id: str,
        skin_type: Optional[str] = None,
        personal_color: Optional[str] = None,
        exclude_product_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> list:
        """피부 조건이 유사한 사용자들의 user_products를 weighted_score로 집계해 추천한다.
        데이터 부족 시 같은 피부타입의 인기 상품으로 폴백한다."""
        results = await run_collaborative(
            user_id=user_id,
            skin_type=skin_type,
            personal_color=personal_color,
            exclude_ids=exclude_product_ids,
            top_k=top_k,
        )
        return [r.model_dump(by_alias=True) for r in results]

except ImportError:
    call_collaborative_agent = None  # type: ignore