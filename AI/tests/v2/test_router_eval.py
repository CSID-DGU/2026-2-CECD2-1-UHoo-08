"""평가 러너의 비교 규칙을 본다.

러너 자체는 실제 LLM 을 부르므로 CI 에서 돌리지 않는다. 대신 "무엇을
맞다고 볼 것인가"만 여기서 고정한다. 이 규칙이 틀리면 리포트 숫자가
전부 틀린 값이 되는데, 숫자만 봐서는 알아챌 수 없다.
"""
import pytest

from eval.run_router_eval import compare, evaluate, to_markdown

_스펙 = {
    "request_type": "SEARCH", "category": "base",
    "budget": {"max": 30000, "total": None},
    "use_env": False, "value_seeking": True, "target": "SELF",
    "base_product_ref": None,
}


def test_기대값에_적힌_키만_본다():
    """모든 필드를 고정하면 프롬프트를 조금 고쳐도 골든셋이 통째로 깨진다."""
    판정 = compare({"scenario": "S2_SEARCH"}, _스펙, "S2_SEARCH", False)
    assert 판정 == {"scenario": True}


def test_중첩된_값도_꺼내_본다():
    판정 = compare({"budget_max": 30000, "budget_total": None}, _스펙, "S2_SEARCH", False)
    assert 판정 == {"budget_max": True, "budget_total": True}


def test_기준_상품은_있는지만_본다():
    """상품 표현은 모델마다 조금씩 다르게 적는다. 문자열을 맞추게 하면
    "라네즈 네오쿠션 21호"와 "네오쿠션 21호"가 오답이 된다."""
    스펙 = dict(_스펙, base_product_ref="라네즈 네오쿠션 21호")
    assert compare({"base_product_ref_present": True}, 스펙, "S1_EVALUATE", False)


def test_쓸_수_없는_키는_바로_알린다():
    """조용히 무시하면 골든셋에 오타가 난 항목이 영영 검사되지 않는다."""
    with pytest.raises(KeyError, match="skin_type"):
        compare({"skin_type": "DRY"}, _스펙, "S2_SEARCH", False)


@pytest.mark.asyncio
async def test_항목별로_맞은_수를_센다():
    기록 = [
        {"id": "router-g-0001", "input": {"raw_query": "쿠션"},
         "expected": {"scenario": "S2_SEARCH", "category": "base"}},
        {"id": "router-g-0002", "input": {"raw_query": "세트"},
         "expected": {"scenario": "S6_BUNDLE", "category": "base"}},
    ]

    async def 한_건(입력):
        return _스펙, "S2_SEARCH", False

    결과 = await evaluate(기록, 한_건)
    assert 결과["전체"]["scenario"] == 2 and 결과["맞음"]["scenario"] == 1
    assert 결과["맞음"]["category"] == 2
    assert len(결과["틀림"]) == 1
    assert 결과["틀림"][0]["틀린_항목"]["scenario"] == {"기대": "S6_BUNDLE", "실제": "S2_SEARCH"}


@pytest.mark.asyncio
async def test_한_건이_터져도_나머지를_잰다():
    """한 질의에서 LLM 이 죽었다고 평가를 처음부터 다시 돌리면, 매번
    돈을 내고 처음부터 시작하게 된다."""
    기록 = [
        {"id": "router-g-0001", "input": {"raw_query": "터짐"}, "expected": {"scenario": "S2_SEARCH"}},
        {"id": "router-g-0002", "input": {"raw_query": "쿠션"}, "expected": {"scenario": "S2_SEARCH"}},
    ]

    async def 한_건(입력):
        if 입력["raw_query"] == "터짐":
            raise RuntimeError("타임아웃")
        return _스펙, "S2_SEARCH", False

    결과 = await evaluate(기록, 한_건)
    assert 결과["맞음"]["scenario"] == 1
    assert any("타임아웃" in (사례.get("error") or "") for 사례 in 결과["틀림"])


@pytest.mark.asyncio
async def test_리포트에_틀린_사례가_들어간다():
    """숫자만 있으면 무엇을 고쳐야 할지 알 수 없다."""
    기록 = [{"id": "router-g-0002", "input": {"raw_query": "세트 짜줘"},
            "tags": ["ambiguous"], "expected": {"scenario": "S6_BUNDLE"}}]

    async def 한_건(입력):
        return _스펙, "S2_SEARCH", False

    글 = to_markdown(await evaluate(기록, 한_건), "test")
    assert "router-g-0002" in 글 and "세트 짜줘" in 글 and "ambiguous" in 글


@pytest.mark.asyncio
async def test_입력에_적힌_값을_그대로_넘긴다():
    """조건 수정은 직전 job 이 있어야 그 경로로 간다. raw_query 만 넘기면
    라우터가 새 검색으로 내려서, 영영 오답으로 잡힌다."""
    받은: dict = {}

    async def 한_건(입력):
        받은.update(입력)
        return _스펙, "S7_REFINE", False

    await evaluate(
        [{"id": "router-g-0301",
          "input": {"raw_query": "더 저렴한 걸로", "parent_job_id": "prev"},
          "expected": {"scenario": "S7_REFINE"}}],
        한_건,
    )
    assert 받은["parent_job_id"] == "prev"


def _실험_인자(**값):
    import argparse

    기본 = dict(condition="b0", runs=1, concurrency=1, threshold=None, vague_threshold=None,
              dump=None, load=None, fit_target=None, version="v2", split="dev", out=None)
    return argparse.Namespace(**{**기본, **값})


def test_불러온_결과의_리포트에는_실행한_커밋과_다시_채점한_커밋을_따로_적는다(tmp_path, monkeypatch):
    import json

    from eval import run_router_eval

    기록 = [{"id": "q1", "input": {"raw_query": "선크림 추천"},
             "expected": {"scenario": "S2_SEARCH"}, "tags": []}]
    저장 = tmp_path / "b0.json"
    저장.write_text(json.dumps({"코드": "c1", "runs": [[{
        "id": "q1", "seconds": 0.1, "calls": [], "error": None,
        "outcome": {"spec": {"request_type": "SEARCH"}, "scenario": "S2_SEARCH"},
    }]]}), encoding="utf-8")

    monkeypatch.setattr(run_router_eval, "_코드_버전", lambda: "c2")
    리포트 = tmp_path / "2.md"
    다시_저장 = tmp_path / "again.json"
    run_router_eval._실험(_실험_인자(load=str(저장), out=str(리포트), dump=str(다시_저장)), 기록)
    글 = 리포트.read_text(encoding="utf-8")
    assert "- 코드: c1" in 글
    assert "- 다시 채점한 코드: c2" in 글
    # 다시 저장해도 실행한 커밋이 남는다
    assert json.loads(다시_저장.read_text(encoding="utf-8"))["코드"] == "c1"


def test_커밋을_적기_전에_저장한_결과도_읽는다(tmp_path):
    import json

    from eval.run_router_eval import _실행_결과_읽기

    기록 = [{"id": "q1", "input": {"raw_query": "q"}, "expected": {}, "tags": []}]
    예전 = tmp_path / "old.json"
    예전.write_text(json.dumps([[{"id": "q1", "outcome": None, "seconds": 0.1,
                                  "calls": [], "error": "x"}]]), encoding="utf-8")
    runs, 코드 = _실행_결과_읽기(예전, 기록)
    assert len(runs[0]) == 1
    assert 코드.startswith("알 수 없음")
