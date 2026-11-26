"""ProductMatcher 실험판: v1.2 흐름(추출 → 후보 → 규칙 확정 → 판정 LLM → 인정 규칙)에 후보 검색 설정만 바꿔 끼운다.

services/product_matcher_v1.match_post 는 고치지 않는다. 이 파일은 scripts/experiment_product_match 가
설정(rules/candidate_search.SearchConfig)마다 같은 게시물을 다시 돌릴 때만 쓴다. DB 에 쓰지 않는다.

판정 LLM 호출은 주입받는다(verify_fn). 실험 스크립트가 같은 입력의 호출을 캐시하고 호출마다 토큰을 센다.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Awaitable, Callable

from rules.candidate_search import SearchConfig, search_candidates, verify_pool_exp
from rules.product_match import MATCHED, REVIEW, accept_choice_v1_2, auto_decide_v12, dedupe_hashtags
from services.product_extractor import extract_post

# (캡션, 언급, 후보 dict 목록) → 판정 LLM 의 JSON 응답 (없으면 None)
VerifyFn = Callable[[str, dict, list[dict]], Awaitable[object]]


async def match_post_exp(post: dict, products: list[dict], prefixes: dict, keys: dict, llm, cfg: SearchConfig,
                         verify_fn: VerifyFn, cache=None, owned_brands: list[str] | None = None, embed_search=None,
                         brand_aliases: dict[str, set[str]] | None = None,
                         product_aliases: list[dict] | None = None) -> dict:
    """게시물 하나 → {extract, rows}. rows[i] 는 추출 언급 i 의 결과다 (골든셋의 mentions 번호와 같다)."""
    ext = await extract_post(post, llm, cache, owned_brands)
    mentions = ext["mentions"]
    queries = [f"{m.get('brand') or ''} {m.get('product_name') or ''}".strip() for m in mentions]
    embeds = embed_search(queries) if embed_search and queries else [{} for _ in mentions]
    rows = []
    for m, emb in zip(mentions, embeds):
        brand, cands = search_candidates(m, products, prefixes, keys, emb, cfg, brand_aliases=brand_aliases,
                                         product_aliases=product_aliases)
        status, pid, reason = auto_decide_v12(m, brand, cands)
        # auto_decide 는 1위 이름 점수가 60 미만이면 판정 없이 unmatched 로 끝낸다. 임베딩 · 브랜드 전체 경로로
        # 들어온 판정 후보가 있으면 판정으로 넘긴다. v1.2 설정에서는 이때 판정 후보가 늘 비어 있어 결과가 같다
        if status == "unmatched" and cands and verify_pool_exp(cands, cfg):
            status = "verify"
        method = "rule" if status == MATCHED else None
        choice, pool, blocked = None, [], None
        if status == "verify":
            pool = verify_pool_exp(cands, cfg)
            if not pool:
                status, reason = "unmatched", "판정 후보 없음"
            else:
                result = await verify_fn(post.get("caption") or "", m, [_verify_view(c) for c in pool])
                choice = result.get("choice") if isinstance(result, dict) else None
                method = "llm"
                status, pid, reason = accept_choice_v1_2(choice, pool, m, brand_aliases)
                # 인정 규칙이 막은 것: LLM 이 후보 하나를 골랐는데 review 가 됐다
                if status == REVIEW and any(c.product_id == choice for c in pool):
                    blocked = reason
        rows.append({
            "config": cfg.name, "mention": m, "brand_resolved": brand, "status": status, "product_id": pid,
            "method": method, "reason": reason, "candidates": [asdict(c) for c in cands],
            "pool": [c.product_id for c in pool], "llm_choice": choice, "blocked": blocked,
        })
    view = [{"status": r["status"], "product_id": r["product_id"], "mention": r["mention"], "method": r["method"],
             "reason": r["reason"]} for r in rows]
    dedupe_hashtags(view, {p["product_id"]: p.get("name") or "" for p in products})
    for r, v in zip(rows, view):
        if v.get("method") == "hashtag":
            r.update(status=MATCHED, product_id=v["product_id"], method="hashtag", reason=v["reason"])
    return {"extract": ext, "rows": rows}


def _verify_view(c) -> dict:
    """판정 LLM 에 보여 주는 후보. v1 의 build_verify_user 가 받는 것과 같은 키를 쓴다."""
    d = asdict(c)
    return {k: d[k] for k in ("product_id", "brand", "name", "category", "name_score", "embed_score", "search_name",
                              "missing", "alias")}
