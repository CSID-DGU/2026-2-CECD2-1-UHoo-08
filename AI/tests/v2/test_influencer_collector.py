"""인플루언서 수집의 파싱·페이지 넘김. Graph API 와 DB 없이 돈다."""
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from services.influencer_collector import (
    ACCOUNTS_PATH,
    AGE_GROUPS,
    KST,
    InstagramApiError,
    _next_run,
    collect_accounts,
    fetch_recent_media,
    load_accounts,
    make_getter,
    parse_collect_hours,
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


class _FakeTable:
    def __init__(self, db, name):
        self.db, self.name, self.row = db, name, None

    def update(self, row):
        self.row = row
        return self

    def upsert(self, rows, on_conflict):
        self.row = rows
        return self

    def eq(self, column, value):
        return self

    def execute(self):
        if self.name in self.db.fail_tables and self.db.fail_on(self.row):
            raise RuntimeError("DB 일시 오류")
        self.db.writes.append((self.name, self.row))
        return self


class _FakeDB:
    """특정 계정의 게시물 저장만 실패하는 가짜 Supabase."""

    def __init__(self, fail_account_id=None):
        self.writes = []
        self.fail_tables = {"influencer_posts"}
        self.fail_on = lambda rows: any(r["account_id"] == fail_account_id for r in rows)

    def table(self, name):
        return _FakeTable(self, name)


def _all_accounts_getter(fields: str) -> dict:
    return {"business_discovery": {"username": "u", "media": {"data": [_media("p", 1)]}}}


def test_한_계정의_DB_저장이_실패해도_다음_계정을_수집한다():
    accounts = [{"username": "a"}, {"username": "b"}, {"username": "c"}]
    db = _FakeDB(fail_account_id=2)
    summary = collect_accounts(accounts, {"a": 1, "b": 2, "c": 3}, NOW - timedelta(days=14),
                               NOW.isoformat(), _all_accounts_getter, db)

    assert summary["posts"] == 2
    assert list(summary["failed"]) == ["b"]
    assert summary["failed"]["b"].startswith("저장 실패")
    saved = [rows[0]["account_id"] for name, rows in db.writes if name == "influencer_posts"]
    assert saved == [1, 3]


def test_수집_시각을_정렬하고_중복을_뺀다():
    assert parse_collect_hours("18, 6,,6") == [6, 18]
    assert parse_collect_hours("") == []


@pytest.mark.parametrize("value", ["24,18", "6,-1", "6,오후", "6.5"])
def test_잘못된_수집_시각은_시작할_때_막는다(value):
    with pytest.raises(ValueError, match="0~23"):
        parse_collect_hours(value)


def _getter_over(handler):
    """가짜 서버 응답으로 실제 get 을 만든다."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return make_getter(client, "https://graph.test/v1/1", "TOKEN")


def test_토큰은_URL_이_아니라_헤더로_보낸다():
    seen = {}

    def handler(request):
        seen["url"], seen["auth"] = str(request.url), request.headers.get("authorization")
        return httpx.Response(200, json={"business_discovery": {}})

    _getter_over(handler)("username")
    assert "TOKEN" not in seen["url"]
    assert seen["auth"] == "Bearer TOKEN"


def test_JSON_이_아닌_응답은_API_오류로_올린다():
    get = _getter_over(lambda request: httpx.Response(502, text="<html>Bad Gateway</html>"))
    with pytest.raises(InstagramApiError, match="JSON"):
        get("username")


@pytest.mark.parametrize("body", [{}, {"business_discovery": None}])
def test_business_discovery_가_없으면_API_오류로_올린다(body):
    with pytest.raises(InstagramApiError, match="business_discovery"):
        fetch_recent_media("u", NOW - timedelta(days=14), lambda fields: body)


def test_응답_형식이_이상한_계정만_실패로_남기고_다음_계정을_수집한다():
    def get(fields: str) -> dict:
        return {} if "username(b)" in fields else _all_accounts_getter(fields)

    accounts = [{"username": "a"}, {"username": "b"}, {"username": "c"}]
    summary = collect_accounts(accounts, {"a": 1, "b": 2, "c": 3}, NOW - timedelta(days=14),
                               NOW.isoformat(), get, _FakeDB())

    assert summary["posts"] == 2
    assert list(summary["failed"]) == ["b"]


@pytest.mark.parametrize("response", [
    httpx.Response(429, text="Too Many Requests"),
    httpx.Response(429, json={"message": "slow down"}),
])
def test_HTTP_429_는_본문과_상관없이_호출_한도다(response):
    get = _getter_over(lambda request: response)
    with pytest.raises(InstagramApiError) as e:
        get("username")
    assert e.value.rate_limited


def test_호출_한도에_걸리면_남은_계정은_호출하지_않는다():
    calls = []

    def get(fields: str) -> dict:
        calls.append(fields)
        if "username(b)" in fields:
            raise InstagramApiError(None, "호출 한도 초과 (HTTP 429)", http_status=429)
        return _all_accounts_getter(fields)

    accounts = [{"username": "a"}, {"username": "b"}, {"username": "c"}]
    summary = collect_accounts(accounts, {"a": 1, "b": 2, "c": 3}, NOW - timedelta(days=14),
                               NOW.isoformat(), get, _FakeDB())

    assert len(calls) == 2
    assert summary["failed"]["c"] == "호출 한도 초과로 건너뜀"
