"""홈 카드 실행이 지켜야 할 성질.

실패한 실행이 카드를 덮어쓰면 어제의 멀쩡한 카드가 빈 카드로 바뀐다.
꼭 필요한 단계 없이 돌면 분석 전 카드가 "추천할 것이 없다" 로 보인다.
"""
import asyncio
import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.internal.v2 import home
from contracts.internal_api import HomeKind
from services import home_runner, home_store


@pytest.fixture
def 바깥(monkeypatch):
    """프로필 읽기, 그래프 실행, 저장을 가짜로 둔다. 부른 것을 남긴다."""
    기록: dict = {"돌림": [], "저장": [], "터짐": None}

    async def load(user_id, basis, target_profile):
        return {"user_profile": {"skin_type": "DRY", "region": "서울"}, "weight_prior": {"review": 0.3}}

    async def run_scenario(scenario, initial):
        기록["돌림"].append((scenario, initial))
        if 기록["터짐"]:
            raise 기록["터짐"]
        return {**initial, "result": {"jobId": initial["job_id"], "items": []}}

    async def save(user_id, kind, result):
        기록["저장"].append((user_id, kind, result))

    from graph import builder
    from services import user_context
    monkeypatch.setattr(user_context, "load", load)
    monkeypatch.setattr(builder, "run_scenario", run_scenario)
    monkeypatch.setattr(home_store, "save", save)
    return 기록


@pytest.mark.asyncio
async def test_성공하면_그_사용자와_종류의_카드를_저장한다(바깥):
    await home_runner.run("u1", HomeKind.ENV)

    시나리오, 상태 = 바깥["돌림"][0]
    assert 시나리오 == "HOME_ENV"
    assert 상태["job_id"] == "home:u1:ENV" and 상태["raw_query"] == ""
    assert 상태["basis"] == "SELF" and 상태["user_id"] == "u1"
    assert 상태["query_spec"]["request_type"] == "SEARCH"
    assert 상태["query_spec"]["target"] == "SELF" and 상태["query_spec"]["use_env"] is True
    assert 상태["user_profile"]["region"] == "서울" and 상태["weight_prior"] == {"review": 0.3}
    assert 바깥["저장"] == [("u1", HomeKind.ENV, {"jobId": "home:u1:ENV", "items": []})]


@pytest.mark.asyncio
async def test_루틴은_환경을_쓰지_않는다(바깥):
    await home_runner.run("u1", HomeKind.ROUTINE)
    시나리오, 상태 = 바깥["돌림"][0]
    assert 시나리오 == "HOME_ROUTINE" and 상태["query_spec"]["use_env"] is False


@pytest.mark.asyncio
async def test_실패하면_저장하지_않고_예외도_올리지_않는다(바깥, caplog):
    바깥["터짐"] = RuntimeError("DB 끊김")
    await home_runner.run("u1", HomeKind.ENV)
    assert 바깥["저장"] == []
    assert "이전 카드를 그대로 둔다" in caplog.text


@pytest.mark.asyncio
async def test_같은_사용자와_종류는_차례로_돈다(바깥, monkeypatch):
    from graph import builder

    도는_중 = {"수": 0, "최대": 0}

    async def 느린_실행(scenario, initial):
        도는_중["수"] += 1
        도는_중["최대"] = max(도는_중["최대"], 도는_중["수"])
        await asyncio.sleep(0.01)
        도는_중["수"] -= 1
        return {"result": {}}

    monkeypatch.setattr(builder, "run_scenario", 느린_실행)
    await asyncio.gather(home_runner.run("u9", HomeKind.ENV), home_runner.run("u9", HomeKind.ENV))
    assert 도는_중["최대"] == 1

    도는_중["최대"] = 0
    await asyncio.gather(home_runner.run("u9", HomeKind.ENV), home_runner.run("u9", HomeKind.ROUTINE))
    assert 도는_중["최대"] == 2


def _없는_단계(monkeypatch, *이름들):
    """B 가 단계를 넣은 뒤에도 "없을 때" 를 볼 수 있게 import 를 막는다."""
    for 이름 in 이름들:
        monkeypatch.setitem(sys.modules, f"graph.nodes.{이름}", None)


def test_꼭_필요한_단계가_없으면_알려_준다(monkeypatch):
    _없는_단계(monkeypatch, "env_history", "compatibility")
    assert home_runner.missing_nodes(HomeKind.ENV) == ["env_history"]
    assert home_runner.missing_nodes(HomeKind.ROUTINE) == ["compatibility"]

    async def env_history(state):
        return {}

    monkeypatch.setitem(sys.modules, "graph.nodes.env_history",
                        types.SimpleNamespace(env_history=env_history))
    assert home_runner.missing_nodes(HomeKind.ENV) == []


# 저장

@pytest.mark.asyncio
async def test_사용자와_종류로_한_줄을_덮어쓰고_job_id_는_비운다(monkeypatch):
    기록: dict = {}

    class 쿼리:
        def upsert(self, 행, on_conflict=None):
            기록["행"], 기록["on_conflict"] = 행, on_conflict
            return self

        def execute(self):
            return types.SimpleNamespace(data=[])

    def get_supabase():
        return types.SimpleNamespace(table=lambda 이름: 기록.setdefault("table", 이름) and 쿼리())

    import db
    모듈 = types.SimpleNamespace(get_supabase=get_supabase)
    monkeypatch.setitem(sys.modules, "db.supabase_client", 모듈)
    monkeypatch.setattr(db, "supabase_client", 모듈, raising=False)

    await home_store.save("u1", HomeKind.ENV, {"items": []})
    assert 기록["table"] == "home_recommendations" and 기록["on_conflict"] == "user_id,kind"
    행 = 기록["행"]
    assert (행["user_id"], 행["kind"], 행["result"], 행["job_id"]) == ("u1", "ENV", {"items": []}, None)
    assert 행["generated_at"]


# 라우터

app = FastAPI()
app.include_router(home.router, prefix="/internal")
client = TestClient(app)


@pytest.fixture
def 받은_실행(monkeypatch):
    받은: list = []

    async def run(user_id, kind):
        받은.append((user_id, kind))

    monkeypatch.setattr(home_runner, "run", run)
    return 받은


def test_필수_단계가_없으면_돌리지_않고_stub_으로_응답한다(받은_실행, monkeypatch):
    _없는_단계(monkeypatch, "env_history")
    응답 = client.post("/internal/home/run", json={"userId": "u1", "kind": "ENV"})
    assert 응답.status_code == 202 and 응답.json()["stub"] is True
    assert 받은_실행 == []


def test_필수_단계가_있으면_배경에서_돌린다(받은_실행, monkeypatch):
    monkeypatch.setattr(home_runner, "missing_nodes", lambda kind: [])
    응답 = client.post("/internal/home/run", json={"userId": "u1", "kind": "ENV"})
    assert 응답.status_code == 202 and 응답.json()["stub"] is False
    assert 받은_실행 == [("u1", HomeKind.ENV)]
