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
    assert len(v2) == 360
    assert not {r["id"] for r in v1} & {r["id"] for r in v2}


class _가짜_LLM:
    """정해 둔 답을 차례로 내놓는다. 받은 프롬프트와 temperature 를 적어 둔다."""

    def __init__(self, 답들):
        self._답들 = list(답들)
        self.받은 = []
        self.받은_말 = []

    async def chat_json(self, system, user, temperature=0.0, **_):
        self.받은.append((system, temperature))
        self.받은_말.append(user)
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
async def test_구조_규칙_조건은_답을_읽었는지를_남긴다(가짜_llm):
    """모델을 바꿔 견줄 때 양식을 못 지킨 비율을 내는 재료다."""
    from eval.router_conditions import CONDITIONS

    가짜_llm([_답(category="base")])
    assert (await CONDITIONS["a2"].run({"raw_query": "쿠션 추천"})).parsed is True

    가짜_llm([None])
    assert (await CONDITIONS["a2"].run({"raw_query": "쿠션 추천"})).parsed is False

    # 직전 결과가 있으면 못 읽어도 조건 수정으로 보낸다. 그래도 못 읽었다는 것은 남는다
    가짜_llm([None])
    나온 = await CONDITIONS["a2"].run({"raw_query": "더 싼 걸로", "parent_job_id": "prev"})
    assert 나온.scenario == "S7_REFINE" and 나온.parsed is False


def test_모델을_고르면_도는_동안만_Normalize_의_모델이_바뀐다(monkeypatch):
    import argparse

    from eval import run_router_eval
    from services.llm import client

    monkeypatch.setattr(client.settings, "LLM_NORMALIZE_MODEL", "")
    본 = []

    async def 조건(입력):
        본.append(client.settings.LLM_NORMALIZE_MODEL)
        return Outcome(spec={}, scenario="S2_SEARCH")

    인자 = argparse.Namespace(model="claude-haiku-5-5", runs=2, concurrency=1)
    runs = run_router_eval._조건_돌리기(인자, [_문제("a")], 조건)

    assert 본 == ["claude-haiku-5-5", "claude-haiku-5-5"]
    assert client.settings.LLM_NORMALIZE_MODEL == ""
    assert [len(run) for run in runs] == [1, 1]
    client.get_llm.cache_clear()


def test_모델을_고르지_않으면_설정을_건드리지_않는다(monkeypatch):
    import argparse

    from eval import run_router_eval
    from services.llm import client

    monkeypatch.setattr(client.settings, "LLM_NORMALIZE_MODEL", "미리-정한-모델")
    본 = []

    async def 조건(입력):
        본.append(client.settings.LLM_NORMALIZE_MODEL)
        return Outcome(spec={}, scenario="S2_SEARCH")

    run_router_eval._조건_돌리기(argparse.Namespace(model=None, runs=1, concurrency=1), [_문제("a")], 조건)

    assert 본 == ["미리-정한-모델"]


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


@pytest.fixture
def 가짜_jev(monkeypatch):
    """Jev 가 내놓을 답을 정해 두고, 받은 내용과 질문을 적어 둔다."""
    def 끼우기(답):
        받은 = []

        async def ask(state, questions):
            받은.append((state, questions))
            return {이름: 답[이름] for 이름 in questions}

        monkeypatch.setattr("services.llm.jev.ask", ask)
        return 받은
    return 끼우기


def _jev_종류(종류, 확률):
    나머지 = {k: 0.0 for k in ("SEARCH", "EVALUATE", "BUNDLE", "REFINE")}
    return {"type": "choice", "choice": 종류, "confidence": 확률, "probabilities": {**나머지, 종류: 확률}}


@pytest.mark.asyncio
async def test_나눠_맡는_조건은_값은_LLM_요청_종류는_Jev_것을_쓴다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    가짜_llm([_답("SEARCH", category="base", base_product_ref="어떤 쿠션")])
    가짜_jev({"request_type": _jev_종류("EVALUATE", 0.8), "vague": {"type": "noul", "noul": 0.1}})

    나온 = await CONDITIONS["a4"].run({"raw_query": "어떤 쿠션 대신 쓸 거"})

    assert 나온.spec["request_type"] == "EVALUATE"
    assert 나온.spec["category"] == "base"
    assert 나온.scenario == "S1_EVALUATE"
    assert (나온.scenario_prob, 나온.vague_prob) == (0.8, 0.1)
    assert not 나온.clarify_rule


@pytest.mark.asyncio
async def test_Jev_가_조건_수정을_골라도_직전_결과가_없으면_검색으로_본다(가짜_jev):
    from eval.router_conditions import CONDITIONS

    가짜_jev({"request_type": _jev_종류("REFINE", 0.7), "vague": {"type": "noul", "noul": 0.2}})
    나온 = await CONDITIONS["a7"].run({"raw_query": "더 저렴한 쿠션 없어?"})

    assert 나온.scenario == "S2_SEARCH"
    assert not 나온.extracts_values


