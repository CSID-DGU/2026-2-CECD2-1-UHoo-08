"""job 갱신이 무엇을 적고 무엇을 건드리지 않는지 본다.

BE 상태 조회는 scenario 를, 검색 기록과 조건 수정 이력은 query_spec 을 읽는다.
값이 없는 인자를 빈 값으로 적으면 앞에서 적어 둔 값이 지워진다.
"""
import importlib
import sys
import types

import pytest


class 가짜테이블:
    def __init__(self, 기록):
        self.기록 = 기록

    def update(self, payload):
        self.기록["update"] = payload
        return self

    def eq(self, 칼럼, 값):
        self.기록["eq"] = (칼럼, 값)
        return self

    def execute(self):
        return types.SimpleNamespace(data=[])


@pytest.fixture
def 갱신(monkeypatch):
    """DB 클라이언트를 가짜로 두고 모듈을 새로 불러온다.

    이 모듈은 최상단에서 DB 클라이언트를 가져오므로, 가짜를 먼저 넣은 뒤
    불러와야 진짜 클라이언트(키 필요)를 건드리지 않는다.
    """
    import db
    import services

    기록: dict = {}
    가짜 = types.SimpleNamespace(
        get_supabase=lambda: types.SimpleNamespace(table=lambda 이름: 가짜테이블(기록))
    )
    monkeypatch.setitem(sys.modules, "db.supabase_client", 가짜)
    monkeypatch.setattr(db, "supabase_client", 가짜, raising=False)
    monkeypatch.delitem(sys.modules, "services.job_updater", raising=False)
    # 새로 불러오면 패키지 속성이 바뀐다. 끝나면 원래대로 돌려놓는다.
    monkeypatch.setattr(services, "job_updater", None, raising=False)
    모듈 = importlib.import_module("services.job_updater")
    yield 모듈.update, 기록
    # 가짜 클라이언트를 잡은 모듈을 남기면 뒤 테스트가 그 모듈을 가져다 쓴다.
    # 처음에 있던 모듈은 monkeypatch 가 이어서 되돌린다.
    sys.modules.pop("services.job_updater", None)


@pytest.mark.asyncio
async def test_시나리오와_질의_해석을_적는다(갱신):
    update, 기록 = 갱신
    await update("j1", scenario="S2_SEARCH", query_spec={"category": "base", "confidence": 0.9})

    assert 기록["update"]["scenario"] == "S2_SEARCH"
    assert 기록["update"]["query_spec"] == {"category": "base", "confidence": 0.9}
    assert 기록["eq"] == ("id", "j1")


@pytest.mark.asyncio
async def test_주지_않은_시나리오와_질의는_건드리지_않는다(갱신):
    update, 기록 = 갱신
    await update("j1", status="IN_PROGRESS", progress=30)

    assert "scenario" not in 기록["update"]
    assert "query_spec" not in 기록["update"]
