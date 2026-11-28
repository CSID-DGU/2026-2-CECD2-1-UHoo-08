"""키워드 트렌드 일일 배치. 게시물 · 상품을 읽어 product_trend_daily 에 그날 점수를 넣는다.

계산은 rules/keyword_trend.py 가 한다. 여기서는 DB 를 읽고 쓰기만 한다.
같은 날짜로 다시 돌리면 그날 행을 덮어쓴다. 이번 계산에서 점수가 없어진 제품의
그날 행은 지운다. 남겨 두면 지난 계산의 점수가 순위에 섞인다.

인스타 수집 스케줄(services/influencer_collector.run_schedule)이 수집 뒤에 부른다.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from rules.keyword_extract import load_keywords
from rules.keyword_trend_daily import FORMULA_VERSION, Post, daily_rows, daily_scores

logger = logging.getLogger(__name__)

PAGE = 1000
KST = timezone(timedelta(hours=9))  # 배치 기준일과 같은 날짜 기준


def _all(query_fn) -> list[dict]:
    rows, start = [], 0
    while True:
        batch = query_fn().range(start, start + PAGE - 1).execute().data or []
        rows += batch
        if len(batch) < PAGE:
            return rows
        start += PAGE


def _int(v) -> int | None:
    return None if v is None else int(v)


def kst_date(ts) -> date:
    """저장된 타임스탬프 → KST 날짜. 시간대가 없으면 UTC 로 본다."""
    dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).date()


def load_posts(sb) -> list[Post]:
    accounts = {a["id"]: a for a in _all(lambda: sb.table("influencer_accounts").select("id,username,follower_count,age_group"))}
    rows = _all(lambda: sb.table("influencer_posts")
                .select("id,account_id,caption,posted_at,like_count,comment_count,is_ad").order("id"))
    posts = []
    for r in rows:
        a = accounts.get(r["account_id"]) or {}
        posts.append(Post(
            post_id=str(r["id"]), author=a.get("username") or str(r["account_id"]), caption=r.get("caption"),
            posted_at=kst_date(r["posted_at"]),
            followers=_int(a.get("follower_count")), like_count=_int(r.get("like_count")),
            comment_count=_int(r.get("comment_count")), is_ad=r.get("is_ad"), age_group=a.get("age_group"),
        ))
    return posts


def compute(sb, as_of: date) -> dict:
    """DB 를 읽어 계산만 한다. 쓰지 않는다."""
    d = load_keywords()
    posts = load_posts(sb)
    products = _all(lambda: sb.table("products").select("product_id,name,brand,category,feature_json").order("product_id"))
    trends, scores = daily_scores(posts, products, d, as_of)
    return {"as_of": as_of, "dictionary": d, "posts": posts, "trends": trends, "scores": scores,
            "rows": daily_rows(scores, as_of)}


def write(sb, result: dict) -> dict:
    """그날 행을 덮어쓰고, 이번에 점수가 없는 제품의 그날 행은 지운다."""
    day = result["as_of"].isoformat()
    now = datetime.now(timezone.utc).isoformat()
    rows = [{**r, "updated_at": now} for r in result["rows"]]
    keep = {r["product_id"] for r in rows}
    existing = {r["product_id"] for r in _all(lambda: sb.table("product_trend_daily").select("product_id").eq("date", day))}
    stale = sorted(existing - keep)
    for i in range(0, len(rows), 500):
        sb.table("product_trend_daily").upsert(rows[i:i + 500], on_conflict="product_id,date").execute()
    for i in range(0, len(stale), 100):
        sb.table("product_trend_daily").delete().eq("date", day).in_("product_id", stale[i:i + 100]).execute()
    return {"date": day, "upserted": len(rows), "deleted": len(stale), "formula_version": FORMULA_VERSION}


def run(as_of: date | None = None) -> dict:
    from db.supabase_client import get_supabase
    sb = get_supabase()
    as_of = as_of or datetime.now(KST).date()
    result = compute(sb, as_of)
    summary = write(sb, result)
    summary["keywords_ranked"] = sum(1 for t in result["trends"] if t.rank)
    logger.info("키워드 트렌드 저장: %s", summary)
    return summary
