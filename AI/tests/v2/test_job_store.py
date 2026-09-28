"""스냅샷 저장·조회가 실제로 그 job 만 건드리는지 본다.

job_id 를 빠뜨린 갱신은 에러 없이 테이블 전체를 덮는다. 그때는 다른
사용자의 결과까지 사라진다.
"""
import sys
import types

import pytest

from services import job_store


class 가짜테이블:
    def __init__(self, 기록, 돌려줄):
        self.기록 = 기록
        self.돌려줄 = 돌려줄

    def update(self, payload):
        self.기록["update"] = payload
        return self

    def select(self, columns):
        self.기록["select"] = columns
        return self

    def eq(self, 칼럼, 값):
        self.기록.setdefault("eq", []).append((칼럼, 값))
        return self

    def limit(self, n):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self.돌려줄)


@pytest.fixture
def DB(monkeypatch):
    def 세우기(돌려줄=None):
        기록: dict = {}

        def get_supabase():
            return types.SimpleNamespace(table=lambda 이름: 가짜테이블(기록, 돌려줄))

        모듈 = types.SimpleNamespace(get_supabase=get_supabase)
        import db
        monkeypatch.setitem(sys.modules, "db.supabase_client", 모듈)
        monkeypatch.setattr(db, "supabase_client", 모듈, raising=False)
        return 기록

    return 세우기


@pytest.mark.asyncio
async def test_그_job만_갱신한다(DB):
    기록 = DB()
    await job_store.save_snapshot("j1", {"raw_query": "쿠션"})

    assert 기록["update"] == {"state_snapshot": {"raw_query": "쿠션"}}
    assert 기록["eq"] == [("id", "j1")]


@pytest.mark.asyncio
async def test_읽으면_상태와_스냅샷이_같이_온다(DB):
    DB([{"id": "j1", "user_id": "u1", "status": "NEEDS_CLARIFICATION",
         "state_snapshot": {"raw_query": "세트"}}])
    job = await job_store.load_job("j1")

    assert job["status"] == "NEEDS_CLARIFICATION"
    assert job["state_snapshot"]["raw_query"] == "세트"


@pytest.mark.asyncio
async def test_없는_job은_None이다(DB):
    """없는 job 에 빈 dict 을 돌려주면 부른 쪽이 정상으로 읽고 진행한다."""
    DB([])
    assert await job_store.load_job("없음") is None
