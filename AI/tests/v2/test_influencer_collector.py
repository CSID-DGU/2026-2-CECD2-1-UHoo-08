"""인플루언서 수집의 파싱·페이지 넘김. Graph API 와 DB 없이 돈다."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from services.influencer_collector import (
    ACCOUNTS_PATH,
    AGE_GROUPS,
    KST,
    _next_run,
    fetch_recent_media,
    load_accounts,
    to_post_row,
)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def _media(post_id: str, days_ago: int) -> dict:
    ts = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    return {"id": post_id, "caption": f"캡션 {post_id}", "timestamp": ts,
            "like_count": 10, "comments_count": 2, "permalink": f"https://instagram.com/p/{post_id}"}


def _getter(pages: list[list[dict]]):
    """페이지 목록을 차례로 돌려주는 가짜 get. 받은 fields 를 기록한다."""
    calls = []

    def get(fields: str) -> dict:
        i = len(calls)
        calls.append(fields)
        media = {"data": pages[i]}
        if i + 1 < len(pages):
            media["paging"] = {"cursors": {"after": f"CUR{i + 1}"}}
        return {"business_discovery": {"username": "u", "followers_count": 100, "media": media}}

    return get, calls


def test_수집_목록은_전부_알려진_연령대이고_중복이_없다():
    accounts = load_accounts()
    names = [a["username"] for a in accounts]
    assert len(names) == len(set(names))
    assert {a["age_group"] for a in accounts} <= set(AGE_GROUPS.values())
    raw = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
    assert all(item["username"].strip() for item in raw)


def test_since_보다_오래된_페이지에서_멈춘다():
    get, calls = _getter([
        [_media("a", 1), _media("b", 3)],
        [_media("c", 10), _media("d", 20)],
        [_media("e", 30)],
    ])
    profile, posts = fetch_recent_media("u", NOW - timedelta(days=14), get)

    assert [p["id"] for p in posts] == ["a", "b", "c"]
    assert len(calls) == 2
    assert ".after(CUR1)" in calls[1]
    assert profile["followers_count"] == 100
    assert "media" not in profile


def test_맨_앞의_오래된_고정_게시물_때문에_멈추지_않는다():
    get, calls = _getter([
        [_media("pinned", 400), _media("a", 1), _media("b", 2)],
        [_media("c", 5), _media("d", 20)],
    ])
    _, posts = fetch_recent_media("u", NOW - timedelta(days=14), get)

    assert [p["id"] for p in posts] == ["a", "b", "c"]
    assert len(calls) == 2


def test_좋아요를_숨긴_게시물은_0이_아니라_None():
    media = _media("x", 1)
    del media["like_count"]
    row = to_post_row(7, media)

    assert row["like_count"] is None
    assert row["comment_count"] == 2
    assert row["platform_post_id"] == "x"
    assert row["raw"] is media
    # 광고 판별 결과를 덮지 않도록 보내지 않는다
    assert "is_ad" not in row and "ad_rule_hits" not in row


@pytest.mark.parametrize("now_kst, expected", [
    (datetime(2026, 10, 29, 5, 30, tzinfo=KST), datetime(2026, 10, 29, 6, 0, tzinfo=KST)),
    (datetime(2026, 10, 29, 6, 0, tzinfo=KST), datetime(2026, 10, 29, 18, 0, tzinfo=KST)),
    (datetime(2026, 10, 29, 19, 0, tzinfo=KST), datetime(2026, 10, 30, 6, 0, tzinfo=KST)),
])
def test_다음_수집_시각(now_kst, expected):
    assert _next_run(now_kst, [18, 6]) == expected
