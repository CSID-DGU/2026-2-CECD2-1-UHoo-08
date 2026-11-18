"""시나리오 결정 실험의 측정 항목 계산을 본다.

계산이 틀리면 리포트 숫자가 전부 틀린 값이 되는데, 숫자만 봐서는 알아챌 수 없다.
"""
from dataclasses import dataclass

import pytest

from eval.router_metrics import (
    Outcome,
    Thresholds,
    Trial,
    calibration_error,
    clarify_precision_recall,
    cost_per_1000,
    coverage_curve,
    decide_clarify,
    fit_threshold,
    mean_and_spread,
    percentile,
    repeat_agreement,
    request_type_macro_f1,
    scenario_accuracy,
    to_markdown,
    value_match_rate,
    wrong_cases,
)


def _문제(아이디: str, **기대) -> dict:
    return {"id": 아이디, "input": {"raw_query": 아이디}, "expected": 기대, "tags": []}


def _실행(rec: dict, 시나리오: str = "S2_SEARCH", 종류: str = "SEARCH", **옵션) -> Trial:
    spec = {"request_type": 종류, **옵션.pop("spec", {})}
    return Trial(rec=rec, outcome=Outcome(spec=spec, scenario=시나리오, **옵션))


def test_규칙에_걸리면_확률과_상관없이_되묻는다():
    나온 = Outcome(spec={}, scenario="S2_SEARCH", clarify_rule=True, scenario_prob=0.99)
    assert decide_clarify(나온, Thresholds(scenario=0.6))


def test_시나리오_확률이_기준보다_낮으면_되묻는다():
    기준 = Thresholds(scenario=0.6)
    assert decide_clarify(Outcome(spec={}, scenario="S2_SEARCH", scenario_prob=0.59), 기준)
    assert not decide_clarify(Outcome(spec={}, scenario="S2_SEARCH", scenario_prob=0.6), 기준)


def test_막연함_확률이_기준보다_높으면_되묻는다():
    기준 = Thresholds(vague=0.5)
    assert decide_clarify(Outcome(spec={}, scenario="S2_SEARCH", vague_prob=0.7), 기준)
    assert not decide_clarify(Outcome(spec={}, scenario="S2_SEARCH", vague_prob=0.3), 기준)


def test_확률을_내지_않는_조건은_규칙만_본다():
    assert not decide_clarify(Outcome(spec={}, scenario="S2_SEARCH"), Thresholds(scenario=0.6))


def test_시나리오_일치율은_시나리오가_적힌_문제만_센다():
    실행 = [
        _실행(_문제("a", scenario="S2_SEARCH")),
        _실행(_문제("b", scenario="S1_EVALUATE")),
        _실행(_문제("c", needs_clarification=True)),
    ]
    assert scenario_accuracy(실행) == pytest.approx(0.5)


def test_오류가_난_문제는_틀린_것으로_센다():
    실행 = [
        _실행(_문제("a", scenario="S2_SEARCH")),
        Trial(rec=_문제("b", scenario="S2_SEARCH"), outcome=None, error="boom"),
    ]
    assert scenario_accuracy(실행) == pytest.approx(0.5)


def test_요청_종류_점수는_종류마다_따로_내서_평균한다():
    # SEARCH: 정답 2 중 2 를 맞히고 EVALUATE 하나를 SEARCH 로 잘못 읽었다 → F1 0.8
    # EVALUATE: 정답 2 중 1 → F1 2/3
    실행 = [
        _실행(_문제("a", request_type="SEARCH"), 종류="SEARCH"),
        _실행(_문제("b", request_type="SEARCH"), 종류="SEARCH"),
        _실행(_문제("c", request_type="EVALUATE"), 종류="EVALUATE"),
        _실행(_문제("d", request_type="EVALUATE"), 종류="SEARCH"),
    ]
    assert request_type_macro_f1(실행) == pytest.approx((0.8 + 2 / 3) / 2)


def test_값_일치율은_적힌_항목만_센다():
    실행 = [
        _실행(_문제("a", category="base", budget_max=30000, scenario="S2_SEARCH"),
              spec={"category": "base", "budget": {"max": 20000}}),
        _실행(_문제("b", base_product_ref_present=True),
              spec={"base_product_ref": "어떤 쿠션"}),
    ]
    assert value_match_rate(실행) == pytest.approx(2 / 3)


def test_되묻기_정밀도와_재현율():
    기준 = Thresholds(scenario=0.6)
    실행 = [
        _실행(_문제("a", needs_clarification=True), scenario_prob=0.2),    # 맞게 되물음
        _실행(_문제("b", needs_clarification=True), scenario_prob=0.9),    # 놓침
        _실행(_문제("c", needs_clarification=False), scenario_prob=0.3),   # 쓸데없이 되물음
        _실행(_문제("d", needs_clarification=False), scenario_prob=0.9),
        _실행(_문제("e", scenario="S2_SEARCH"), scenario_prob=0.1),        # 정답이 없어 세지 않음
    ]
    정밀도, 재현율 = clarify_precision_recall(실행, 기준)
    assert 정밀도 == pytest.approx(0.5)
    assert 재현율 == pytest.approx(0.5)


