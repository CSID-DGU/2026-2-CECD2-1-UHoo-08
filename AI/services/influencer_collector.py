"""
인플루언서 인스타그램 게시물 수집.

Instagram Graph API 의 business_discovery 로 다른 계정의 공개 게시물을 읽어
influencer_accounts · influencer_posts 에 쌓는다. 이 데이터는 소급해서 모을 수
없으므로 하루 몇 번 배치로 돌린다 (027_influencer.sql 참고).

수집 대상은 data/influencer_accounts.json 이 정한다. 목록에서 빠진 계정은
지우지 않고 active=false 로 둔다. 이미 모은 게시물과 트렌드 계산이 그 계정을
참조하기 때문이다.

같은 게시물을 여러 번 읽어도 (account_id, platform_post_id) 로 덮어쓰므로
중복이 생기지 않는다. 최근 게시물은 다시 읽어 좋아요·댓글 수를 갱신한다.
is_ad · ad_rule_hits 는 보내지 않으므로 광고 판별 결과는 덮이지 않는다.

config · DB 는 함수 안에서 import 한다. 파싱·페이지 넘김 로직은 키 없이
테스트할 수 있어야 한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

ACCOUNTS_PATH = Path(__file__).resolve().parent.parent / "data" / "influencer_accounts.json"

# 노션 인플루언서 리스트의 표기 → influencer_accounts.age_group (10s|20s|30s+)
AGE_GROUPS = {"10대": "10s", "20대": "20s", "30대": "30s+", "40대이상": "30s+"}

MEDIA_FIELDS = "id,caption,like_count,comments_count,timestamp,permalink,media_type"
# 한 번에 받는 게시물 수. 크게 잡을수록 호출 수가 줄어든다.
PAGE_SIZE = 50
# 계정당 최대 페이지. 게시물을 매일 올리는 계정이라도 2주치는 1~2페이지다.
# 호출 횟수 제한이 있어 한 계정이 배치 전체를 잡아먹지 않게 막는다.
MAX_PAGES = 4
# 이만큼 지난 게시물까지 다시 읽어 반응 수를 갱신한다.
DEFAULT_LOOKBACK_DAYS = 14

# 호출 한도 초과. 이 뒤로는 어느 계정을 불러도 실패하므로 배치를 멈춘다.
RATE_LIMIT_CODES = {4, 17, 32, 613, 80002}

KST = timezone(timedelta(hours=9))


class InstagramApiError(Exception):
    def __init__(self, code: int | None, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code

    @property
    def rate_limited(self) -> bool:
        return self.code in RATE_LIMIT_CODES


def load_accounts(path: Path = ACCOUNTS_PATH) -> list[dict]:
    """수집 대상 목록을 읽어 influencer_accounts 행 모양으로 바꾼다."""
    rows = []
    for item in json.loads(path.read_text(encoding="utf-8")):
        age = item["age_group"]
        if age not in AGE_GROUPS:
            raise ValueError(f"{item['username']}: 알 수 없는 연령대 {age!r}")
        rows.append({
            "platform": "instagram",
            "username": item["username"],
            "age_group": AGE_GROUPS[age],
            "focus": [item["focus"]],
        })
    return rows


def _discovery_fields(username: str, after: str | None) -> str:
    media = "media"
    if after:
        media += f".after({after})"
    media += f".limit({PAGE_SIZE}){{{MEDIA_FIELDS}}}"
    return f"business_discovery.username({username}){{username,name,followers_count,media_count,{media}}}"


def _parse_timestamp(value: str) -> datetime:
    # Graph API 는 "2026-10-28T09:00:00+0000" 형식으로 준다
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")


def fetch_recent_media(
    username: str,
    since: datetime,
    get: Callable[[str], dict],
) -> tuple[dict, list[dict]]:
    """since 이후 게시물을 페이지를 넘기며 모은다.

    get 은 fields 문자열을 받아 응답 JSON 을 돌려준다. 고정 게시물은 오래돼도
    맨 앞에 올 수 있어서, 첫 오래된 게시물에서 멈추지 않고 페이지의 마지막
    (가장 오래된) 게시물이 since 보다 오래됐을 때 멈춘다.
    """
    profile: dict = {}
    posts: list[dict] = []
    after = None
    for _ in range(MAX_PAGES):
        discovery = get(_discovery_fields(username, after))["business_discovery"]
        profile = {k: v for k, v in discovery.items() if k != "media"}
        media = discovery.get("media", {})
        page = media.get("data", [])
        posts += [m for m in page if _parse_timestamp(m["timestamp"]) >= since]

        after = media.get("paging", {}).get("cursors", {}).get("after")
        if not page or not after or _parse_timestamp(page[-1]["timestamp"]) < since:
            break
    return profile, posts


def to_post_row(account_id: int, media: dict) -> dict:
    return {
        "account_id": account_id,
        "platform_post_id": media["id"],
        "caption": media.get("caption"),
        "permalink": media.get("permalink"),
        "posted_at": _parse_timestamp(media["timestamp"]).isoformat(),
        # 좋아요 수를 숨긴 게시물은 like_count 가 오지 않는다. 0 과 구분한다.
        "like_count": media.get("like_count"),
        "comment_count": media.get("comments_count"),
        "raw": media,
    }


def _graph_getter(client: httpx.Client) -> Callable[[str], dict]:
    from config import settings

    url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/{settings.META_IG_USER_ID}"

    def get(fields: str) -> dict:
        resp = client.get(url, params={"fields": fields, "access_token": settings.META_PAGE_ACCESS_TOKEN})
        body = resp.json()
        if "error" in body:
            err = body["error"]
            raise InstagramApiError(err.get("code"), err.get("message", ""))
        resp.raise_for_status()
        return body

    return get


def collect(lookback_days: int = DEFAULT_LOOKBACK_DAYS, accounts_path: Path = ACCOUNTS_PATH) -> dict:
    """목록의 모든 계정을 수집한다. 계정 하나가 실패해도 나머지는 계속한다.

    비공개 전환·아이디 변경·개인 계정 전환은 계정마다 따로 일어나므로,
    한 계정 때문에 그날 수집 전체를 잃지 않는다. 실패한 계정은 반환값의
    failed 에 남긴다. 호출 한도에 걸리면 남은 계정은 건너뛴다.
    """
    from db.supabase_client import get_supabase

    sb = get_supabase()
    accounts = load_accounts(accounts_path)
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    now = datetime.now(timezone.utc).isoformat()

    saved = sb.table("influencer_accounts").upsert(
        [{**a, "active": True, "updated_at": now} for a in accounts],
        on_conflict="platform,username",
    ).execute().data
    account_ids = {row["username"]: row["id"] for row in saved}

    listed = list(account_ids)
    sb.table("influencer_accounts").update({"active": False, "updated_at": now}) \
        .eq("platform", "instagram").eq("active", True) \
        .not_.in_("username", listed).execute()

    summary: dict[str, Any] = {"accounts": len(accounts), "posts": 0, "failed": {}}
    with httpx.Client(timeout=30) as client:
        get = _graph_getter(client)
        for i, account in enumerate(accounts):
            username = account["username"]
            try:
                profile, media = fetch_recent_media(username, since, get)
            except InstagramApiError as e:
                logger.error("인스타 수집 실패 %s: %s", username, e)
                summary["failed"][username] = str(e)
                if e.rate_limited:
                    for rest in accounts[i + 1:]:
                        summary["failed"][rest["username"]] = "호출 한도 초과로 건너뜀"
                    break
                continue
            except httpx.HTTPError as e:
                logger.error("인스타 수집 실패 %s: %s", username, e)
                summary["failed"][username] = str(e)
                continue

            account_id = account_ids[username]
            sb.table("influencer_accounts").update({
                "display_name": profile.get("name"),
                "follower_count": profile.get("followers_count"),
                "updated_at": now,
            }).eq("id", account_id).execute()

            if media:
                sb.table("influencer_posts").upsert(
                    [to_post_row(account_id, m) for m in media],
                    on_conflict="account_id,platform_post_id",
                ).execute()
            summary["posts"] += len(media)

    logger.info("인스타 수집 완료: %s", summary)
    return summary


def _next_run(now: datetime, hours: list[int]) -> datetime:
    """now 이후 가장 가까운 수집 시각 (KST 정각)."""
    local = now.astimezone(KST)
    for day in range(2):
        base = (local + timedelta(days=day)).replace(minute=0, second=0, microsecond=0)
        for h in sorted(hours):
            candidate = base.replace(hour=h)
            if candidate > local:
                return candidate
    raise ValueError(f"수집 시각이 비어 있다: {hours}")


async def run_schedule() -> None:
    """INFLUENCER_COLLECT_HOURS 의 KST 시각마다 수집한다. 앱 시작 시 띄운다."""
    from config import settings

    hours = [int(h) for h in settings.INFLUENCER_COLLECT_HOURS.split(",") if h.strip()]
    if not hours or not settings.META_PAGE_ACCESS_TOKEN or not settings.META_IG_USER_ID:
        logger.info("인스타 수집 스케줄 꺼짐 (시각 또는 토큰 없음)")
        return

    while True:
        at = _next_run(datetime.now(timezone.utc), hours)
        logger.info("다음 인스타 수집: %s", at.isoformat())
        await asyncio.sleep((at - datetime.now(KST)).total_seconds())
        try:
            await asyncio.to_thread(collect)
        except Exception:
            # 배치 하나가 실패해도 다음 시각에는 다시 돌아야 한다
            logger.exception("인스타 수집 배치 실패")
