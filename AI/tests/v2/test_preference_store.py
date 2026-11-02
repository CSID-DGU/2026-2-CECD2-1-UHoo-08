"""저장소의 조회와 갱신이 그 사용자, 그 행으로 좁혀지는지 본다.

조건을 빠뜨린 갱신은 에러 없이 다른 사용자의 값까지 덮는다.
"""
import sys
import types
from datetime import datetime, timezone

import pytest

from services import preference_store

지금 = datetime(2026, 11, 3, tzinfo=timezone.utc)


class 가짜쿼리:
    def __init__(self, 기록, 이름, 돌려줄):
        self.기록 = 기록
        self.기록["table"] = 이름
        self.돌려줄 = 돌려줄

    def __getattr__(self, 동작):
        def 부름(*인자, **이름인자):
            self.기록.setdefault(동작, []).append(인자 + tuple(이름인자.values()))
            return self

        return 부름

    def execute(self):
        return types.SimpleNamespace(data=self.돌려줄)


@pytest.fixture
def DB(monkeypatch):
    def 세우기(돌려줄=None):
        기록: dict = {}

        def get_supabase():
            return types.SimpleNamespace(table=lambda 이름: 가짜쿼리(기록, 이름, 돌려줄))

        import db
        모듈 = types.SimpleNamespace(get_supabase=get_supabase)
        monkeypatch.setitem(sys.modules, "db.supabase_client", 모듈)
        monkeypatch.setattr(db, "supabase_client", 모듈, raising=False)
        return 기록

    return 세우기


@pytest.mark.asyncio
async def test_반영_전_피드백은_그_사용자의_것만_읽는다(DB):
    기록 = DB([{"id": 1}, {"id": 2}])
    assert await preference_store.load_unapplied_feedback_ids("u1") == [1, 2]
    assert ("user_id", "u1") in 기록["eq"]
    assert ("applied_at", "null") in 기록["is_"]


@pytest.mark.asyncio
async def test_반영_시각은_아직_반영_전일_때만_채운다(DB):
    기록 = DB([{"id": 1, "vote": "UP"}])
    assert await preference_store.claim_feedback(1, 지금) == {"id": 1, "vote": "UP"}
    assert 기록["update"] == [({"applied_at": 지금.isoformat()},)]
    assert 기록["eq"] == [("id", 1)]
    assert ("applied_at", "null") in 기록["is_"]


@pytest.mark.asyncio
async def test_이미_가져간_피드백이면_None이다(DB):
    DB([])
    assert await preference_store.claim_feedback(1, 지금) is None


@pytest.mark.asyncio
async def test_이전_변경은_그_피드백의_것만_뺀다(DB):
    기록 = DB([])
    await preference_store.retire_feedback_changes("u1", 7, 지금)
    assert 기록["table"] == "preference_weight_changes"
    assert set(기록["eq"]) == {("user_id", "u1"), ("source", "FEEDBACK"), ("source_ref", "7")}
    assert ("reverted_at", "null") in 기록["is_"]


@pytest.mark.asyncio
async def test_조건_수정이_없는_job은_빼고_돌려준다(DB):
    기록 = DB([{"refine_presets": ["CHEAPER"]}, {"refine_presets": None}, {"refine_presets": []}])
    assert await preference_store.load_refine_presets_since("u1", 지금) == [["CHEAPER"]]
    assert 기록["eq"] == [("user_id", "u1")]
    assert 기록["gte"] == [("created_at", 지금.isoformat())]


@pytest.mark.asyncio
async def test_합산에는_되돌리지_않은_그_사용자의_변경만_읽는다(DB):
    기록 = DB([{"source": "FEEDBACK", "deltas": {}}])
    await preference_store.load_active_changes("u1")
    assert 기록["eq"] == [("user_id", "u1")]
    assert ("reverted_at", "null") in 기록["is_"]


@pytest.mark.asyncio
async def test_가중치는_사용자당_한_줄로_쓴다(DB):
    기록 = DB([])
    await preference_store.save_weights("u1", {"review": 0.3}, {"feedback": 1}, 지금)
    행, 충돌 = 기록["upsert"][0]
    assert 행["user_id"] == "u1" and 행["weights"] == {"review": 0.3}
    assert 충돌 == "user_id"
