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


class _가짜_LLM:
    """정해 둔 답을 차례로 내놓는다. 받은 프롬프트와 temperature 를 적어 둔다."""

    def __init__(self, 답들):
        self._답들 = list(답들)
        self.받은 = []

    async def chat_json(self, system, user, temperature=0.0, **_):
        self.받은.append((system, temperature))
        return self._답들[(len(self.받은) - 1) % len(self._답들)]


def _답(종류="SEARCH", **채운):
    return {"request_type": 종류, "category": None, "features": {}, "conditions": [],
            "budget": {"max": None, "total": None}, **채운}


@pytest.fixture
def 가짜_llm(monkeypatch):
    def 끼우기(답들):
        llm = _가짜_LLM(답들)
        monkeypatch.setattr("services.llm.get_llm", lambda role: llm)
        return llm
    return 끼우기


@pytest.mark.asyncio
async def test_구조_규칙_조건은_확신_점수를_묻지_않고_확률도_내지_않는다(가짜_llm):
    from eval.router_conditions import CONDITIONS

    llm = 가짜_llm([_답(category="base")])
    나온 = await CONDITIONS["a2"].run({"raw_query": "쿠션 추천"})

    assert "confidence" not in llm.받은[0][0]
    assert 나온.scenario == "S2_SEARCH"
    assert not 나온.clarify_rule
    assert 나온.scenario_prob is None


@pytest.mark.asyncio
async def test_구조_규칙_조건은_단서가_없거나_필수_값이_비면_되묻는다(가짜_llm):
    from eval.router_conditions import CONDITIONS

    가짜_llm([_답()])
    assert (await CONDITIONS["a2"].run({"raw_query": "추천해줘"})).clarify_rule

    가짜_llm([_답("EVALUATE", category="base")])
    나온 = await CONDITIONS["a2"].run({"raw_query": "그 쿠션 어때?"})
    assert 나온.scenario == "S1_EVALUATE" and 나온.clarify_rule


@pytest.mark.asyncio
async def test_구조_규칙_조건은_답을_읽지_못하면_되묻는다(가짜_llm):
    from eval.router_conditions import CONDITIONS

    가짜_llm([None])
    나온 = await CONDITIONS["a2"].run({"raw_query": "쿠션 추천"})
    assert 나온.clarify_rule and 나온.scenario == "S2_SEARCH"


@pytest.mark.asyncio
async def test_반복_질문_조건은_다섯_번_묻고_일치한_비율을_확률로_쓴다(가짜_llm):
    from eval.router_conditions import CONDITIONS

    llm = 가짜_llm([
        _답("SEARCH", category="base"), _답("EVALUATE", category="base", base_product_ref="어떤 쿠션"),
        _답("SEARCH", category="base"), _답("SEARCH", category="base"),
        _답("EVALUATE", category="base", base_product_ref="어떤 쿠션"),
    ])
    나온 = await CONDITIONS["a3"].run({"raw_query": "쿠션 뭐가 좋아?"})

    assert len(llm.받은) == 5
    assert all(온도 == 0.7 for _, 온도 in llm.받은)
    assert 나온.scenario == "S2_SEARCH"
    assert 나온.scenario_prob == pytest.approx(0.6)
    assert 나온.spec["request_type"] == "SEARCH"


@pytest.mark.asyncio
async def test_반복_질문_조건도_조건이_부족하면_일치_비율과_상관없이_되묻는다(가짜_llm):
    from eval.router_conditions import CONDITIONS

    가짜_llm([_답()])
    나온 = await CONDITIONS["a3"].run({"raw_query": "추천해줘"})

    assert 나온.scenario_prob == 1.0
    assert 나온.clarify_rule


@pytest.mark.asyncio
async def test_직전_결과가_있으면_반복하지_않고_한_번만_묻는다(가짜_llm):
    from eval.router_conditions import CONDITIONS

    llm = 가짜_llm([_답(category="base")])
    나온 = await CONDITIONS["a3"].run({"raw_query": "쿠션 추천", "parent_job_id": "prev"})

    assert len(llm.받은) == 1
    assert 나온.scenario == "S7_REFINE"
    assert 나온.scenario_prob is None and not 나온.clarify_rule
