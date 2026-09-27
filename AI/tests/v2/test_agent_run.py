"""/internal/agent/run/v2 가 그래프를 돌리고 job 을 갱신하는지 본다.

job 갱신은 DB 를 쓰므로 가짜 모듈을 끼워 넣는다. 실행 함수가 DB 모듈을
함수 안에서 import 하도록 만든 이유가 이것이다. 최상단에서 가져오면
키 없이는 이 테스트 파일조차 열리지 않는다.
"""
import sys
import types

import pytest

from api.internal.v2 import agent
from contracts.internal_api import AgentRunV2Request


class 가짜기록:
    def __init__(self):
        self.호출: list[dict] = []

    async def update(self, job_id, **kwargs):
        self.호출.append({"job_id": job_id, **kwargs})


@pytest.fixture
def 기록(monkeypatch):
    가짜 = 가짜기록()
    monkeypatch.setitem(
        sys.modules, "services.job_updater",
        types.SimpleNamespace(update=가짜.update),
    )
    return 가짜


@pytest.mark.asyncio
async def test_그래프를_돌리고_완료로_남긴다(기록):
    await agent._실행(AgentRunV2Request(job_id="j1", user_id="u1", raw_query="여름 쿠션"))

    상태 = [c.get("status") for c in 기록.호출]
    assert "IN_PROGRESS" in 상태
    assert 상태[-1] == "COMPLETED"
    assert 기록.호출[-1]["progress"] == 100


@pytest.mark.asyncio
async def test_질의가_조건으로_들어간다(기록, monkeypatch):
    """Normalize 가 들어오기 전까지는 원문을 조건으로 넘겨 경로를 태운다."""
    받은: dict = {}

    async def 가짜실행(scenario, initial=None, **kwargs):
        받은.update({"scenario": scenario, "initial": initial})
        return {"result": {}}

    monkeypatch.setattr(agent.builder, "run_scenario", 가짜실행)
    await agent._실행(AgentRunV2Request(job_id="j1", user_id="u1", raw_query="여름 쿠션"))

    assert 받은["scenario"] == "S2_SEARCH"
    assert 받은["initial"]["query_spec"]["conditions"] == ["여름 쿠션"]


@pytest.mark.asyncio
async def test_실패하면_FAILED로_남기고_삼킨다(기록, monkeypatch):
    """배경 작업이라 예외를 올려도 받을 곳이 없다. 대신 job 에 남긴다."""
    async def 망가진(scenario, initial=None, **kwargs):
        await kwargs["on_fail"](RuntimeError("벡터 검색 실패"))
        raise RuntimeError("벡터 검색 실패")

    monkeypatch.setattr(agent.builder, "run_scenario", 망가진)
    await agent._실행(AgentRunV2Request(job_id="j1", user_id="u1", raw_query="q"))

    마지막 = 기록.호출[-1]
    assert 마지막["status"] == "FAILED"
    assert "벡터 검색 실패" in 마지막["error_msg"]
