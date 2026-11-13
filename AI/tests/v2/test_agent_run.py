"""/internal/agent/run/v2 가 실행 결과를 job 에 어떻게 남기는지 본다.

그래프 자체는 test_builder 가 본다. 여기서는 "돌린 결과를 job 에 어떻게
적느냐"만 확인한다. 그래서 실행은 가짜로 두고, 실제 LLM 을 부르지 않는다.
"""
import json
import sys
import types

import pytest

from api.internal.v2 import agent
from contracts.internal_api import AgentRunV2Request


class 가짜기록:
    def __init__(self):
        self.호출: list[dict] = []
        self.스냅샷: dict | None = None
        # 스냅샷 저장과 갱신이 어떤 순서로 일어났는지
        self.순서: list[str] = []

    async def update(self, job_id, **kwargs):
        self.호출.append({"job_id": job_id, **kwargs})
        self.순서.append(kwargs.get("status") or "update")

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

    # 되묻는 경우에는 멈춘 시점의 상태도 남긴다. 진짜를 두면 DB 를 찌른다.
    async def 저장(job_id, snapshot):
        가짜.스냅샷 = snapshot
        가짜.순서.append("snapshot")

    저장소 = types.SimpleNamespace(save_snapshot=저장)
    monkeypatch.setitem(sys.modules, "services.job_store", 저장소)
    monkeypatch.setattr(services, "job_store", 저장소, raising=False)
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
async def test_진행과_함께_단계_목록을_남긴다(기록, monkeypatch):
    단계들 = [{"key": "normalize", "label": "요청 이해", "state": "NOW"}]

    async def 가짜(initial=None, **kwargs):
        await kwargs["on_progress"]("요청 이해", 0, 단계들)
        return {**(initial or {}), "result": {}}

    monkeypatch.setattr(agent.builder, "run_query", 가짜)
    await agent._실행(_요청)

    진행 = 기록.호출[0]
    assert 진행["step"] == "요청 이해"
    assert 진행["progress"] == 0
    assert 진행["status"] == "IN_PROGRESS"
    assert 진행["steps"] == 단계들


@pytest.mark.asyncio
async def test_질의를_그대로_넘긴다(기록, 실행대역):
    받은 = 실행대역({"result": {}})
    await agent._실행(_요청)
    assert 받은["raw_query"] == "여름 쿠션"
    assert 받은["job_id"] == "j1"


@pytest.mark.asyncio
async def test_기준_상품을_넘기고_빠진_질의는_빈_문자열로_둔다(기록, 실행대역):
    받은 = 실행대역({"result": {}})
    await agent._실행(AgentRunV2Request(job_id="j1", user_id="u1", base_product_id="p1"))
    assert 받은["base_product_id"] == "p1"
    assert 받은["raw_query"] == ""


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
    assert 마지막["result"]["clarify"]["missingFields"] == []


@pytest.mark.asyncio
async def test_되묻는_결과에_빠진_항목을_담는다(기록, 실행대역):
    실행대역({
        "clarify_question": "전체 예산이 얼마인가요?",
        "clarify_missing_fields": ["budget.total", "bundle_steps"],
        "scenario": "S6_BUNDLE",
    })
    await agent._실행(_요청)

    assert 기록.마지막["result"]["clarify"]["missingFields"] == ["budget.total", "bundle_steps"]
    # 답을 받으면 라우터가 다시 검사하므로 남겨 둘 필요가 없다
    assert "clarify_missing_fields" not in 기록.스냅샷


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


@pytest.mark.asyncio
async def test_경로가_정해지면_시나리오와_질의_해석을_바로_적는다(기록, monkeypatch):
    """끝날 때까지 기다리면 진행 중인 job 의 시나리오가 화면에 보이지 않는다."""
    본: dict = {}

    async def 가짜(initial=None, **kwargs):
        await kwargs["on_route"]({"scenario": "S2_SEARCH", "query_spec": {"category": "base"}})
        본["경로_뒤_호출_수"] = len(기록.호출)
        return {**(initial or {}), "result": {}}

    monkeypatch.setattr(agent.builder, "run_query", 가짜)
    await agent._실행(_요청)

    assert 본["경로_뒤_호출_수"] == 1
    assert 기록.호출[0]["scenario"] == "S2_SEARCH"
    assert 기록.호출[0]["query_spec"] == {"category": "base"}