@pytest.mark.asyncio
async def test_확인하는_조건은_LLM_이_정한_종류를_Jev_에_묻고_그_확률을_쓴다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    가짜_llm([_답("BUNDLE", category="skincare")])
    받은 = 가짜_jev({"correct": {"type": "noul", "noul": 0.35}})

    나온 = await CONDITIONS["a6"].run({"raw_query": "스킨케어 세트 추천"})

    assert 받은[0][0]["predicted_request_type"] == "BUNDLE"
    assert 나온.scenario == "S6_BUNDLE"
    assert 나온.scenario_prob == 0.35
    assert 나온.clarify_rule          # 전체 예산이 없다. 구조 규칙은 그대로 본다


@pytest.mark.asyncio
async def test_직전_결과가_있으면_Jev_를_부르지_않는다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    가짜_llm([_답(category="base")])
    받은 = 가짜_jev({})

    for 키 in ("a4", "a5", "a6", "a7"):
        나온 = await CONDITIONS[키].run({"raw_query": "쿠션 추천", "parent_job_id": "prev"})
        assert 나온.scenario == "S7_REFINE"
        assert 나온.scenario_prob is None

    assert 받은 == []


def _jev_답(종류, 막연함=0.1):
    return {"request_type": _jev_종류(종류, 0.9), "vague": {"type": "noul", "noul": 막연함}}


@pytest.mark.asyncio
async def test_이중_확인_조건은_두_답이_같으면_다시_묻지_않고_확정한다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    llm = 가짜_llm([_답("SEARCH", category="base")])
    가짜_jev(_jev_답("SEARCH", 막연함=0.3))

    나온 = await CONDITIONS["a5"].run({"raw_query": "쿠션 추천"})

    assert len(llm.받은) == 1
    assert 나온.agreement == "same"
    assert 나온.scenario == "S2_SEARCH"
    assert 나온.scenario_prob is None and 나온.vague_prob == 0.3
    assert not 나온.clarify_rule


@pytest.mark.asyncio
async def test_이중_확인_조건은_직전_결과_없는_조건_수정과_검색을_같은_답으로_본다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    llm = 가짜_llm([_답("REFINE", category="base")])
    가짜_jev(_jev_답("SEARCH"))

    나온 = await CONDITIONS["a5"].run({"raw_query": "더 저렴한 쿠션 없어?"})

    assert len(llm.받은) == 1
    assert 나온.agreement == "same" and 나온.scenario == "S2_SEARCH"


@pytest.mark.asyncio
async def test_이중_확인_조건은_두_답이_다르면_두_후보를_알려_주고_다시_해석한다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    llm = 가짜_llm([
        _답("SEARCH", category="base"),
        _답("EVALUATE", category="base", base_product_ref="어떤 쿠션"),
    ])
    가짜_jev(_jev_답("EVALUATE"))

    나온 = await CONDITIONS["a5"].run({"raw_query": "어떤 쿠션 대신 쓸 거"})

    assert len(llm.받은) == 2
    assert "SEARCH" in llm.받은_말[1] and "EVALUATE" in llm.받은_말[1]
    assert 나온.agreement == "resolved"
    assert 나온.scenario == "S1_EVALUATE"
    # 값도 다시 해석한 것을 쓴다
    assert 나온.spec["base_product_ref"] == "어떤 쿠션"
    assert not 나온.clarify_rule


@pytest.mark.asyncio
async def test_이중_확인_조건은_다시_해석해도_다르면_사용자에게_묻는다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    llm = 가짜_llm([_답("SEARCH", category="base")])
    가짜_jev(_jev_답("EVALUATE"))

    나온 = await CONDITIONS["a5"].run({"raw_query": "어떤 쿠션 대신 쓸 거"})

    assert len(llm.받은) == 2
    assert 나온.agreement == "unresolved"
    assert 나온.clarify_rule


@pytest.mark.asyncio
async def test_이중_확인_조건은_두_답이_같아도_필수_값이_비면_되묻는다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    가짜_llm([_답("BUNDLE", category="skincare")])
    가짜_jev(_jev_답("BUNDLE"))

    나온 = await CONDITIONS["a5"].run({"raw_query": "스킨케어 세트 추천"})

    assert 나온.agreement == "same" and 나온.clarify_rule


@pytest.mark.asyncio
async def test_이중_확인_조건은_값을_읽지_못하면_견주지_않고_되묻는다(가짜_llm, 가짜_jev):
    from eval.router_conditions import CONDITIONS

    가짜_llm([None])
    가짜_jev(_jev_답("EVALUATE"))

    나온 = await CONDITIONS["a5"].run({"raw_query": "쿠션 추천"})

    assert 나온.agreement is None
    assert 나온.clarify_rule and 나온.scenario == "S1_EVALUATE"


def test_확신_점수로_되묻던_예전_조건은_없다():
    """채택되지 않아 뺐다. 결과는 리포트로만 남아 있다."""
    from eval.router_conditions import CONDITIONS

    assert sorted(CONDITIONS) == ["a2", "a3", "a4", "a5", "a6", "a7", "b0"]
