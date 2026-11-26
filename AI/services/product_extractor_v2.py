"""ProductMatcher v2 추출: 캡션 → LLM {brand, product_name} → 브랜드 보정 · 쇼핑 검색어.

LLM(LLMRole.MATCH, qwen-plus)은 브랜드와 제품명만 낸다(prompts/product_extract_v2). 그다음은 규칙이다.
  - 응답 검사: product_name 이 문자열이 아니거나 비면 그 항목은 뺀다. 같은 제품명은 하나로.
  - 브랜드 보정 · 검색어: rules/brand_resolve.resolve
게시물에 검색어가 하나도 없으면 그 게시물은 매칭에서 뺀다(matchable = False).

LLM 응답은 캐시한다(.cache/product_extract/extract-v2.jsonl). 같은 게시물 · 같은 캡션 · 같은 프롬프트 버전이면 다시 부르지 않는다.
호출 실패(시간 초과 · 네트워크)는 예외로 올린다. 응답 틀이 깨지면 두 번 더 묻고, 그래도 깨지면 failed 로 남긴다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from prompts.product_extract_v2 import EXTRACT_V2_SYSTEM, EXTRACT_V2_VERSION, build_extract_v2_user
from rules.brand_resolve import RESOLVE_VERSION, BrandDictionary, key, resolve
from services.product_extractor import ExtractCache, cache_key

CACHE_PATH = Path(__file__).resolve().parent.parent / ".cache" / "product_extract" / f"{EXTRACT_V2_VERSION}.jsonl"
RETRIES = 2
TIMEOUT_S = 60.0


def parse_products(result: Any) -> list[dict] | None:
    """LLM 응답 → [{brand, product_name}]. 틀이 깨졌으면 None."""
    if not isinstance(result, dict) or not isinstance(result.get("products"), list):
        return None
    out, seen = [], set()
    for it in result["products"]:
        if not isinstance(it, dict):
            continue
        name = it.get("product_name")
        if not isinstance(name, str) or not name.strip():
            continue
        brand = it.get("brand") if isinstance(it.get("brand"), str) and it.get("brand").strip() else None
        k = (key(brand), key(name))
        if k in seen:
            continue
        seen.add(k)
        out.append({"brand": brand.strip() if brand else None, "product_name": re.sub(r"\s+", " ", name).strip()})
    return out


async def extract_products(post: dict, llm, cache: ExtractCache | None = None) -> dict:
    """게시물 하나 → {products, attempts, cached, failed}. post: {id, caption, username}."""
    caption = post.get("caption") or ""
    ck = cache_key(post["id"], caption, EXTRACT_V2_VERSION)
    if cache and (hit := cache.get(ck)) is not None:
        return {**hit, "cached": True}
    if not caption.strip():
        out = {"products": [], "attempts": 0, "failed": False}
    else:
        out = None
        user = build_extract_v2_user(caption, post.get("username") or "")
        for attempt in range(1, RETRIES + 2):
            res = await llm.chat_json(system=EXTRACT_V2_SYSTEM, user=user, timeout=TIMEOUT_S,
                                      temperature=0.0 if attempt == 1 else 0.3)
            parsed = parse_products(res)
            if parsed is not None:
                out = {"products": parsed, "attempts": attempt, "failed": False}
                break
        if out is None:
            out = {"products": [], "attempts": RETRIES + 1, "failed": True}
    if cache and not out["failed"]:
        cache.put(ck, out)
    return {**out, "cached": False}


async def mentions_for_post(post: dict, llm, d: BrandDictionary, cache: ExtractCache | None = None) -> dict:
    """게시물 하나 → {matchable, mentions:[{brand_text, brand, brand_from, product_name, query, query_kind}], extract}."""
    ext = await extract_products(post, llm, cache)
    rows = []
    for it in ext["products"]:
        r = resolve(it, post.get("caption") or "", d)
        rows.append({
            "brand_text": r.brand_text, "brand_ko": r.brand.ko if r.brand else None, "brand_en": r.brand.en if r.brand else None,
            "db_brand": r.brand.db_brand if r.brand else None, "brand_from": r.brand_from,
            "product_name": r.product_name, "query": r.query, "query_kind": r.query_kind,
        })
    return {"matchable": any(x["query"] for x in rows), "mentions": rows, "extract": ext,
            "versions": {"extract": EXTRACT_V2_VERSION, "resolve": RESOLVE_VERSION}}


def v2_cache() -> ExtractCache:
    return ExtractCache(CACHE_PATH)
