"""시나리오 결정 실험의 측정 항목.

조건(지금 방식, 구조 규칙, 반복 질문 등)이 문제 하나에 내놓은 결과를 받아
정확도, 되묻기 판단, 확률의 믿을 만한 정도, 시간, 비용을 계산한다.
LLM 을 부르지 않으므로 키 없이 테스트할 수 있다.

조건은 되물을지를 직접 정하지 않고 재료만 내놓는다(Outcome). 확률을 어느
기준에서 자를지는 여기서 정한다. 그래야 같은 실행 결과로 기준값을 바꿔 가며
볼 수 있고, 기준값을 연습용 문제에서 정할 수 있다.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

# 요청 종류. 요청 종류 점수는 이 넷을 따로 채점해 평균 낸다.
REQUEST_TYPES = ("SEARCH", "EVALUATE", "BUNDLE", "REFINE")

# 값 일치율에 넣는 항목. 문장에서 꺼낸 값만 본다.
VALUE_KEYS = (
    "category", "target", "use_env", "value_seeking",
    "budget_max", "budget_total", "base_product_ref_present",
)

# 모델별 100만 토큰당 가격(달러): (입력, 출력).
# 2026년 11월 DashScope 콘솔에서 확인한 값이다. 가격이 바뀌면 여기를 고친다.
# 여기 없는 모델은 비용을 계산하지 않는다.
PRICES_PER_1M: dict[str, tuple[float, float]] = {
    "qwen-plus": (0.26, 0.78),
    # Jev 는 입력 토큰에만 값을 매긴다 (TypeSafe 모델 문서, 2026년 11월)
    "jev-1.14.0": (0.042, 0.0),
}


@dataclass
class Outcome:
    """조건 하나가 문제 하나에 내놓은 결과."""

    spec: dict                               # 뽑아낸 값. 값을 뽑지 않는 조건은 request_type 만 담는다
    scenario: str
    clarify_rule: bool = False               # 확률과 상관없이 되물어야 한다 (필수 값이 비었다 등)
    scenario_prob: Optional[float] = None    # 시나리오를 맞혔을 확률. 내지 않는 조건은 None
    vague_prob: Optional[float] = None       # 막연한 질문일 확률. 내지 않는 조건은 None
    extracts_values: bool = True             # 값 뽑기를 하는 조건인가. 아니면 값 일치율에서 뺀다
    # LLM 과 Jev 가 고른 요청 종류를 견준 결과. 견주지 않는 조건은 None
    # same: 처음부터 같았다, resolved: 다시 해석해 같아졌다, unresolved: 끝까지 달라 사용자에게 묻는다
    agreement: Optional[str] = None


@dataclass
class Trial:
    """문제 하나를 한 번 실행한 기록."""

    rec: dict
    outcome: Optional[Outcome]               # 실행 중 오류가 나면 None
    seconds: float = 0.0
    calls: list = field(default_factory=list)   # 이 문제를 푸는 동안의 LLM 호출 기록
    error: str = ""


@dataclass(frozen=True)
class Thresholds:
    """되물을지를 가르는 기준값."""

    scenario: Optional[float] = None   # 시나리오 확률이 이보다 낮으면 되묻는다
    vague: Optional[float] = None      # 막연한 질문일 확률이 이보다 높으면 되묻는다


def decide_clarify(outcome: Outcome, thr: Thresholds) -> bool:
    """되물을지. 규칙에 걸리거나 확률이 기준을 넘지 못하면 되묻는다."""
    if outcome.clarify_rule:
        return True
    if thr.scenario is not None and outcome.scenario_prob is not None:
        if outcome.scenario_prob < thr.scenario:
            return True
    if thr.vague is not None and outcome.vague_prob is not None:
        if outcome.vague_prob > thr.vague:
            return True
    return False


# 기대값의 키 → 결과에서 그 값을 꺼내는 법. eval/run_router_eval.py 와 같은 뜻이다.
_꺼내기: dict[str, Callable[[dict], Any]] = {
    "request_type": lambda spec: spec.get("request_type"),
    "category": lambda spec: spec.get("category"),
    "target": lambda spec: spec.get("target"),
    "use_env": lambda spec: spec.get("use_env"),
    "value_seeking": lambda spec: spec.get("value_seeking"),
    "budget_max": lambda spec: (spec.get("budget") or {}).get("max"),
    "budget_total": lambda spec: (spec.get("budget") or {}).get("total"),
    "base_product_ref_present": lambda spec: bool(spec.get("base_product_ref")),
}


def _비율(맞음: int, 전체: int) -> Optional[float]:
    return 맞음 / 전체 if 전체 else None


def _시나리오_문제(trials: Sequence[Trial]) -> list[Trial]:
    return [t for t in trials if "scenario" in t.rec["expected"]]


def _시나리오_맞음(t: Trial) -> bool:
    return t.outcome is not None and t.outcome.scenario == t.rec["expected"]["scenario"]


def scenario_accuracy(trials: Sequence[Trial]) -> Optional[float]:
    """정답 시나리오로 간 비율. 오류가 난 문제는 틀린 것으로 센다."""
    대상 = _시나리오_문제(trials)
    return _비율(sum(_시나리오_맞음(t) for t in 대상), len(대상))


def request_type_macro_f1(trials: Sequence[Trial]) -> Optional[float]:
    """요청 종류마다 F1 을 구해 평균 낸다. 정답에도 예측에도 없는 종류는 뺀다."""
    쌍 = [
        (t.rec["expected"]["request_type"],
         t.outcome.spec.get("request_type") if t.outcome else None)
        for t in trials if "request_type" in t.rec["expected"]
    ]
    if not 쌍:
        return None
    점수 = []
    for 종류 in REQUEST_TYPES:
        tp = sum(정답 == 종류 and 예측 == 종류 for 정답, 예측 in 쌍)
        fp = sum(정답 != 종류 and 예측 == 종류 for 정답, 예측 in 쌍)
        fn = sum(정답 == 종류 and 예측 != 종류 for 정답, 예측 in 쌍)
        if tp + fp + fn == 0:
            continue
        점수.append(2 * tp / (2 * tp + fp + fn))
    return statistics.fmean(점수) if 점수 else None


def value_match_rate(trials: Sequence[Trial]) -> Optional[float]:
    """뽑아낸 값이 정답과 같은 비율. 문제에 적힌 항목만 센다.

    값 뽑기를 하지 않는 조건의 결과는 세지 않는다.
    """
    맞음 = 전체 = 0
    for t in trials:
        if t.outcome is not None and not t.outcome.extracts_values:
            continue
        for 키 in VALUE_KEYS:
            if 키 not in t.rec["expected"]:
                continue
            전체 += 1
            if t.outcome is not None and _꺼내기[키](t.outcome.spec) == t.rec["expected"][키]:
                맞음 += 1
    return _비율(맞음, 전체)


def clarify_precision_recall(
    trials: Sequence[Trial], thr: Thresholds,
) -> tuple[Optional[float], Optional[float]]:
    """되묻기 정밀도와 재현율. 되물어야 하는지가 적힌 문제만 센다.

    오류가 난 문제는 되묻지 않은 것으로 센다.
    """
    tp = fp = fn = 0
    for t in trials:
        if "needs_clarification" not in t.rec["expected"]:
            continue
        정답 = bool(t.rec["expected"]["needs_clarification"])
        예측 = t.outcome is not None and decide_clarify(t.outcome, thr)
        tp += 정답 and 예측
        fp += (not 정답) and 예측
        fn += 정답 and not 예측
    return _비율(tp, tp + fp), _비율(tp, tp + fn)


def _확률_있는_문제(trials: Sequence[Trial]) -> list[Trial]:
    """시나리오 정답이 적혀 있고, 조건이 시나리오 확률을 낸 문제."""
    return [
        t for t in _시나리오_문제(trials)
        if t.outcome is not None and t.outcome.scenario_prob is not None
    ]


def calibration_error(
    쌍: Sequence[tuple[float, bool]], bins: int = 10,
) -> Optional[float]:
    """확률과 실제 정답률의 차이(ECE). 0 에 가까울수록 그 확률을 믿을 수 있다.

    확률을 같은 너비의 칸으로 나누고, 칸마다 평균 확률과 실제 정답률의 차이를
    구해 칸에 든 문제 수로 가중 평균한다.
    """
    if not 쌍:
        return None
    칸: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for 확률, 맞음 in 쌍:
        칸[min(int(확률 * bins), bins - 1)].append((확률, 맞음))
    오차 = 0.0
    for 묶음 in 칸:
        if not 묶음:
            continue
        평균_확률 = statistics.fmean(p for p, _ in 묶음)
        정답률 = sum(m for _, m in 묶음) / len(묶음)
        오차 += len(묶음) / len(쌍) * abs(평균_확률 - 정답률)
    return 오차


def scenario_calibration_error(trials: Sequence[Trial], bins: int = 10) -> Optional[float]:
    """시나리오 확률의 오차."""
    return calibration_error(
        [(t.outcome.scenario_prob, _시나리오_맞음(t)) for t in _확률_있는_문제(trials)], bins,
    )


def vague_calibration_error(trials: Sequence[Trial], bins: int = 10) -> Optional[float]:
    """막연한 질문일 확률의 오차. 그 확률을 내는 조건만 값이 나온다."""
    return calibration_error(
        [
            (t.outcome.vague_prob, bool(t.rec["expected"]["needs_clarification"]))
            for t in trials
            if t.outcome is not None and t.outcome.vague_prob is not None
            and "needs_clarification" in t.rec["expected"]
        ],
        bins,
    )


def coverage_curve(trials: Sequence[Trial]) -> list[tuple[float, float, float]]:
    """기준값마다 (기준값, 처리한 비율, 처리한 것 중 시나리오를 맞힌 비율).

    시나리오 확률이 기준 이상인 질문만 되묻지 않고 처리한다고 볼 때의 값이다.
    기준값 후보는 실제로 나온 확률들이다. 낮은 기준부터 적는다.
    """
    대상 = _확률_있는_문제(trials)
    곡선 = []
    for 기준 in sorted({t.outcome.scenario_prob for t in 대상}):
        처리 = [t for t in 대상 if t.outcome.scenario_prob >= 기준]
        곡선.append((
            기준,
            len(처리) / len(대상),
            sum(_시나리오_맞음(t) for t in 처리) / len(처리),
        ))
    return 곡선


def fit_threshold(trials: Sequence[Trial], target: float) -> Optional[float]:
    """처리한 질문의 시나리오 일치율이 목표 이상이 되는 가장 낮은 기준값.

    감으로 정하지 않기 위한 규칙이다. 연습용 문제에서만 쓴다.
    어떤 기준으로도 목표에 못 미치면 None.
    """
    for 기준, _, 일치율 in coverage_curve(trials):
        if 일치율 >= target:
            return 기준
    return None


def fit_vague_threshold(trials: Sequence[Trial], scenario: Optional[float]) -> Optional[float]:
    """되묻기 판단의 F1 이 가장 높아지는 막연함 확률 기준값.

    시나리오 확률 기준값은 먼저 정해 두고 그대로 둔 채 찾는다. 후보는 실제로 나온
    확률들이다. F1 이 같으면 낮은 기준값을 고른다. 연습용 문제에서만 쓴다.
    막연함 확률을 내지 않는 조건이면 None.
    """
    후보 = sorted({
        t.outcome.vague_prob for t in trials
        if t.outcome is not None and t.outcome.vague_prob is not None
    })
    가장_좋은: tuple[float, Optional[float]] = (-1.0, None)
    for 기준 in 후보:
        정밀도, 재현율 = clarify_precision_recall(trials, Thresholds(scenario=scenario, vague=기준))
        f1 = 2 * 정밀도 * 재현율 / (정밀도 + 재현율) if 정밀도 and 재현율 else 0.0
        if f1 > 가장_좋은[0]:
            가장_좋은 = (f1, 기준)
    return 가장_좋은[1]


def agreement_stats(trials: Sequence[Trial]) -> Optional[dict[str, Any]]:
    """LLM 과 Jev 가 고른 요청 종류를 견준 결과. 견주는 조건이 아니면 None.

    같았을 때와 달랐을 때의 시나리오 일치율은 시나리오 정답이 적힌 문제로만 낸다.
    다시 해석해 맞게 정해졌다는 것은 두 답이 같아졌고 그 시나리오가 정답이라는 뜻이다.
    """
    견준 = [t for t in trials if t.outcome is not None and t.outcome.agreement is not None]
    if not 견준:
        return None
    같음 = [t for t in 견준 if t.outcome.agreement == "same"]
    다름 = [t for t in 견준 if t.outcome.agreement != "same"]
    다름_채점 = _시나리오_문제(다름)
    return {
        "견준 수": len(견준),
        "같았던 수": len(같음),
        "같았던 비율": len(같음) / len(견준),
        "같았을 때 시나리오 일치율": scenario_accuracy(같음),
        "달랐던 수": len(다름),
        "달랐을 때 시나리오 일치율": scenario_accuracy(다름),
        "다시 해석해 같아진 비율": _비율(sum(t.outcome.agreement == "resolved" for t in 다름), len(다름)),
        "다시 해석해 맞게 정해진 비율": _비율(
            sum(t.outcome.agreement == "resolved" and _시나리오_맞음(t) for t in 다름_채점),
            len(다름_채점),
        ),
        "사용자에게 물은 비율": _비율(sum(t.outcome.agreement == "unresolved" for t in 다름), len(다름)),
    }


def to_records(runs: Sequence[Sequence[Trial]]) -> list[list[dict]]:
    """실행 결과를 파일에 적을 수 있는 모양으로 바꾼다. 문제는 id 만 적는다."""
    return [
        [
            {
                "id": t.rec["id"],
                "outcome": None if t.outcome is None else {
                    "spec": t.outcome.spec,
                    "scenario": t.outcome.scenario,
                    "clarify_rule": t.outcome.clarify_rule,
                    "scenario_prob": t.outcome.scenario_prob,
                    "vague_prob": t.outcome.vague_prob,
                    "extracts_values": t.outcome.extracts_values,
                    "agreement": t.outcome.agreement,
                },
                "seconds": t.seconds,
                "calls": [
                    {"model": c.model, "input_tokens": c.input_tokens,
                     "output_tokens": c.output_tokens, "seconds": c.seconds}
                    for c in t.calls
                ],
                "error": t.error,
            }
            for t in run
        ]
        for run in runs
    ]


@dataclass(frozen=True)
class _적어_둔_호출:
    model: str
    input_tokens: int
    output_tokens: int
    seconds: float


def from_records(적힌: Sequence[Sequence[dict]], 기록: Sequence[dict]) -> list[list[Trial]]:
    """파일에 적어 둔 실행 결과를 다시 읽는다. 기준값만 바꿔 다시 채점할 때 쓴다."""
    문제 = {rec["id"]: rec for rec in 기록}
    return [
        [
            Trial(
                rec=문제[줄["id"]],
                outcome=Outcome(**줄["outcome"]) if 줄["outcome"] else None,
                seconds=줄["seconds"],
                calls=[_적어_둔_호출(**c) for c in 줄["calls"]],
                error=줄["error"],
            )
            for 줄 in run
        ]
        for run in 적힌
    ]


def repeat_agreement(runs: Sequence[Sequence[Trial]], thr: Thresholds) -> Optional[float]:
    """같은 질문을 여러 번 넣었을 때 시나리오와 되묻기 판단이 모두 같았던 비율."""
    if len(runs) < 2:
        return None
    문제별: dict[str, set] = {}
    for run in runs:
        for t in run:
            결과 = (
                (t.outcome.scenario, decide_clarify(t.outcome, thr))
                if t.outcome is not None else ("오류", False)
            )
            문제별.setdefault(t.rec["id"], set()).add(결과)
    return _비율(sum(len(v) == 1 for v in 문제별.values()), len(문제별))


def percentile(값: Sequence[float], q: float) -> Optional[float]:
    """줄 세웠을 때 q 번째(0~100) 값. 가장 가까운 순위를 쓴다."""
    if not 값:
        return None
    순서 = sorted(값)
    return 순서[max(0, math.ceil(q / 100 * len(순서)) - 1)]


def cost_per_1000(trials: Sequence[Trial]) -> Optional[float]:
    """질문 1,000건당 금액(달러). 가격을 모르는 모델이 섞여 있으면 None."""
    if not trials:
        return None
    합 = 0.0
    for t in trials:
        for c in t.calls:
            if c.model not in PRICES_PER_1M:
                return None
            입력가, 출력가 = PRICES_PER_1M[c.model]
            합 += (c.input_tokens * 입력가 + c.output_tokens * 출력가) / 1_000_000
    return 합 / len(trials) * 1000


def summarize_run(trials: Sequence[Trial], thr: Thresholds) -> dict[str, Optional[float]]:
    """한 번 실행한 결과의 측정값."""
    정밀도, 재현율 = clarify_precision_recall(trials, thr)
    시간 = [t.seconds for t in trials if t.outcome is not None]
    호출 = [c for t in trials for c in t.calls]
    return {
        "시나리오 일치율": scenario_accuracy(trials),
        "요청 종류 점수(macro-F1)": request_type_macro_f1(trials),
        "값 일치율": value_match_rate(trials),
        "되묻기 정밀도": 정밀도,
        "되묻기 재현율": 재현율,
        "시나리오 확률의 오차": scenario_calibration_error(trials),
        "막연함 확률의 오차": vague_calibration_error(trials),
        "걸린 시간 가운데 값(초)": percentile(시간, 50),
        "걸린 시간 느린 쪽 값(초)": percentile(시간, 95),
        "질문당 LLM 호출 수": len(호출) / len(trials) if trials else None,
        "질문당 입력 토큰": sum(c.input_tokens for c in 호출) / len(trials) if trials else None,
        "질문당 출력 토큰": sum(c.output_tokens for c in 호출) / len(trials) if trials else None,
        "1,000건당 비용(달러)": cost_per_1000(trials),
    }


def mean_and_spread(값들: Sequence[Optional[float]]) -> tuple[Optional[float], Optional[float]]:
    """반복 실행한 값의 평균과 표준편차. 한 번뿐이면 표준편차는 None."""
    있는 = [v for v in 값들 if v is not None]
    if not 있는:
        return None, None
    return statistics.fmean(있는), (statistics.stdev(있는) if len(있는) > 1 else None)


def wrong_cases(runs: Sequence[Sequence[Trial]], thr: Thresholds) -> list[dict]:
    """한 번이라도 틀린 문제와, 몇 번 틀렸는지."""
    문제별: dict[str, dict] = {}
    for run in runs:
        for t in run:
            기대 = t.rec["expected"]
            틀린: dict[str, Any] = {}
            if t.outcome is None:
                틀린["실행"] = t.error
            else:
                if "scenario" in 기대 and t.outcome.scenario != 기대["scenario"]:
                    틀린["scenario"] = t.outcome.scenario
                if "request_type" in 기대 and t.outcome.spec.get("request_type") != 기대["request_type"]:
                    틀린["request_type"] = t.outcome.spec.get("request_type")
                if "needs_clarification" in 기대:
                    되물음 = decide_clarify(t.outcome, thr)
                    if 되물음 != bool(기대["needs_clarification"]):
                        틀린["needs_clarification"] = 되물음
            if not 틀린:
                continue
            항목 = 문제별.setdefault(t.rec["id"], {
                "id": t.rec["id"], "query": t.rec["input"]["raw_query"],
                "tags": t.rec.get("tags") or [], "횟수": 0, "틀린_항목": {},
            })
            항목["횟수"] += 1
            for 키, 실제 in 틀린.items():
                항목["틀린_항목"].setdefault(키, {"기대": 기대.get(키), "실제": []})["실제"].append(실제)
    return sorted(문제별.values(), key=lambda x: x["id"])


def _숫자(v: Optional[float], 퍼센트: bool) -> str:
    if v is None:
        return "-"
    return f"{v * 100:.1f}%" if 퍼센트 else f"{v:.3f}"


_퍼센트_항목 = {
    "시나리오 일치율", "값 일치율", "되묻기 정밀도", "되묻기 재현율",
}


def to_markdown(
    *,
    runs: Sequence[Sequence[Trial]],
    thr: Thresholds,
    머리말: dict[str, str],
) -> str:
    """조건 하나의 리포트. 머리말에는 날짜, 조건, 모델 같은 실행 정보를 넣는다."""
    줄 = [f"# 시나리오 결정 실험: {머리말.get('조건', '')}", ""]
    줄 += [f"- {키}: {값}" for 키, 값 in 머리말.items()]
    줄 += [
        f"- 반복: {len(runs)}번",
        f"- 시나리오 확률 기준값: {thr.scenario if thr.scenario is not None else '쓰지 않음'}",
        f"- 막연함 확률 기준값: {thr.vague if thr.vague is not None else '쓰지 않음'}",
        "",
        "## 측정값",
        "",
        "| 항목 | 평균 | 표준편차 | 실행별 |",
        "| --- | ---: | ---: | --- |",
    ]
    요약들 = [summarize_run(run, thr) for run in runs]
    for 키 in 요약들[0]:
        값들 = [요약[키] for 요약 in 요약들]
        평균, 편차 = mean_and_spread(값들)
        퍼 = 키 in _퍼센트_항목
        줄.append(
            f"| {키} | {_숫자(평균, 퍼)} | {_숫자(편차, 퍼)} | "
            f"{', '.join(_숫자(v, 퍼) for v in 값들)} |"
        )
    일치 = repeat_agreement(runs, thr)
    줄.append(f"| 반복 일치율 | {_숫자(일치, True)} | - | - |")

    곡선 = coverage_curve([t for run in runs for t in run])
    줄 += ["", "## 처리 비율별 시나리오 일치율", ""]
    if 곡선:
        줄 += [
            "시나리오 확률이 기준 이상인 질문만 되묻지 않고 처리할 때의 값이다. 반복 실행을 모두 합쳐 계산했다.",
            "",
            "| 기준값 | 처리한 비율 | 처리한 것 중 시나리오 일치율 |",
            "| ---: | ---: | ---: |",
        ]
        줄 += [f"| {기준:.2f} | {비율 * 100:.1f}% | {일치율 * 100:.1f}% |" for 기준, 비율, 일치율 in 곡선]
    else:
        줄.append("이 조건은 시나리오 확률을 내지 않는다.")

    견줌 = agreement_stats([t for run in runs for t in run])
    if 견줌:
        줄 += [
            "", "## LLM 과 Jev 의 요청 종류 견주기", "",
            "반복 실행을 모두 합쳐 계산했다. 직전 결과가 있는 질문은 견주지 않는다.",
            "",
            "| 항목 | 값 |",
            "| --- | ---: |",
            f"| 요청 종류가 같았던 비율 | {_숫자(견줌['같았던 비율'], True)} ({견줌['같았던 수']} / {견줌['견준 수']}) |",
            f"| 같았을 때 시나리오 일치율 | {_숫자(견줌['같았을 때 시나리오 일치율'], True)} |",
            f"| 달랐을 때 시나리오 일치율 | {_숫자(견줌['달랐을 때 시나리오 일치율'], True)} ({견줌['달랐던 수']}건) |",
            f"| 다시 해석해 두 답이 같아진 비율 | {_숫자(견줌['다시 해석해 같아진 비율'], True)} |",
            f"| 다시 해석해 맞게 정해진 비율 | {_숫자(견줌['다시 해석해 맞게 정해진 비율'], True)} |",
            f"| 사용자에게까지 물은 비율 | {_숫자(견줌['사용자에게 물은 비율'], True)} |",
        ]

    틀림 = wrong_cases(runs, thr)
    줄 += ["", f"## 틀린 문제 ({len(틀림)}건)", ""]
    if not 틀림:
        줄.append("없다.")
    for 사례 in 틀림:
        태그 = f" `{' '.join(사례['tags'])}`" if 사례["tags"] else ""
        줄.append(f"- **{사례['id']}**{태그} {사례['query']} ({len(runs)}번 중 {사례['횟수']}번)")
        for 키, 값 in 사례["틀린_항목"].items():
            실제 = ", ".join(sorted({repr(v) for v in 값["실제"]}))
            줄.append(f"  - `{키}` 기대 `{값['기대']!r}`, 실제 {실제}")

    줄 += ["", "## 원인과 다음 조치", "", "- (여기에 적는다)"]
    return "\n".join(줄)
