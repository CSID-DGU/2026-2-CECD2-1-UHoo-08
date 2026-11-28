"""광고 판별 배치. 아직 판별하지 않은(is_ad IS NULL) 게시물을 판정해 influencer_posts 에 쓴다.

판정은 services/ad_classifier.classify_post 가 한다(1차 규칙 → 못 정하면 2차 LLM).
2차 응답을 쓸 수 없으면(is_ad=None) 쓰지 않고 넘긴다. 다음 배치에서 다시 대상이 된다.
LLM 호출 자체가 실패한 게시물도 마찬가지로 건너뛰고 개수만 센다. 하나가 실패했다고
나머지 판정을 버리지 않는다.

ad_rule_hits 에는 1차 규칙이 찾은 근거를 "규칙:표기" 로 넣는다(예: disclosure.hashtag:#광고).
인스타 수집 스케줄(services/influencer_collector.run_schedule)이 수집 뒤, 트렌드 계산 전에 부른다.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from pathlib import Path

from services.ad_classifier import classify_post
from services.influencer_collector import ACCOUNTS_PATH

logger = logging.getLogger(__name__)

CONCURRENCY = 4
PAGE = 1000


def _unlabeled(sb) -> list[dict]:
    rows, start = [], 0
    while True:
        batch = (sb.table("influencer_posts").select("id,account_id,caption").is_("is_ad", "null")
                 .order("id").range(start, start + PAGE - 1).execute().data or [])
        rows += batch
        if len(batch) < PAGE:
            return rows
        start += PAGE


def owned_brands(path: Path | None = None) -> dict[str, list[dict] | None]:
    """계정별 운영 브랜드. load_accounts 는 수집 행 모양이라 owned_brands 가 없어 원본을 읽는다."""
    items = json.loads((path or ACCOUNTS_PATH).read_text(encoding="utf-8"))
    return {a["username"]: a.get("owned_brands") for a in items}


def hit_strings(rule_hits: list[dict]) -> list[str]:
    return [f"{h.get('rule')}:{h.get('text')}" for h in rule_hits]


async def label(sb, llm=None, concurrency: int = CONCURRENCY) -> dict:
    owned = owned_brands()
    names = {a["id"]: a["username"] for a in sb.table("influencer_accounts").select("id,username").execute().data or []}
    posts = _unlabeled(sb)
    sem = asyncio.Semaphore(concurrency)
    stats = Counter()

    async def one(p):
        user = names.get(p["account_id"], "")
        async with sem:
            try:
                r = await classify_post(p.get("caption"), user, owned.get(user), llm=llm)
            except Exception:
                logger.exception("광고 판별 호출 실패 post=%s", p["id"])
                stats["call_failed"] += 1
                return
        if r["is_ad"] is None:
            stats["unusable"] += 1
            return
        await asyncio.to_thread(lambda: sb.table("influencer_posts").update(
            {"is_ad": r["is_ad"], "ad_rule_hits": hit_strings(r["rule_hits"])}).eq("id", p["id"]).execute())
        stats[f"{r['labeled_by'].lower()}_{'ad' if r['is_ad'] else 'organic'}"] += 1

    await asyncio.gather(*(one(p) for p in posts))
    summary = {"targets": len(posts), **dict(sorted(stats.items()))}
    logger.info("광고 판별 저장: %s", summary)
    return summary


def run() -> dict:
    from db.supabase_client import get_supabase
    return asyncio.run(label(get_supabase()))