def test_한_번도_되묻지_않으면_정밀도는_값이_없다():
    실행 = [_실행(_문제("a", needs_clarification=True))]
    정밀도, 재현율 = clarify_precision_recall(실행, Thresholds())
    assert 정밀도 is None
    assert 재현율 == 0.0


def test_확률이_실제_정답률과_같으면_오차는_0이다():
    쌍 = [(0.75, True)] * 3 + [(0.75, False)]
    assert calibration_error(쌍) == pytest.approx(0.0)


def test_확률_오차는_칸마다_차이를_문제_수로_가중한다():
    # 0.9 칸: 2건 중 1건 맞음 → 차이 0.4, 0.1 칸: 2건 중 0건 → 차이 0.1
    쌍 = [(0.9, True), (0.9, False), (0.1, False), (0.1, False)]
    assert calibration_error(쌍) == pytest.approx(0.5 * 0.4 + 0.5 * 0.1)


def test_확률_1은_마지막_칸에_든다():
    assert calibration_error([(1.0, True)]) == pytest.approx(0.0)


def _곡선용_실행() -> list[Trial]:
    return [
        _실행(_문제("a", scenario="S2_SEARCH"), scenario_prob=0.4, 시나리오="S1_EVALUATE"),
        _실행(_문제("b", scenario="S2_SEARCH"), scenario_prob=0.6),
        _실행(_문제("c", scenario="S2_SEARCH"), scenario_prob=0.8, 시나리오="S6_BUNDLE"),
        _실행(_문제("d", scenario="S2_SEARCH"), scenario_prob=1.0),
    ]


def test_처리_비율별_일치율():
    곡선 = coverage_curve(_곡선용_실행())
    assert 곡선 == [
        (0.4, 1.0, pytest.approx(0.5)),
        (0.6, 0.75, pytest.approx(2 / 3)),
        (0.8, 0.5, pytest.approx(0.5)),
        (1.0, 0.25, pytest.approx(1.0)),
    ]


def test_목표를_채우는_가장_낮은_기준값을_고른다():
    assert fit_threshold(_곡선용_실행(), 0.6) == 0.6
    assert fit_threshold(_곡선용_실행(), 0.97) == 1.0


def test_어떤_기준으로도_목표에_못_미치면_값이_없다():
    실행 = [_실행(_문제("a", scenario="S2_SEARCH"), scenario_prob=0.9, 시나리오="S1_EVALUATE")]
    assert fit_threshold(실행, 0.97) is None


def test_반복_일치율은_시나리오와_되묻기가_모두_같아야_센다():
    a, b = _문제("a", scenario="S2_SEARCH"), _문제("b", scenario="S2_SEARCH")
    기준 = Thresholds(scenario=0.6)
    runs = [
        [_실행(a, scenario_prob=0.9), _실행(b, scenario_prob=0.9)],
        [_실행(a, scenario_prob=0.8), _실행(b, scenario_prob=0.5)],   # b 는 되묻기가 달라졌다
    ]
    assert repeat_agreement(runs, 기준) == pytest.approx(0.5)


def test_한_번만_실행하면_반복_일치율은_값이_없다():
    assert repeat_agreement([[_실행(_문제("a"))]], Thresholds()) is None


def test_순위로_가운데_값과_느린_쪽_값을_낸다():
    값 = [float(i) for i in range(1, 101)]
    assert percentile(값, 50) == 50.0
    assert percentile(값, 95) == 95.0
    assert percentile([], 50) is None


@dataclass
class _호출:
    model: str
    input_tokens: int
    output_tokens: int


def test_비용은_기록된_토큰으로_계산한다():
    실행 = [
        Trial(rec=_문제("a"), outcome=None, calls=[_호출("qwen-plus", 1_000_000, 0)]),
        Trial(rec=_문제("b"), outcome=None, calls=[_호출("qwen-plus", 0, 1_000_000)]),
    ]
    # 입력 0.26 달러 + 출력 0.78 달러를 2건이 썼다 → 1,000건이면 520 달러
    assert cost_per_1000(실행) == pytest.approx(520.0)


def test_가격을_모르는_모델이_있으면_비용을_내지_않는다():
    실행 = [Trial(rec=_문제("a"), outcome=None, calls=[_호출("모르는-모델", 10, 10)])]
    assert cost_per_1000(실행) is None


def test_평균과_표준편차():
    평균, 편차 = mean_and_spread([0.8, 0.9, None, 1.0])
    assert 평균 == pytest.approx(0.9)
    assert 편차 == pytest.approx(0.1)
    assert mean_and_spread([0.5]) == (0.5, None)
    assert mean_and_spread([None]) == (None, None)


def test_틀린_문제에는_몇_번_틀렸는지가_남는다():
    a = _문제("a", scenario="S2_SEARCH", needs_clarification=False)
    runs = [
        [_실행(a)],
        [_실행(a, 시나리오="S1_EVALUATE")],
        [_실행(a, clarify_rule=True)],
    ]
    틀림 = wrong_cases(runs, Thresholds())
    assert len(틀림) == 1
    assert 틀림[0]["횟수"] == 2
    assert set(틀림[0]["틀린_항목"]) == {"scenario", "needs_clarification"}