@pytest.mark.asyncio
async def test_되묻는_경우에도_시나리오를_적는다(기록, monkeypatch):
    async def 가짜(initial=None, **kwargs):
        정해진 = {"scenario": "S6_BUNDLE", "query_spec": {"category": "skincare"}}
        await kwargs["on_route"](정해진)
        return {**(initial or {}), **정해진, "clarify_question": "예산이 얼마인가요?"}

    monkeypatch.setattr(agent.builder, "run_query", 가짜)
    await agent._실행(_요청)

    assert 기록.호출[0]["scenario"] == "S6_BUNDLE"
    assert 기록.마지막["status"] == "NEEDS_CLARIFICATION"


@pytest.mark.asyncio
async def test_완료_때_스냅샷을_먼저_남기고_완료로_바꾼다(기록, 실행대역):
    """완료를 먼저 적으면 BE 가 스냅샷이 빈 완료 job 을 읽을 수 있다."""
    실행대역({
        "scenario": "S7_REFINE",
        "query_spec": {"category": "base", "conditions": ["무향"]},
        "result": {"items": []},
    })
    await agent._실행(_요청)

    assert 기록.순서[-2:] == ["snapshot", "COMPLETED"]
    # 조건 수정은 경로 중에 질의가 바뀌므로 완료 때 한 번 더 적는다
    assert 기록.마지막["scenario"] == "S7_REFINE"
    assert 기록.마지막["query_spec"] == {"category": "base", "conditions": ["무향"]}


@pytest.mark.asyncio
async def test_완료_스냅샷에_필요한_값만_줄여_담는다(기록, 실행대역):
    후보들 = [
        {"product_id": f"p{i}", "source": "vector", "similarity": 0.9, "extra": "버림"}
        for i in range(70)
    ]
    후보들[0]["slot_key"] = "toner"
    실행대역({
        "scenario": "S2_SEARCH",
        "basis": "SELF",
        "query_spec": {"category": "base"},
        "candidates": 후보들,
        "scored": [{"product_id": "p0", "total": 80, "breakdown": [{"key": "review"}]}],
        "bundle_slots": [{"slotKey": "toner", "label": "토너", "candidates": []}],
        "intent_vector": [0.1] * 1024,
        "product_meta": {"p0": {"name": "쿠션"}},
        "trace": ["normalize", "router", "retrieve"],
        "result": {"items": []},
    })
    await agent._실행(_요청)

    스냅샷 = 기록.스냅샷
    assert len(스냅샷["candidates"]) == agent.스냅샷_후보_상한
    assert 스냅샷["candidates"][0] == {
        "product_id": "p0", "source": "vector", "similarity": 0.9, "slot_key": "toner",
    }
    assert 스냅샷["candidates"][1] == {"product_id": "p1", "source": "vector", "similarity": 0.9}
    assert 스냅샷["scored"] == [{"product_id": "p0", "total": 80}]
    assert 스냅샷["bundle_slots"] == [{"slotKey": "toner", "label": "토너", "candidates": []}]
    assert 스냅샷["raw_query"] == "여름 쿠션"
    assert 스냅샷["basis"] == "SELF"
    assert 스냅샷["trace"] == ["normalize", "router", "retrieve"]
    # 크기만 크고 다시 만들 수 있는 값은 넣지 않는다
    assert "intent_vector" not in 스냅샷
    assert "product_meta" not in 스냅샷
    json.dumps(스냅샷)


@pytest.mark.asyncio
async def test_대체_후보를_뺀_수가_없으면_0으로_남긴다(기록, 실행대역):
    """BE 가 이 값을 그대로 읽는다. 키가 없으면 BE 쪽에서 따로 처리해야 한다."""
    실행대역({"result": {}})
    await agent._실행(_요청)

    assert 기록.스냅샷["alternatives_dropped_count"] == 0
    assert 기록.스냅샷["candidates"] == []
    assert 기록.스냅샷["scored"] == []


@pytest.mark.asyncio
async def test_대체_후보를_뺀_수를_남긴다(기록, 실행대역):
    실행대역({"alternatives_dropped_count": 3, "result": {}})
    await agent._실행(_요청)
    assert 기록.스냅샷["alternatives_dropped_count"] == 3
