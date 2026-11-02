"""인스타 게시물 광고 판별. 1차 규칙 → 2차 LLM.

1차 규칙(rules/ad_disclosure.py)이 광고 / 광고 아님을 정한 게시물은 거기서
끝낸다. 판단을 넘긴(unsure) 게시물만 LLM 에 묻는다. 판정 기준은
eval/prompts/trend_ad_v1.md, 2차 프롬프트는 prompts/ad_classify.py.

LLM 응답이 JSON 이 아니거나 판정 코드가 목록에 없으면 is_ad 를 None 으로
돌려준다. 판정하지 못한 것이다. 근거가 부족하다는 판정(INSUFFICIENT_EVIDENCE)
과는 다르다. 그쪽은 LLM 이 읽고 비광고로 본 것이다.

config · LLM SDK 는 함수 안에서 import 한다. 키 없이 테스트할 수 있어야 한다.
"""
from __future__ import annotations

import logging
from typing import Any

from prompts.ad_classify import AD_CLASSIFY_SYSTEM
from rules.ad_disclosure import RULE_VERSION, UNSURE, classify

logger = logging.getLogger(__name__)

LLM_VERSION = "ad-llm-v2"

# 판정 코드 → 권장 결과. LLM 이 is_ad 를 빠뜨리면 이 값을 쓴다
REASON_CODES: dict[str, bool] = {
    "OWN_BRAND": True,
    "DIRECT_SALES": True,
    "PRODUCT_GIVEAWAY": True,
    "PROMOTIONAL_COPY": True,
    "EARLY_ACCESS": True,
    "PERSONAL_REVIEW": False,
    "SALE_SHARING": False,
    "NON_PRODUCT_EVENT": False,
    "INSUFFICIENT_EVIDENCE": False,
}


def owned_brand_aliases(owned_brands: list[dict] | None) -> list[str]:
    """influencer_accounts.json 의 owned_brands → 1차 규칙이 캡션에서 찾을 표기."""
    return [alias for b in owned_brands or [] for alias in b.get("aliases", [])]


def build_user_message(caption: str, username: str, owned_brands: list[dict] | None, rule_hits: list[dict]) -> str:
    if owned_brands:
        brands = ", ".join(f"{b['brand']}({', '.join(b.get('aliases', []))})" for b in owned_brands)
        account = f"@{username}. 이 계정이 운영하는 브랜드: {brands}"
    else:
        account = f"@{username}. 운영하는 브랜드 없음"
    signals = ", ".join(f"{h['text']}" for h in rule_hits) or "없음"
    return f"[계정 정보]\n{account}\n\n[1차 규칙이 찾은 상업 신호]\n{signals}\n\n[캡션]\n{caption}"


def parse_judgement(result: Any) -> dict | None:
    """LLM 응답을 검사한다. 쓸 수 없으면 None."""
    if not isinstance(result, dict):
        return None
    code = result.get("reason_code")
    if code not in REASON_CODES:
        return None
    is_ad = result.get("is_ad")
    if not isinstance(is_ad, bool):
        is_ad = REASON_CODES[code]
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    return {
        "is_ad": is_ad,
        "reason_code": code,
        "evidence": [e for e in evidence if isinstance(e, str)],
        "reason": result.get("reason") if isinstance(result.get("reason"), str) else "",
    }


async def judge_with_llm(
    caption: str,
    username: str,
    owned_brands: list[dict] | None,
    rule_hits: list[dict],
    llm=None,
) -> dict | None:
    """1차가 넘긴 게시물 하나를 LLM 에 묻는다. 쓸 수 없는 응답이면 None."""
    if llm is None:
        from services.llm import LLMRole, get_llm
        llm = get_llm(LLMRole.AD)
    result = await llm.chat_json(
        system=AD_CLASSIFY_SYSTEM,
        user=build_user_message(caption, username, owned_brands, rule_hits),
    )
    judgement = parse_judgement(result)
    if judgement is None:
        logger.warning("광고 2차 판정 응답을 쓸 수 없음 @%s: %r", username, result)
    return judgement


async def classify_post(caption: str | None, username: str, owned_brands: list[dict] | None = None, llm=None) -> dict:
    """게시물 하나를 판정한다.

    반환값:
        is_ad:       True | False | None (2차 응답을 쓸 수 없음)
        labeled_by:  "RULE" | "LLM"
        version:     판정한 규칙·프롬프트 버전. 고치면 이 버전으로 골라 다시 돌린다
        rule_hits:   1차 규칙이 찾은 근거
        reason_code: 2차 판정 코드 (1차에서 끝났으면 None)
        evidence, reason: 2차가 든 근거
    """
    rule = classify(caption, owned_brand_aliases(owned_brands))
    base = {"rule_hits": rule["hits"], "reason_code": None, "evidence": [], "reason": ""}
    if rule["verdict"] != UNSURE:
        return {**base, "is_ad": rule["is_ad"], "labeled_by": "RULE", "version": RULE_VERSION}

    judgement = await judge_with_llm(caption or "", username, owned_brands, rule["hits"], llm=llm)
    if judgement is None:
        return {**base, "is_ad": None, "labeled_by": "LLM", "version": LLM_VERSION}
    return {**base, **judgement, "labeled_by": "LLM", "version": LLM_VERSION}
