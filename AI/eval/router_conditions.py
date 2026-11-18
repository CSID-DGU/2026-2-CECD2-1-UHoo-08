"""시나리오 결정 실험의 조건.

조건 하나는 골든셋의 입력을 받아 Outcome 을 내놓는 함수다. 되물을지는 여기서
정하지 않고 재료(규칙에 걸렸는지, 확률)만 내놓는다. 기준값으로 자르는 일은
eval/router_metrics.py 가 한다.

직전 결과가 있는 질문은 어느 조건에서나 규칙으로 조건 수정에 보내고,
되묻지 않으며, 확률도 내지 않는다.
"""
from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Sequence

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


# ── B0. 규칙만 ──────────────────────────────────────────────────────────────

_금액 = re.compile(r"\d+\s*(만|천)\s*\d*\s*천?\s*원|\d{4,}\s*원")
_세트_말 = ("세트", "루틴", "묶", "조합", "구성", "맞춰", "맞추", "합쳐", "합해", "라인")
_평가_말 = ("어때", "어떤가", "어떨까", "괜찮", "맞아", "맞을까", "써도", "살 만", "대신", "비슷", "비교", "대체")
# 제품을 가리키기만 하는 말. 종류 이름 앞에 이것만 있으면 제품 이름으로 보지 않는다
_가리키는_말 = frozenset({"이", "그", "저", "이거", "그거", "저거", "요즘", "좋은", "괜찮은"})


def _종류_이름() -> tuple[str, ...]:
    from rules.product_types import CATEGORY_TYPES

    return tuple(sorted({종류 for 목록 in CATEGORY_TYPES.values() for 종류 in 목록}, key=len, reverse=True))


def _제품_이름이_있나(질문: str) -> bool:
    """종류 이름 앞에 브랜드나 제품 이름으로 볼 만한 말이 붙어 있는가.

    LLM 없이는 제품 이름을 알 수 없다. "라운드랩 독도 토너"처럼 종류 이름 앞에
    다른 말이 있으면 제품 이름으로, "토너"나 "그 토너"처럼 없으면 종류로 본다.
    """
    for 종류 in _종류_이름():
        자리 = 질문.find(종류)
        if 자리 < 0:
            continue
        앞말 = [낱말 for 낱말 in 질문[:자리].split() if 낱말 not in _가리키는_말]
        return bool(앞말)
    return False


def _종류가_여럿인가(질문: str) -> bool:
    """종류 이름이 둘 이상 나오는가. 긴 이름부터 지워 가며 세어 "선크림"을 "크림"으로 또 세지 않는다."""
    남은, 수 = 질문, 0
    for 종류 in _종류_이름():
        if 종류 in 남은:
            남은 = 남은.replace(종류, " ")
            수 += 1
    return 수 >= 2


def keyword_request_type(질문: str) -> str:
    """단어 규칙으로 요청 종류를 정한다. LLM 이 정말 필요한지를 보는 최저 기준이다.

    금액과 세트를 뜻하는 말이 함께 있으면 세트다. 종류를 둘 이상 늘어놓은 것도
    세트를 뜻하는 말로 본다. 제품 이름과 평가를 뜻하는 말이 함께 있으면 평가,
    나머지는 검색이다. 조건 수정은 직전 결과가 있는지로만 정하므로 여기서 고르지 않는다.
    """
    if _금액.search(질문) and (any(말 in 질문 for 말 in _세트_말) or _종류가_여럿인가(질문)):
        return "BUNDLE"
    if any(말 in 질문 for 말 in _평가_말) and _제품_이름이_있나(질문):
        return "EVALUATE"
    return "SEARCH"


async def _b0(입력: dict) -> Outcome:
    from graph.registry import ROUTE
    from contracts.query_spec import RequestType

    if 입력.get("parent_job_id"):
        return Outcome(spec={"request_type": "REFINE"}, scenario=ROUTE[RequestType.REFINE],
                       extracts_values=False)
    종류 = keyword_request_type(입력.get("raw_query") or "")
    return Outcome(spec={"request_type": 종류}, scenario=ROUTE[RequestType(종류)],
                   extracts_values=False)


# ── A2. LLM + 구조 규칙 ─────────────────────────────────────────────────────

def is_underspecified(spec: dict) -> bool:
    """찾을 단서가 하나도 없는가.

    카테고리, 특징, 조건, 예산, 기준 제품이 모두 비었으면 무엇을 추천할지 정할 수
    없다. LLM 이 매긴 숫자가 아니라 양식이 얼마나 비었는지로 본다.
    """
    예산 = spec.get("budget") or {}
    return not any((
        spec.get("category"),
        spec.get("features"),
        spec.get("conditions"),
        예산.get("max") is not None,
        예산.get("total") is not None,
        spec.get("base_product_ref"),
    ))