def test_리포트에_측정값과_틀린_문제가_들어간다():
    a = _문제("router-g-1001", scenario="S2_SEARCH", needs_clarification=False)
    runs = [[_실행(a, scenario_prob=0.9)], [_실행(a, scenario_prob=0.9, 시나리오="S1_EVALUATE")]]
    글 = to_markdown(runs=runs, thr=Thresholds(scenario=0.6), 머리말={"조건": "A1", "날짜": "2026-11-19"})
    assert "시나리오 일치율 | 50.0%" in 글
    assert "반복 일치율 | 0.0%" in 글
    assert "router-g-1001" in 글
    assert "2번 중 1번" in 글


def test_막연함_확률_기준값은_되묻기_판단이_가장_잘_맞는_값을_고른다():
    from eval.router_metrics import fit_vague_threshold

    실행 = [
        _실행(_문제("a", needs_clarification=True), vague_prob=0.9),
        _실행(_문제("b", needs_clarification=True), vague_prob=0.7),
        _실행(_문제("c", needs_clarification=False), vague_prob=0.6),
        _실행(_문제("d", needs_clarification=False), vague_prob=0.2),
    ]
    # 0.6 보다 높으면 되묻는다고 해야 둘을 다 잡고 헛짚지 않는다
    assert fit_vague_threshold(실행, None) == 0.6


def test_막연함_확률을_내지_않는_조건은_기준값이_없다():
    from eval.router_metrics import fit_vague_threshold

    assert fit_vague_threshold([_실행(_문제("a", needs_clarification=True))], None) is None


def test_실행_결과를_적었다가_다시_읽어도_측정값이_같다():
    from eval.router_metrics import from_records, summarize_run, to_records

    문제들 = [_문제("a", scenario="S2_SEARCH", needs_clarification=False),
              _문제("b", needs_clarification=True)]
    runs = [[
        _실행(문제들[0], scenario_prob=0.9, spec={"category": "base"}),
        Trial(rec=문제들[1], outcome=None, error="boom", calls=[_호출("qwen-plus", 10, 2)]),
    ]]
    for t in runs[0]:
        for c in t.calls:
            c.seconds = 0.5

    읽은 = from_records(to_records(runs), 문제들)
    기준 = Thresholds(scenario=0.6)
    assert summarize_run(읽은[0], 기준) == summarize_run(runs[0], 기준)
    assert 읽은[0][1].error == "boom"


def test_견주지_않는_조건은_견준_결과가_없다():
    from eval.router_metrics import agreement_stats

    assert agreement_stats([_실행(_문제("a", scenario="S2_SEARCH"))]) is None


def test_요청_종류를_견준_결과를_같았을_때와_달랐을_때로_나눠_센다():
    from eval.router_metrics import agreement_stats

    실행 = [
        _실행(_문제("a", scenario="S2_SEARCH"), agreement="same"),
        _실행(_문제("b", scenario="S1_EVALUATE"), agreement="same"),
        _실행(_문제("c", scenario="S2_SEARCH"), agreement="resolved"),
        _실행(_문제("d", scenario="S1_EVALUATE"), agreement="resolved"),
        _실행(_문제("e", scenario="S2_SEARCH"), agreement="unresolved", clarify_rule=True),
        _실행(_문제("f", scenario="S2_SEARCH")),
    ]
    결과 = agreement_stats(실행)

    assert 결과["견준 수"] == 5
    assert 결과["같았던 비율"] == pytest.approx(0.4)
    assert 결과["같았을 때 시나리오 일치율"] == pytest.approx(0.5)
    assert 결과["달랐을 때 시나리오 일치율"] == pytest.approx(2 / 3)
    assert 결과["다시 해석해 같아진 비율"] == pytest.approx(2 / 3)
    # 같아진 둘 중 하나는 틀린 시나리오로 같아졌다
    assert 결과["다시 해석해 맞게 정해진 비율"] == pytest.approx(1 / 3)
    assert 결과["사용자에게 물은 비율"] == pytest.approx(1 / 3)


def test_견준_결과는_적었다가_다시_읽어도_남고_리포트에_들어간다():
    from eval.router_metrics import from_records, to_records

    문제 = _문제("a", scenario="S2_SEARCH", needs_clarification=False)
    runs = [[_실행(문제, agreement="resolved", vague_prob=0.2)]]

    읽은 = from_records(to_records(runs), [문제])
    assert 읽은[0][0].outcome.agreement == "resolved"

    글 = to_markdown(runs=읽은, thr=Thresholds(vague=0.6), 머리말={"조건": "A5"})
    assert "요청 종류가 같았던 비율 | 0.0% (0 / 1)" in 글
    assert "사용자에게까지 물은 비율 | 0.0%" in 글


def test_견주지_않는_조건의_리포트에는_견주기_항목이_없다():
    문제 = _문제("a", scenario="S2_SEARCH")
    글 = to_markdown(runs=[[_실행(문제)]], thr=Thresholds(), 머리말={"조건": "A2"})
    assert "견주기" not in 글
