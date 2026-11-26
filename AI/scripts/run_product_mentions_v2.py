"""ProductMatcher v2 추출 실행 (read-only): 게시물 → 뷰티 거르기 → LLM {brand, product_name} → 브랜드 보정 → 쇼핑 검색어.

DB 는 읽기만 한다. 쇼핑 검색 · DB 매칭은 아직 하지 않는다(쇼핑 API 미정).

    cd AI
    python -m scripts.run_product_mentions_v2                 # 10/29 수집 235개 (개발셋)
    python -m scripts.run_product_mentions_v2 --all-posts     # DB 게시물 전부

평가를 위해 뷰티 거르기에 걸린 게시물도 LLM 을 부른다(--skip-filtered 를 주면 부르지 않는다). 결과에 filtered 표시가 있어
"거르기가 LLM 이 제품을 찾은 게시물을 몇 개 버렸나"를 셀 수 있다.

결과: AI/.cache/match_exp/mentions_v2.json (git 에 올리지 않음)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "match_exp" / "mentions_v2.json"
DEV_COLLECTED = "2026-10-29"
CONCURRENCY = 4
PRICE_IN, PRICE_OUT = 0.4, 1.2   # qwen-plus 국제 요금 (USD / 100만 토큰). 청구서로 확인할 것


def load_posts(all_posts: bool) -> list[dict]:
    from db.supabase_client import get_supabase

    sb = get_supabase()
    accounts = {a["id"]: a["username"] for a in sb.table("influencer_accounts").select("id,username").execute().data or []}
    posts = sb.table("influencer_posts").select("id,account_id,caption,posted_at,collected_at").order("id").execute().data or []
    if not all_posts:
        posts = [p for p in posts if (p.get("collected_at") or "").startswith(DEV_COLLECTED)]
    for p in posts:
        p["username"] = accounts.get(p["account_id"], "")
    return posts


class CountingLLM:
    """호출마다 새 클라이언트를 써서 토큰을 정확히 센다 (동시에 돌아도 섞이지 않는다)."""

    def __init__(self):
        from services.llm.client import LLMClient, LLMRole, _설정

        self._make = lambda: LLMClient(*_설정(LLMRole.MATCH))
        self.usage = Counter()

    async def chat_json(self, **kw):
        c = self._make()
        res = await c.chat_json(**kw)
        self.usage.update(c.usage)
        return res


async def run(posts: list[dict], skip_filtered: bool) -> dict:
    from rules.beauty_filter import beauty_signal
    from rules.brand_resolve import BrandDictionary
    from services.product_extractor_v2 import mentions_for_post, v2_cache

    d = BrandDictionary.load()
    cache = v2_cache()
    llm = CountingLLM()
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(p):
        sig = beauty_signal(p.get("caption") or "", d)
        row = {"id": p["id"], "u": p["username"], "cap": p.get("caption") or "", "beauty": sig.is_beauty,
               "signal": {"brands": sig.brands, "types": sig.type_words, "tags": sig.beauty_tags}}
        if skip_filtered and not sig.is_beauty:
            return {**row, "llm_called": False, "matchable": False, "mentions": []}
        async with sem:
            res = await mentions_for_post({"id": p["id"], "caption": p.get("caption") or "", "username": p["username"]}, llm, d, cache)
        return {**row, "llm_called": True, "cached": res["extract"].get("cached"), "failed": res["extract"]["failed"],
                "matchable": res["matchable"], "mentions": res["mentions"], "raw": res["extract"]["products"]}

    t0 = time.perf_counter()
    rows = await asyncio.gather(*(one(p) for p in posts))
    return {"rows": rows, "usage": dict(llm.usage), "elapsed_s": round(time.perf_counter() - t0, 1), "dict_size": len(d.brands)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all-posts", action="store_true")
    ap.add_argument("--skip-filtered", action="store_true")
    args = ap.parse_args()
    posts = load_posts(args.all_posts)
    res = asyncio.run(run(posts, args.skip_filtered))
    rows = res["rows"]
    ms = [m for r in rows for m in r["mentions"]]
    u = res["usage"]
    summary = {
        "posts": len(rows), "beauty_by_filter": sum(r["beauty"] for r in rows),
        "matchable_posts": sum(r["matchable"] for r in rows),
        "filtered_but_llm_found": [r["id"] for r in rows if not r["beauty"] and r["matchable"]],
        "mentions": len(ms), "query_kind": dict(Counter(m["query_kind"] for m in ms)),
        "brand_from": dict(Counter(m["brand_from"] for m in ms)),
        "llm_calls": u.get("calls", 0), "prompt_tokens": u.get("prompt_tokens", 0), "completion_tokens": u.get("completion_tokens", 0),
        "cost_usd_est": round(u.get("prompt_tokens", 0) / 1e6 * PRICE_IN + u.get("completion_tokens", 0) / 1e6 * PRICE_OUT, 4),
        "elapsed_s": res["elapsed_s"], "dict_size": res["dict_size"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