def structural_clarify(spec: Optional[dict], 빠진_필수: Sequence[str]) -> bool:
    """구조 규칙으로 되물을지 정한다.

    되묻는 경우는 셋이다. LLM 의 답을 양식으로 읽지 못했다, 요청 종류에 꼭 필요한
    값이 비었다, 찾을 단서가 하나도 없다.
    """
    if spec is None:
        return True
    return bool(빠진_필수) or is_underspecified(spec)


async def _구조_규칙으로_해석(입력: dict, temperature: float = 0.0) -> tuple[Optional[dict], str, bool]:
    """확신 점수를 묻지 않는 프롬프트로 한 번 해석한다. (spec, 시나리오, 되물을지)

    해석하지 못하면 spec 은 None 이고 검색으로 둔 채 되묻는다.
    """
    from contracts.query_spec import RequestType
    from graph.nodes.normalize import _사용자_말, parse_query
    from graph.registry import ROUTE
    from prompts.query_normalize import QUERY_NORMALIZE_SYSTEM_NO_CONFIDENCE

    raw = (입력.get("raw_query") or "").strip()
    읽은 = await parse_query(
        _사용자_말(입력, raw), raw,
        system=QUERY_NORMALIZE_SYSTEM_NO_CONFIDENCE, temperature=temperature,
    )
    if 입력.get("parent_job_id"):
        spec = 읽은.model_dump(mode="json") if 읽은 else {"request_type": "REFINE"}
        return spec, ROUTE[RequestType.REFINE], False
    if 읽은 is None:
        return None, ROUTE[RequestType.SEARCH], True

    spec = 읽은.model_dump(mode="json")
    # 직전 결과 없이 조건 수정으로 읽히면 수정할 대상이 없다. 라우터와 같이 새 검색으로 본다
    종류 = RequestType.SEARCH if 읽은.request_type is RequestType.REFINE else 읽은.request_type
    return spec, ROUTE[종류], structural_clarify(spec, 읽은.missing_required())


async def _a2(입력: dict) -> Outcome:
    """확신 점수를 없애고, 양식이 얼마나 비었는지를 보고 코드가 되물을지 정한다."""
    spec, 시나리오, 되물음 = await _구조_규칙으로_해석(입력)
    return Outcome(spec=spec or {}, scenario=시나리오, clarify_rule=되물음)


# ── A3. LLM + 구조 규칙 + 반복 질문 ─────────────────────────────────────────

# 같은 질문을 몇 번 묻는가
반복_횟수 = 5
# 반복할 때의 temperature. 0 이면 다섯 번이 거의 같은 답이라 일치 비율이 뜻이 없다
반복_temperature = 0.7


def majority_vote(시나리오들: Sequence[str]) -> tuple[str, float]:
    """가장 많이 나온 답과 그 답이 나온 비율. 같은 수면 먼저 나온 답을 고른다."""
    수 = Counter(시나리오들)
    최다 = max(수.values())
    답 = next(s for s in 시나리오들 if 수[s] == 최다)
    return 답, 최다 / len(시나리오들)


async def _a3(입력: dict) -> Outcome:
    """같은 질문을 동시에 여러 번 물어, 답이 일치한 비율을 시나리오 확률로 쓴다.

    조건이 부족한지는 구조 규칙으로 따로 본다. 요청 종류는 분명한데 조건이 하나도
    없는 질문은 매번 같은 답이 나와서, 일치 비율만으로는 걸러지지 않는다.
    """
    if 입력.get("parent_job_id"):
        # 직전 결과가 있으면 경로가 규칙으로 정해진다. 값만 뽑으면 되므로 한 번만 묻는다
        spec, 시나리오, _ = await _구조_규칙으로_해석(입력)
        return Outcome(spec=spec or {}, scenario=시나리오)

    답들 = await asyncio.gather(*(
        _구조_규칙으로_해석(입력, temperature=반복_temperature) for _ in range(반복_횟수)
    ))
    # 읽지 못한 답은 어느 시나리오에도 표를 주지 않도록 따로 센다
    표 = [시나리오 if spec is not None else "해석 실패" for spec, 시나리오, _ in 답들]
    답, 비율 = majority_vote(표)
    if 답 == "해석 실패":
        return Outcome(spec={}, scenario=답들[0][1], clarify_rule=True, scenario_prob=비율)

    # 값은 다수 답을 낸 첫 응답의 것을 쓴다
    spec, 시나리오, 되물음 = next(x for x in 답들 if x[0] is not None and x[1] == 답)
    return Outcome(spec=spec, scenario=시나리오, clarify_rule=되물음, scenario_prob=비율)


CONDITIONS: dict[str, Condition] = {
    "b0": Condition("b0", "B0. 규칙만", _b0),
    "a1": Condition("a1", "A1. LLM + 스스로 매긴 확신 점수", _a1, _a1_기준()),
    "a2": Condition("a2", "A2. LLM + 구조 규칙", _a2),
    # 다섯 번 중 세 번 이상 같은 답이면 처리한다. 연습용 문제에서 다시 정한다
    "a3": Condition("a3", "A3. LLM + 구조 규칙 + 반복 질문", _a3, Thresholds(scenario=0.6)),
}
