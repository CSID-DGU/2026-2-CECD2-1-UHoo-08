"""ProductMatcher v1: 캡션 → LLM 추출 → DB 후보 → 규칙 확정 또는 판정 LLM.

1. 추출(services/product_extractor): 캡션에 언급된 제품을 {brand, product_name, category, evidence, …} 로.
2. 후보(rules/product_match.rank_candidates): 브랜드 · 카테고리로 거르고 이름 점수(RapidFuzz)와
   이름 임베딩(bge-m3) 유사도로 TOP 5.
3. 판정: 이름이 거의 같고 브랜드가 확인된 것만 규칙으로 확정한다(rules/product_match.auto_decide).
   나머지는 판정 LLM 에 원문 · 추출 결과 · 후보 5개를 주고, 후보 ID 중 하나 · review · unmatched 를
   받는다(accept_choice 가 후보 밖 ID 를 거부한다). LLM 의 자기보고 확신도는 판정에 쓰지 않는다.

DB 에 쓰지 않는다. 결과 저장 배치는 실제 사례 검수 뒤 따로 잇는다.
임베딩 · LLM 은 주입받는다. 키 · 모델 없이 테스트할 수 있어야 한다.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from prompts.product_extract import VERIFY_SYSTEM, VERIFY_VERSION, build_verify_user
from rules.product_match import (MATCH_V1_2_VERSION, MATCH_V1_VERSION, MATCHED, REVIEW, accept_choice, accept_choice_v1_2,
                                 auto_decide_v12, dedupe_hashtags, load_brand_aliases, load_product_aliases,
                                 rank_candidates_v12, verify_pool)
from services.product_extractor import extract_post

VERIFY_TIMEOUT_S = 60.0

# 이름 임베딩 검색: (질의 문자열들) → [{product_id: 유사도}]. 없으면 이름 점수만 쓴다
EmbedSearch = Callable[[list[str]], list[dict[str, float]]]


def make_name_index(products: list[dict], embed_batch: Callable[[list[str]], list[list[float]]]) -> EmbedSearch:
    """상품명 임베딩을 한 번 만들고, 질의마다 코사인 유사도를 돌려주는 함수를 만든다.

    product_embeddings.feature_vec 은 feature_json 을 문장으로 바꾼 것이라 브랜드 · 제품명이
    들어 있지 않다. 이름 검색에는 쓸 수 없어 상품명을 따로 임베딩한다(L2 정규화 → 내적 = 코사인).
    """
    ids = [p["product_id"] for p in products]
    vecs = embed_batch([f"{p.get('brand') or ''} {p.get('name') or ''}".strip() for p in products])

    def search(queries: list[str]) -> list[dict[str, float]]:
        if not queries:
            return []
        qv = embed_batch(queries)
        return [{pid: float(sum(a * b for a, b in zip(q, v))) for pid, v in zip(ids, vecs)} for q in qv]

    return search


async def verify(llm, caption: str, mention: dict, cands) -> tuple[str, str | None, str, object]:
    """판정 LLM. (status, product_id, 사유, LLM 이 낸 choice 원본)."""
    result = await llm.chat_json(system=VERIFY_SYSTEM, user=build_verify_user(caption, mention, [asdict(c) for c in cands]),
                                 timeout=VERIFY_TIMEOUT_S)
    if not isinstance(result, dict):
        return REVIEW, None, "판정 응답을 읽지 못함", None
    status, pid = accept_choice(result.get("choice"), cands)
    reason = result.get("reason") if isinstance(result.get("reason"), str) else ""
    if status == REVIEW and result.get("choice") != "review":
        known = any(c.product_id == result.get("choice") for c in cands)
        reason = ("고른 후보의 이름에 추출명에 없는 단어가 있음 — " if known else f"후보 밖의 답({result.get('choice')!r}) — ") + reason
    return status, pid, reason, result.get("choice")


async def match_post(post: dict, products: list[dict], prefixes: dict, keys: dict, llm,
                     cache=None, owned_brands: list[str] | None = None, embed_search: EmbedSearch | None = None,
                     brand_aliases: dict[str, set[str]] | None = None, product_aliases: list[dict] | None = None) -> dict:
    """게시물 하나 → {extract, rows}. rows 는 언급마다 판정 결과 한 줄.

    후보 검색은 v1.2(rank_candidates_v12: 정규형 · 부분 이름 · 호수명 · 확인된 별칭)다. 판정 LLM 을 부른 줄에는
    LLM 의 choice 원본과, 같은 답을 완화 규칙(accept_choice_v1_2)으로 본 결과(v1_1 칸)를 함께 남긴다.
    status 칸은 v1 의 엄격한 규칙(accept_choice) 결과다. 두 판정이 같은 LLM 답을 쓰므로 차이는 규칙에서만 나온다.
    해시태그 중복(dedupe_hashtags)은 완화 판정 쪽에만 적용한다.
    """
    if brand_aliases is None:
        brand_aliases = load_brand_aliases()
    if product_aliases is None:
        product_aliases = load_product_aliases()
    ext = await extract_post(post, llm, cache, owned_brands)
    mentions = ext["mentions"]
    queries = [f"{m.get('brand') or ''} {m.get('product_name') or ''}".strip() for m in mentions]
    embeds = embed_search(queries) if embed_search and queries else [{} for _ in mentions]
    rows = []
    for m, emb in zip(mentions, embeds):
        brand, cands = rank_candidates_v12(m, products, prefixes, keys, emb, brand_aliases=brand_aliases,
                                           product_aliases=product_aliases)
        status, pid, reason = auto_decide_v12(m, brand, cands)
        method = "rule" if status == "matched" else None
        choice, v11 = None, None
        if status == "verify":
            pool = verify_pool(cands)
            status, pid, reason, choice = await verify(llm, post.get("caption") or "", m, pool)
            method = "llm"
            s11, p11, r11 = accept_choice_v1_2(choice, pool, m, brand_aliases)
            v11 = {"version": MATCH_V1_2_VERSION, "status": s11, "product_id": p11, "reason": r11}
        rows.append({
            "version": MATCH_V1_VERSION, "verify_version": VERIFY_VERSION if method == "llm" else None,
            "mention": m, "brand_resolved": brand, "status": status, "product_id": pid, "method": method,
            "reason": reason, "candidates": [asdict(c) for c in cands], "llm_choice": choice, "v1_1": v11,
        })
    # 완화 판정 기준으로 해시태그 중복을 묶는다
    view = [{"status": (r["v1_1"] or r)["status"], "product_id": (r["v1_1"] or r)["product_id"], "mention": r["mention"],
             "method": r["method"], "reason": (r["v1_1"] or r)["reason"]} for r in rows]
    names = {p["product_id"]: p.get("name") or "" for p in products}
    dedupe_hashtags(view, names)
    for r, v in zip(rows, view):
        if v.get("method") == "hashtag":
            r["v1_1"] = {"version": MATCH_V1_2_VERSION, "status": MATCHED, "product_id": v["product_id"], "reason": v["reason"]}
    return {"extract": ext, "rows": rows}
