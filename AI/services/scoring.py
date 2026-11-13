"""후보 상품에 점수를 매긴다. Score 노드와 가벼운 채점(score_lite)이 함께 쓴다.

점수 항목은 scorers/ 폴더를 읽어 불러온다. 파일 하나가 항목 하나이고, 함수
이름이 파일 이름과 같다. B, C 가 항목 파일을 넣으면 여기를 고치지 않아도 쓰인다.

순서는 이렇다.
    1. 카테고리별 가격 중앙값을 낸다. 이번 후보와 보유 제품 가격을 함께 쓴다
    2. 모든 항목을 동시에 계산한다. 항목 안의 예외는 삼키지 않는다
    3. 가중치를 정한다. full 모드면 LLM 배수 보정을 한 번 더 한다
    4. 점수를 낼 수 없는 상품을 빼고 총점을 합친다
    5. 총점, 같으면 검색 유사도 순으로 정렬한다

점수를 낼 수 없는 상품은 데이터가 비어 있는 상품이라 빼고 개수만 남긴다. 모든
상품이 그렇다면 상품이 아니라 설정이 잘못된 것이므로 예외를 올린다.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import statistics
from pathlib import Path
from typing import Any

from contracts.score import ScoreContext, Scorer, build_score
from rules.score_weights import decide

logger = logging.getLogger(__name__)

# 점수 항목 폴더와 패키지 이름
_기본_폴더 = Path(__file__).resolve().parent.parent / "scorers"
_기본_패키지 = "scorers"

# 불러온 점수 항목. 폴더마다 한 번만 읽는다.
_불러온: dict[tuple[str, str], dict[str, Scorer]] = {}


def load_scorers(
    directory: Path | None = None, package: str = _기본_패키지,
) -> dict[str, Scorer]:
    """폴더 안의 점수 항목을 {키: 함수} 로 돌려준다. __init__ 은 뺀다.

    파일은 있는데 같은 이름 함수가 없으면 예외다. 이름을 잘못 지은 항목이
    조용히 빠지면 그 항목이 왜 점수에 없는지 찾기 어렵다.
    """
    폴더 = directory or _기본_폴더
    열쇠 = (str(폴더), package)
    if 열쇠 in _불러온:
        return _불러온[열쇠]

    항목들: dict[str, Scorer] = {}
    for 파일 in sorted(폴더.glob("*.py")):
        이름 = 파일.stem
        if 이름.startswith("_"):
            continue
        모듈 = importlib.import_module(f"{package}.{이름}")
        함수 = getattr(모듈, 이름, None)
        if 함수 is None:
            raise AttributeError(f"{package}.{이름} 에 async def {이름}(products, ctx) 가 없다")
        항목들[이름] = 함수
    _불러온[열쇠] = 항목들
    logger.info("점수 항목 %d개를 불러왔다: %s", len(항목들), ", ".join(항목들))
    return 항목들


def category_stats(products: list[dict[str, Any]], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    """카테고리별 가격 중앙값. {카테고리: {"median_price": 값}}

    보유 제품 가격도 넣는다. 평소 쓰는 제품보다 비싼지가 예산을 말하지 않은
    사용자에게는 가장 가까운 기준이다.
    """
    가격들: dict[str, list[float]] = {}
    for 상품 in [*products, *inventory]:
        카테고리, 가격 = 상품.get("category"), 상품.get("price")
        if 카테고리 and 가격 is not None and 가격 > 0:
            가격들.setdefault(카테고리, []).append(가격)
    return {
        카테고리: {"median_price": statistics.median(값들)}
        for 카테고리, 값들 in 가격들.items()
    }


async def _llm_배수(가중치: dict[str, float], ctx: ScoreContext) -> dict[str, float]:
    """LLM 이 준 항목별 배수. 호출이 실패하면 보정하지 않는다(모두 1.0).

    보정은 덤이다. LLM 이 멈췄다고 추천 전체를 실패로 만들 이유는 없다.
    """
    from prompts.weight_adjustment_v2 import (
        WEIGHT_ADJUSTMENT_V2_SYSTEM,
        build_weight_adjustment_v2_user_prompt,
    )
    from services.llm import LLMRole, get_llm
    from services.weight_validator import validate_multipliers

    켜진 = [키 for 키, 값 in 가중치.items() if 값 > 0]
    if not 켜진:
        return {}
    spec = ctx.query_spec
    try:
        원본 = await get_llm(LLMRole.WEIGHT).chat_json(
            system=WEIGHT_ADJUSTMENT_V2_SYSTEM,
            user=build_weight_adjustment_v2_user_prompt(
                가중치, ctx.user_profile.get("search_purpose"),
                spec.conditions, spec.value_seeking,
            ),
        )
    except Exception:
        logger.warning("가중치 보정 LLM 호출 실패. 보정 없이 진행한다.", exc_info=True)
        원본 = None
    return validate_multipliers(원본, 켜진)


async def _가중치(
    ctx: ScoreContext, prior: dict | None, 항목_키: set[str], lite: bool,
) -> dict[str, float]:
    가중치 = decide(prior, ctx.query_spec, ctx.query_spec.target.value, 항목_키)
    if lite:
        return 가중치
    배수 = await _llm_배수(가중치, ctx)
    return {키: 값 * 배수.get(키, 1.0) for 키, 값 in 가중치.items()}


async def score_products(
    products: list[dict[str, Any]],
    ctx: ScoreContext,
    prior: dict | None,
    *,
    lite: bool,
) -> list[dict]:
    """상품마다 ScoredProduct 를 dump 한 dict 를 총점 순으로 돌려준다.

    products 는 상품 정보(product_meta 한 칸)에 product_id 와 검색 유사도
    similarity 를 더한 것이다. lite 면 LLM 보정을 하지 않는다.
    """
    if not products:
        return []

    항목들 = load_scorers()
    ctx = ctx.model_copy(update={"category_stats": category_stats(products, ctx.inventory)})

    결과들 = await asyncio.gather(*(함수(products, ctx) for 함수 in 항목들.values()))
    항목별 = dict(zip(항목들, 결과들))
    가중치 = await _가중치(ctx, prior, set(항목들), lite)

    매긴: list[tuple[dict, float]] = []
    뺀 = 0
    for 상품 in products:
        pid = 상품["product_id"]
        점수 = {키: 값.get(pid) for 키, 값 in 항목별.items()}
        # 가중치가 있는 항목 중 하나라도 점수가 있어야 총점을 낼 수 있다
        if not any(v is not None and 가중치.get(k, 0) > 0 for k, v in 점수.items()):
            뺀 += 1
            continue
        매긴.append((build_score(pid, 점수, 가중치).model_dump(), 상품.get("similarity") or 0.0))

    if 뺀:
        logger.warning("점수를 낼 수 없는 상품 %d개를 뺐다 (전체 %d개).", 뺀, len(products))
    if not 매긴:
        raise ValueError(
            f"상품 {len(products)}개 모두 점수를 낼 수 없다. 점수 항목이나 가중치 설정을 확인한다 "
            f"(항목={sorted(항목들)}, 가중치={가중치})"
        )

    매긴.sort(key=lambda 쌍: (쌍[0]["total"], 쌍[1]), reverse=True)
    return [점수 for 점수, _ in 매긴]
