"""시나리오 결정 실험의 실행부를 본다. LLM 은 부르지 않는다."""
import pytest

from eval.router_metrics import Outcome
from eval.run_router_eval import read_golden, run_condition


def _문제(아이디: str) -> dict:
    return {"id": 아이디, "input": {"raw_query": 아이디}, "expected": {"scenario": "S2_SEARCH"}}


@pytest.mark.asyncio
async def test_정한_횟수만큼_반복하고_실행마다_모든_문제를_돌린다():
    async def 조건(입력):
        return Outcome(spec={"request_type": "SEARCH"}, scenario="S2_SEARCH")

    runs = await run_condition([_문제("a"), _문제("b")], 조건, runs=3)

    assert [len(run) for run in runs] == [2, 2, 2]
    assert all(t.outcome.scenario == "S2_SEARCH" for run in runs for t in run)
    assert all(t.seconds >= 0 for run in runs for t in run)


@pytest.mark.asyncio
async def test_한_문제가_터져도_나머지는_잰다():
    async def 조건(입력):
        if 입력["raw_query"] == "a":
            raise RuntimeError("boom")
        return Outcome(spec={}, scenario="S2_SEARCH")

    (run,) = await run_condition([_문제("a"), _문제("b")], 조건, runs=1)

    assert run[0].outcome is None and "boom" in run[0].error
    assert run[1].outcome is not None


@pytest.mark.asyncio
async def test_문제마다_그_사이의_호출_기록만_담긴다():
    from services.llm.usage import LLMCall, record

    async def 조건(입력):
        for _ in range(2 if 입력["raw_query"] == "a" else 1):
            record(LLMCall(role="normalize", model="m", input_tokens=1, output_tokens=1, seconds=0.0))
        return Outcome(spec={}, scenario="S2_SEARCH")

    (run,) = await run_condition([_문제("a"), _문제("b")], 조건, runs=1, concurrency=2)

    assert [len(t.calls) for t in run] == [2, 1]


def test_버전을_주면_그_버전_문제만_읽는다():
    v1 = read_golden("test", "v1")
    v2 = read_golden("test", "v2")
    assert len(v1) == 36
    assert len(v2) == 180
    assert not {r["id"] for r in v1} & {r["id"] for r in v2}
