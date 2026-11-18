"""시나리오 결정 실험의 조건.

조건 하나는 골든셋의 입력을 받아 Outcome 을 내놓는 함수다. 되물을지는 여기서
정하지 않고 재료(규칙에 걸렸는지, 확률)만 내놓는다. 기준값으로 자르는 일은
eval/router_metrics.py 가 한다.

직전 결과가 있는 질문은 어느 조건에서나 규칙으로 조건 수정에 보내고,
되묻지 않으며, 확률도 내지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from eval.router_metrics import Outcome, Thresholds


@dataclass(frozen=True)
class Condition:
    key: str
    name: str
    run: Callable[[dict], Awaitable[Outcome]]
    # 기준값을 따로 주지 않았을 때 쓰는 값
    thresholds: Thresholds = Thresholds()


async def _a1(입력: dict) -> Outcome:
    """지금 방식. LLM 이 스스로 적은 확신 점수를 그대로 쓴다.

    확신 점수 하나에 "어느 시나리오인지 헷갈린다"와 "조건이 없다"가 섞여 있다.
    따로 낼 수 없으므로 이 숫자를 시나리오 확률 자리에 둔다.
    """
    from contracts.query_spec import QuerySpec
    from graph.nodes.normalize import normalize
    from graph.nodes.router import router

    상태: dict = dict(입력)
    상태.update(await normalize(상태))
    상태.update(await router(상태))
    spec = 상태["query_spec"]
    if 입력.get("parent_job_id"):
        return Outcome(spec=spec, scenario=상태["scenario"])

    읽은 = QuerySpec.model_validate(spec)
    return Outcome(
        spec=spec,
        scenario=상태["scenario"],
        clarify_rule=bool(읽은.missing_required()),
        scenario_prob=읽은.confidence,
    )


def _a1_기준() -> Thresholds:
    from contracts.query_spec import CONFIDENCE_THRESHOLD

    return Thresholds(scenario=CONFIDENCE_THRESHOLD)


CONDITIONS: dict[str, Condition] = {
    "a1": Condition("a1", "A1. LLM + 스스로 매긴 확신 점수", _a1, _a1_기준()),
}
