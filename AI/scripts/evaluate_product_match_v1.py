"""ProductMatcher v1 실험: 수집한 인스타 게시물 전체를 LLM 추출 → DB 후보 → 판정으로 돌린다.

DB 는 읽기만 한다. influencer_post_products · products 에 쓰지 않는다. 합성 데이터
(eval/trend/)는 읽지 않는다 — 입력은 운영 DB 의 influencer_posts 뿐이다.

    cd AI
    python -m scripts.evaluate_product_match_v1 --out-dir match_v1
    python -m scripts.evaluate_product_match_v1 --out-dir match_v1 --limit 20   # 앞 20개만

결과 (out-dir):
  rows.csv          게시물 × 언급 한 줄. 상태 · 방법(rule/llm) · 후보 TOP5
  unregistered.csv  추출됐지만 DB 에 없는 제품. 브랜드+제품명으로 묶고 독립 작성자 수 순
  golden_draft.jsonl 골든셋 초안 100건 (eval/golden/trend 형식, 사람이 검수해야 정답이 된다)
  summary.json      v0.1 과 비교 · 토큰 · 비용 추정 · 처리 시간 · v1.1(빠진 단어 검사 완화) 비교

v1.1 은 판정 LLM 의 같은 답에 다른 인정 규칙(rules/product_match.accept_choice_v1_1)을 쓴 결과다.
rows.csv 의 status_v1_1 · product_id_v1_1 · reason_v1_1 열에 있다. 운영 판정은 v1 그대로다.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from prompts.product_extract import EXTRACT_VERSION, VERIFY_VERSION
from rules.product_match import MATCH_V1_VERSION, MATCHED, brand_keys, brand_prefixes, core_name, compact, normalize

# 비용 추정용 단가 (USD / 100만 토큰). qwen-plus 국제 요금으로 알고 있는 값이다. 청구서로 확인할 것
PRICE_IN, PRICE_OUT = 0.4, 1.2
CONCURRENCY = 4
SCOPE = ("base", "sun", "lip", "skincare")


def _load():
    from db.supabase_client import get_supabase

    sb = get_supabase()
    products = [p for p in sb.table("products").select("product_id,brand,name,category").execute().data or []
                if p.get("category") in SCOPE]
    accounts = {a["id"]: a["username"] for a in sb.table("influencer_accounts").select("id,username").execute().data or []}
    posts = sb.table("influencer_posts").select("id,account_id,caption,posted_at").order("id").execute().data or []
    for p in posts:
        p["username"] = accounts.get(p["account_id"], "")
    return products, posts


def _owned_brands() -> dict[str, list[str]]:
    from services.influencer_collector import ACCOUNTS_PATH

    rows = json.loads(Path(ACCOUNTS_PATH).read_text(encoding="utf-8"))
    out = {}
    for a in rows:
        names = []
        for b in a.get("owned_brands") or []:
            names += [b.get("brand", "")] + list(b.get("aliases", []))
        if names:
            out[a["username"]] = [n for n in names if n]
    return out


def _baseline(products, posts) -> dict:
    """v0.1 을 같은 입력으로 다시 돌려 비교 기준을 만든다."""
    from scripts.evaluate_product_match import link_handles, run, summarize

    rows = run(products, posts, link_handles(products, posts)[0])
    s = summarize(rows, len(posts))
    return {k: s[k] for k in ("posts_with_match", "matched_pairs", "products_matched", "products_2plus_authors")}


async def _run(products, posts, limit=None, product_aliases=None):
    from services.embedding_service import EmbeddingService
    from services.llm import LLMRole, get_llm
    from services.product_extractor import ExtractCache
    from services.product_matcher_v1 import make_name_index, match_post
    from scripts.evaluate_product_match import link_handles

    llm = get_llm(LLMRole.MATCH)
    prefixes = brand_prefixes(products)
    keys = brand_keys(products, prefixes, link_handles(products, posts)[0])
    emb = EmbeddingService.get()
    search = make_name_index(products, emb.embed_batch)
    owned = _owned_brands()
    cache = ExtractCache()
    sem = asyncio.Semaphore(CONCURRENCY)
    todo = posts[:limit] if limit else posts

    async def one(p):
        async with sem:
            try:
                return p, await match_post(p, products, prefixes, keys, llm, cache, owned.get(p["username"]), search,
                                              product_aliases=product_aliases), None
            except Exception as e:  # 실험 스크립트라 게시물 하나의 실패는 기록하고 다음으로 간다
                return p, None, f"{type(e).__name__}: {e}"

    before = dict(llm.usage)
    t0 = time.perf_counter()
    results = await asyncio.gather(*(one(p) for p in todo))
    elapsed = time.perf_counter() - t0
    usage = {k: llm.usage[k] - before.get(k, 0) for k in llm.usage}
    return results, usage, elapsed


def _key(brand, name) -> str:
    return compact(normalize(brand or "")) + "|" + compact(core_name(name or ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="match_v1")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--golden", type=int, default=100)
    # 일반화 평가: DB 밖 게시물 파일 · 메모리에만 더할 상품 · 사람이 확인한 별칭만 쓰기
    ap.add_argument("--posts-file", help="게시물 JSON [{platform_post_id, username, caption, posted_at}] (DB 대신)")
    ap.add_argument("--extra-products", help="메모리에서만 마스터에 더할 상품 JSON (DB 에 쓰지 않음)")
    ap.add_argument("--user-aliases-only", action="store_true", help="verified_by=user 인 제품 별칭만 쓴다")
    args = ap.parse_args()
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

    products, posts = _load()
    if args.posts_file:
        raw = json.loads(Path(args.posts_file).read_text(encoding="utf-8"))
        # 게시물 ID 는 DB 와 겹치지 않게 100000 부터. 추출 캐시 키에 쓰인다
        posts = [{"id": 100000 + i, "username": r["username"], "caption": r.get("caption") or "",
                  "posted_at": r.get("posted_at")} for i, r in enumerate(raw)]
    if args.extra_products:
        products = products + json.loads(Path(args.extra_products).read_text(encoding="utf-8"))
    from rules.product_match import load_product_aliases
    aliases = load_product_aliases()
    if args.user_aliases_only:
        aliases = [a for a in aliases if a.get("verified_by") == "user"]
    byid = {p["product_id"]: p for p in products}
    base = _baseline(products, posts)
    results, usage, elapsed = asyncio.run(_run(products, posts, args.limit, aliases))

    rows, failed, errors, cached = [], 0, [], 0
    for p, res, err in results:
        if err:
            errors.append({"post_id": p["id"], "error": err}); continue
        ext = res["extract"]
        failed += ext["failed"]; cached += ext.get("cached", False)
        if not res["rows"]:
            rows.append({"post_id": p["id"], "username": p["username"], "status": "no_mention", "method": "", "product_id": "",
                         "product_name": "", "brand": "", "extracted": "", "mention_type": "", "specificity": "",
                         "evidence": "", "reason": "", "candidates": "", "llm_choice": "", "llm_choice_name": "",
                         "status_v1_1": "no_mention", "product_id_v1_1": "", "reason_v1_1": ""})
        for r in res["rows"]:
            m = r["mention"]
            rows.append({"post_id": p["id"], "username": p["username"], "status": r["status"], "method": r["method"] or "",
                         "product_id": r["product_id"] or "", "product_name": byid.get(r["product_id"], {}).get("name", ""),
                         "brand": m.get("brand") or "", "extracted": m.get("product_name") or "", "category": m.get("category") or "",
                         "mention_type": m["mention_type"], "specificity": m["specificity"], "evidence": m["evidence"],
                         "reason": r["reason"], "candidates": " | ".join(f"{c['name']}({c['name_score']:.0f}/{c['embed_score']:.2f})" for c in r["candidates"]),
                         "llm_choice": r.get("llm_choice") or "" if isinstance(r.get("llm_choice"), str) else "",
                         "llm_choice_name": byid.get(r.get("llm_choice") or "", {}).get("name", "") if isinstance(r.get("llm_choice"), str) else "",
                         # v1.1 은 판정 LLM 을 부른 줄만 다르다. 나머지는 v1 과 같다
                         "status_v1_1": (r.get("v1_1") or {}).get("status", r["status"]),
                         "product_id_v1_1": (r.get("v1_1") or {}).get("product_id", r["product_id"]) or "",
                         "reason_v1_1": (r.get("v1_1") or {}).get("reason", "")})
    fields = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0].keys()).index(k) if k in rows[0] else 99)
    with (out / "rows.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

    matched = [r for r in rows if r["status"] == MATCHED]
    pairs = {(r["post_id"], r["product_id"]) for r in matched}
    authors = defaultdict(set)
    for r in matched:
        authors[r["product_id"]].add(r["username"])

    # 미등록 제품: product 언급인데 DB 와 잇지 못한 것
    unreg = defaultdict(lambda: {"authors": set(), "posts": set(), "brand": "", "name": "", "category": ""})
    for r in rows:
        if r["mention_type"] == "product" and r["status"] in ("unmatched", "review"):
            u = unreg[_key(r["brand"], r["extracted"])]
            u["authors"].add(r["username"]); u["posts"].add(r["post_id"])
            u["brand"], u["name"], u["category"] = u["brand"] or r["brand"], u["name"] or r["extracted"], u["category"] or r["category"]
    unreg_rows = sorted(({"brand": v["brand"], "product_name": v["name"], "category": v["category"], "authors": len(v["authors"]),
                          "posts": len(v["posts"]), "status_note": "카테고리 범위 밖" if v["category"] == "other" else ""}
                         for v in unreg.values()), key=lambda x: (-x["authors"], -x["posts"]))
    with (out / "unregistered.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(unreg_rows[0].keys()) if unreg_rows else ["brand"]); w.writeheader(); w.writerows(unreg_rows)

    # 골든셋 초안: 언급이 있는 게시물을 우선, 나머지를 섞어 100건. 사람이 검수해야 정답이 된다
    random.seed(133)
    by_post = defaultdict(list)
    for r in rows:
        by_post[r["post_id"]].append(r)
    with_m = [pid for pid, rs in by_post.items() if any(x["mention_type"] for x in rs)]
    without = [pid for pid in by_post if pid not in with_m]
    pick = sorted(random.sample(with_m, min(len(with_m), int(args.golden * 0.7))) +
                  random.sample(without, min(len(without), args.golden - min(len(with_m), int(args.golden * 0.7)))))
    caps = {p["id"]: p for p in posts}
    with (out / "golden_draft.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for n, pid in enumerate(pick, 1):
            rs = by_post[pid]
            f.write(json.dumps({
                "id": f"trend-g-m{n:04d}", "split": "test" if n % 2 else "dev", "source": "real", "tags": ["product_match", "draft"],
                "note": "v1 추출 결과 초안. 검수 전에는 정답이 아니다",
                "input": {"post_id": pid, "username": caps[pid]["username"], "caption": caps[pid]["caption"]},
                "expected": {"mentions": [{"brand": x["brand"], "product_name": x["extracted"], "mention_type": x["mention_type"],
                                           "product_id": x["product_id"] or None} for x in rs if x["mention_type"]]},
                "check": "exact",
            }, ensure_ascii=False) + "\n")

    m11 = [r for r in rows if r["status_v1_1"] == MATCHED]
    a11 = defaultdict(set)
    for r in m11:
        a11[r["product_id_v1_1"]].add(r["username"])
    changed = [{"post_id": r["post_id"], "extracted": r["extracted"], "v1": r["status"], "v1_1": r["status_v1_1"],
                "product": byid.get(r["product_id_v1_1"], {}).get("name", ""), "reason_v1_1": r["reason_v1_1"]}
               for r in rows if (r["status"], r["product_id"]) != (r["status_v1_1"], r["product_id_v1_1"])]
    v1_1 = {"version": "match-v1.1", "status": dict(Counter(r["status_v1_1"] for r in rows)),
            "posts_with_match": len({r["post_id"] for r in m11}), "matched_pairs": len({(r["post_id"], r["product_id_v1_1"]) for r in m11}),
            "products_matched": len(a11), "products_2plus_authors": sum(1 for a in a11.values() if len(a) >= 2),
            "changed_from_v1": changed}

    n = len(results)
    summary = {
        "version": {"match": MATCH_V1_VERSION, "extract": EXTRACT_VERSION, "verify": VERIFY_VERSION},
        "posts": n, "errors": len(errors), "extract_failed": failed, "extract_cached": cached,
        "mentions": dict(Counter(r["mention_type"] or "none" for r in rows)),
        "status": dict(Counter(r["status"] for r in rows)),
        "method": dict(Counter(r["method"] for r in matched)),
        "v1": {"posts_with_match": len({r["post_id"] for r in matched}), "matched_pairs": len(pairs),
               "products_matched": len(authors), "products_2plus_authors": sum(1 for a in authors.values() if len(a) >= 2)},
        "v0_1": base,
        "v1_1": v1_1,
        "unregistered_products": len(unreg_rows), "unregistered_2plus_authors": sum(1 for u in unreg_rows if u["authors"] >= 2),
        "usage": usage, "cost_usd_est": round(usage["prompt_tokens"] / 1e6 * PRICE_IN + usage["completion_tokens"] / 1e6 * PRICE_OUT, 4),
        "elapsed_s": round(elapsed, 1), "error_samples": errors[:5],
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
