"""되묻기 재개가 지켜야 할 성질.

멈춘 job 을 이어 돌리는 일이라, 잘못 돌면 사용자가 보고 있던 결과를 덮는다.
무엇을 복원하고 무엇을 거절하는지가 이 경로의 전부다.
"""
import sys
import types

import pytest

from api.internal.v2 import agent
from contracts.internal_api import AgentClarifyRequest


@pytest.fixture
def 대역(monkeypatch):
    """job 조회·기록과 실행을 전부 가짜로 둔다."""
    import services

    본: dict = {"갱신": [], "스냅샷": None, "돌린_상태": None}

    def 세우기(job):
        async def load_job(job_id):
            return job

        async def save_snapshot(job_id, snapshot):
            본["스냅샷"] = snapshot

        async def update(job_id, **kwargs):
            본["갱신"].append(kwargs)

        async def run_query(initial=None, **kwargs):
            본["돌린_상태"] = dict(initial or {})
            # 라우터는 물을 것이 없으면 질문 자리를 None 으로 적는다.
            # 그러지 않으면 남아 있던 질문 때문에 같은 자리에서 또 멈춘다.
            return {**(initial or {}), "clarify_question": None, "result": {"items": []}}

        저장소 = types.SimpleNamespace(load_job=load_job, save_snapshot=save_snapshot)
        기록 = types.SimpleNamespace(update=update)
        monkeypatch.setitem(sys.modules, "services.job_store", 저장소)
        monkeypatch.setattr(services, "job_store", 저장소, raising=False)
        monkeypatch.setitem(sys.modules, "services.job_updater", 기록)
        monkeypatch.setattr(services, "job_updater", 기록, raising=False)
        monkeypatch.setattr(agent.builder, "run_query", run_query)
        return 본

    return 세우기


_멈춘_job = {
    "id": "j1",
    "status": "NEEDS_CLARIFICATION",
    "state_snapshot": {
        "job_id": "j1", "user_id": "u1", "raw_query": "스킨케어 세트 짜줘",
        "basis": "SELF", "scenario": "S6_BUNDLE",
        "clarify_question": "전체 예산이 얼마인가요?", "clarify_count": 0,
    },
}
_답 = AgentClarifyRequest(job_id="j1", answer="10만원")


@pytest.mark.asyncio
async def test_남긴_상태를_복원해_이어_돈다(대역):
    본 = 대역(_멈춘_job)
    await agent._이어_돌리기(_답)

    상태 = 본["돌린_상태"]
    assert 상태["raw_query"] == "스킨케어 세트 짜줘"
    assert 상태["user_id"] == "u1"
    assert 상태["clarify_answer"] == "10만원"


@pytest.mark.asyncio
async def test_물은_횟수를_올린다(대역):
    """올리지 않으면 라우터가 같은 것을 계속 묻는다."""
    본 = 대역(_멈춘_job)
    await agent._이어_돌리기(_답)
    assert 본["돌린_상태"]["clarify_count"] == 1


@pytest.mark.asyncio
async def test_경로는_다시_정한다(대역):
    """답을 받으면 요청 유형이 달라질 수 있다. 멈출 때 정한 경로를 그대로
    들고 가면 새 답과 맞지 않는 곳으로 간다."""
    본 = 대역(_멈춘_job)
    await agent._이어_돌리기(_답)
    assert "scenario" not in 본["돌린_상태"]


@pytest.mark.asyncio
async def test_이어_돌아_끝나면_완료로_적는다(대역):
    본 = 대역(_멈춘_job)
    await agent._이어_돌리기(_답)
    assert 본["갱신"][-1]["status"] == "COMPLETED"


@pytest.mark.asyncio
@pytest.mark.parametrize("상태", ["COMPLETED", "IN_PROGRESS", "FAILED"])
async def test_멈춘_job이_아니면_답을_무시한다(대역, 상태):
    """이미 끝난 job 을 다시 돌리면 사용자가 보고 있던 결과가 덮인다."""
    본 = 대역({**_멈춘_job, "status": 상태})
    await agent._이어_돌리기(_답)
    assert 본["돌린_상태"] is None
    assert 본["갱신"] == []


@pytest.mark.asyncio
async def test_없는_job이면_아무것도_하지_않는다(대역):
    본 = 대역(None)
    await agent._이어_돌리기(_답)
    assert 본["돌린_상태"] is None


@pytest.mark.asyncio
async def test_또_물어야_하면_다시_멈춘다(대역, monkeypatch):
    """답을 받고도 모자랄 수 있다. 진행할지 다시 물을지는 라우터가 정한다."""
    본 = 대역(_멈춘_job)

    async def 또_묻는다(initial=None, **kwargs):
        본["돌린_상태"] = dict(initial or {})
        return {**(initial or {}), "clarify_question": "카테고리를 알려주세요"}

    monkeypatch.setattr(agent.builder, "run_query", 또_묻는다)
    await agent._이어_돌리기(_답)

    assert 본["갱신"][-1]["status"] == "NEEDS_CLARIFICATION"
    assert 본["스냅샷"]["clarify_count"] == 1
