"""/internal/agent/run/v2 가 실행 결과를 job 에 어떻게 남기는지 본다.

그래프 자체는 test_builder 가 본다. 여기서는 "돌린 결과를 job 에 어떻게
적느냐"만 확인한다. 그래서 실행은 가짜로 두고, 실제 LLM 을 부르지 않는다.
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

    @property
    def 마지막(self) -> dict:
        return self.호출[-1]


@pytest.fixture
def 기록(monkeypatch):
    import services

    가짜 = 가짜기록()
    모듈 = types.SimpleNamespace(update=가짜.update)

    # sys.modules 만 바꾸면 모자란다. 다른 테스트가 먼저 진짜 모듈을 불러오면
    # services 패키지에 속성이 붙고, `from services import job_updater` 는
    # 그 속성을 먼저 본다. 그때는 진짜 모듈이 돌아 DB 를 찌른다.
    monkeypatch.setitem(sys.modules, "services.job_updater", 모듈)
    monkeypatch.setattr(services, "job_updater", 모듈, raising=False)
    return 가짜


@pytest.fixture
def 실행대역(monkeypatch):
    """run_query 를 가짜로 바꾼다. 진짜를 두면 LLM 을 실제로 부른다."""
    def 세우기(반환=None, 예외=None):
        받은: dict = {}

        async def 가짜(initial=None, **kwargs):
            받은.update(initial or {})
            if 예외 is not None:
                await kwargs["on_fail"](예외)
                raise 예외
            return {**(initial or {}), **(반환 or {})}

        monkeypatch.setattr(agent.builder, "run_query", 가짜)
        return 받은

    return 세우기


_요청 = AgentRunV2Request(job_id="j1", user_id="u1", raw_query="여름 쿠션")


@pytest.mark.asyncio
async def test_끝나면_결과와_함께_완료로_남긴다(기록, 실행대역):
    실행대역({"result": {"items": []}})
    await agent._실행(_요청)

    assert 기록.마지막["status"] == "COMPLETED"
    assert 기록.마지막["progress"] == 100
    assert 기록.마지막["result"] == {"items": []}


@pytest.mark.asyncio
async def test_질의를_그대로_넘긴다(기록, 실행대역):
    받은 = 실행대역({"result": {}})
    await agent._실행(_요청)
    assert 받은["raw_query"] == "여름 쿠션"
    assert 받은["job_id"] == "j1"


@pytest.mark.asyncio
async def test_되물어야_하면_멈춘_상태로_남긴다(기록, 실행대역):
    """되묻는 중은 실패가 아니다. 이 상태의 job 을 정리하면 답을 받아도
    이어 돌릴 수 없다."""
    실행대역({
        "clarify_question": "전체 예산이 얼마인가요?",
        "scenario": "S6_BUNDLE",
        "query_spec": {"category": "skincare", "conditions": ["건성"]},
    })
    await agent._실행(_요청)

    마지막 = 기록.마지막
    assert 마지막["status"] == "NEEDS_CLARIFICATION"
    assert 마지막["result"]["clarify"]["question"] == "전체 예산이 얼마인가요?"
    # 화면이 결과를 읽는 경로 하나만 알면 되도록 결과 스키마에 담는다
    assert 마지막["result"]["scenario"] == "S6_BUNDLE"
    assert 마지막["result"]["query"]["raw"] == "여름 쿠션"


@pytest.mark.asyncio
async def test_되묻는_동안은_완료로_적지_않는다(기록, 실행대역):
    실행대역({"clarify_question": "조금 더 알려주세요"})
    await agent._실행(_요청)
    assert all(c.get("status") != "COMPLETED" for c in 기록.호출)


@pytest.mark.asyncio
async def test_실패하면_FAILED로_남기고_삼킨다(기록, 실행대역):
    """배경 작업이라 예외를 올려도 받을 곳이 없다. 대신 job 에 남긴다."""
    실행대역(예외=RuntimeError("벡터 검색 실패"))
    await agent._실행(_요청)

    assert 기록.마지막["status"] == "FAILED"
    assert "벡터 검색 실패" in 기록.마지막["error_msg"]
