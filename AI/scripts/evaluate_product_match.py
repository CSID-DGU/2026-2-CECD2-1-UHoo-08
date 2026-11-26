"""ProductMatcher v0 실험: 수집한 인스타 게시물을 상품 마스터와 매칭해 CSV 로 낸다.

DB 는 읽기만 한다. influencer_post_products 에 쓰지 않는다. 임계값을 바꿔 가며
다시 돌려도 기존 데이터가 오염되지 않게 하려는 것이다.

    cd AI
    python -m scripts.evaluate_product_match --out match_v0.csv
    python -m scripts.evaluate_product_match --out match_v0.csv --samples 15

CSV 한 줄 = 게시물 × 제품 후보 하나. 후보가 없는 게시물은 product_id 가 빈 unmatched 한 줄.
지표의 "게시물 매칭률"은 Recall 이 아니다. 실제로 제품을 언급한 게시물 중 몇 개를
찾았는지는 정답 라벨이 있어야 알 수 있다.
"""
from __future__ import annotations

import argparse
import csv
import random
from collections import Counter, defaultdict

from rules.product_match import (
    MATCH_VERSION, MATCHED, REVIEW, UNMATCHED, brand_from_handle, brand_prefixes, find_handles, match_caption,
)


def _load():
    from db.supabase_client import get_supabase

    sb = get_supabase()
    products = sb.table("products").select("product_id,brand,name,category").execute().data or []
    accounts = {a["id"]: a["username"] for a in sb.table("influencer_accounts").select("id,username").execute().data or []}
    posts = sb.table("influencer_posts").select("id,account_id,platform_post_id,caption,posted_at").execute().data or []
    for p in posts:
        p["username"] = accounts.get(p["account_id"], "")
    return products, posts


def link_handles(products: list[dict], posts: list[dict]) -> tuple[dict[str, str], Counter]:
    """전체 캡션의 공식 계정명 → 브랜드. 잇지 못한 계정명은 빈도와 함께 따로 돌려준다."""
    brands = sorted({p.get("brand") or "" for p in products} - {""})
    seen = Counter(h for post in posts for h in set(find_handles(post.get("caption") or "")))
    linked = {h: b for h in seen if (b := brand_from_handle(h, brands))}
    return linked, Counter({h: n for h, n in seen.items() if h not in linked})


def run(products: list[dict], posts: list[dict], handle_brands: dict[str, str] | None = None) -> list[dict]:
    prefixes = brand_prefixes(products)
    handle_brands = handle_brands if handle_brands is not None else link_handles(products, posts)[0]
    rows = []
    for post in posts:
        cands = match_caption(post.get("caption") or "", products, prefixes, handle_brands)
        base = {"post_id": post["id"], "username": post["username"], "posted_at": (post.get("posted_at") or "")[:10]}
        if not cands:
            rows.append({**base, "product_id": "", "product_name": "", "score": 0, "status": UNMATCHED,
                         "matched_text": "", "reason": "", "brand_confirmed": "", "missing": "", "family": "", "caption_head": (post.get("caption") or "")[:80].replace("\n", " / ")})
            continue
        for c in cands:
            rows.append({**base, "product_id": c.product_id, "product_name": c.name, "score": round(c.score, 1),
                         "status": c.status, "matched_text": c.matched_text, "reason": c.reason,
                         "brand_confirmed": c.brand_confirmed, "missing": " ".join(c.missing),
                         "family": ";".join(c.family), "caption_head": ""})
    return rows


def summarize(rows: list[dict], n_posts: int) -> dict:
    by_post = defaultdict(set)
    for r in rows:
        by_post[r["post_id"]].add(r["status"])
    matched_posts = sum(1 for s in by_post.values() if MATCHED in s)
    review_only = sum(1 for s in by_post.values() if MATCHED not in s and REVIEW in s)
    authors = defaultdict(set)
    for r in rows:
        if r["status"] == MATCHED:
            authors[r["product_name"]].add(r["username"])
    return {
        "version": MATCH_VERSION,
        "posts": n_posts,
        "posts_with_match": matched_posts,
        "post_match_rate": round(matched_posts / n_posts, 3) if n_posts else 0,
        "matched_pairs": sum(1 for r in rows if r["status"] == MATCHED),
        "posts_review_only": review_only,
        "posts_unmatched": n_posts - matched_posts - review_only,
        "products_matched": len(authors),
        "products_2plus_authors": sum(1 for a in authors.values() if len(a) >= 2),
        "authors_per_product": sorted(((len(a), name) for name, a in authors.items()), reverse=True),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="match_v0.csv")
    parser.add_argument("--samples", type=int, default=0, help="상태별로 보여 줄 사례 수")
    args = parser.parse_args()

    products, posts = _load()
    handle_brands, unlinked = link_handles(products, posts)
    rows = run(products, posts, handle_brands)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    s = summarize(rows, len(posts))
    print(f"[{s['version']}] 게시물 {s['posts']}개 · 제품 {len(products)}개 → {args.out}")
    print(f"  자동 매칭된 게시물 {s['posts_with_match']} ({s['post_match_rate']:.1%}), 게시물×제품 {s['matched_pairs']}쌍")
    print(f"  검토만 있는 게시물 {s['posts_review_only']}, 미매칭 게시물 {s['posts_unmatched']}")
    print(f"  자동 매칭된 제품 {s['products_matched']}개 (작성자 수 상위): {s['authors_per_product'][:10]}")
    print(f"  작성자 2명 이상이 언급한 제품 {s['products_2plus_authors']}개")
    print(f"  상태별 행: {dict(Counter(r['status'] for r in rows))}")
    print(f"  공식 계정명 → 브랜드 연결 {len(handle_brands)}개: {sorted(handle_brands.items())}")
    print(f"  연결 못 한 계정명 {len(unlinked)}개 (DB 에 없는 브랜드거나 표기가 다름): {unlinked.most_common(40)}")

    if args.samples:
        random.seed(0)
        for status in (MATCHED, REVIEW, UNMATCHED):
            pool = [r for r in rows if r["status"] == status]
            print(f"\n── {status} 사례 {min(args.samples, len(pool))}/{len(pool)}")
            for r in random.sample(pool, min(args.samples, len(pool))):
                if status == UNMATCHED:
                    print(f"  #{r['post_id']} @{r['username']}: {r['caption_head']}")
                else:
                    print(f"  #{r['post_id']} {r['score']:>5} {r['product_name']} ← \"{r['matched_text']}\"  ({r['reason']})")


if __name__ == "__main__":
    main()
