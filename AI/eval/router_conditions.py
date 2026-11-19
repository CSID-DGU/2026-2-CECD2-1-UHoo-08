"""시나리오 결정 실험의 조건.

조건 하나는 골든셋의 입력을 받아 Outcome 을 내놓는 함수다. 되물을지는 여기서
정하지 않고 재료(규칙에 걸렸는지, 확률)만 내놓는다. 기준값으로 자르는 일은
eval/router_metrics.py 가 한다.

직전 결과가 있는 질문은 어느 조건에서나 규칙으로 조건 수정에 보내고,
되묻지 않으며, 확률도 내지 않는다.

LLM 이 스스로 매긴 확신 점수로 되묻던 예전 방식(A1)은 채택되지 않아 뺐다.
그 결과는 eval/reports/experiments/a_router 의 a1 리포트에 남아 있다.
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
#
# 서비스가 쓰는 방식이다. 되물을지는 rules/clarify.py 의 규칙으로 정한다.

async def _구조_규칙으로_해석(
    입력: dict, temperature: float = 0.0, 덧붙일_말: str = "",
) -> tuple[Optional[dict], str, bool]:
    """서비스와 같은 프롬프트로 한 번 해석한다. (spec, 시나리오, 되물을지)

    해석하지 못하면 spec 은 None 이고 검색으로 둔 채 되묻는다.
    덧붙일_말은 사용자 말 뒤에 붙여 함께 보낸다.
    """
    from contracts.query_spec import RequestType
    from graph.nodes.normalize import _사용자_말, parse_query
    from graph.registry import ROUTE
    from rules.clarify import needs_clarification

    raw = (입력.get("raw_query") or "").strip()
    읽은 = await parse_query(
        _사용자_말(입력, raw) + 덧붙일_말, raw, temperature=temperature,
    )
    if 입력.get("parent_job_id"):
        spec = 읽은.model_dump(mode="json") if 읽은 else {"request_type": "REFINE"}
        return spec, ROUTE[RequestType.REFINE], False
    if 읽은 is None:
        return None, ROUTE[RequestType.SEARCH], True

    spec = 읽은.model_dump(mode="json")
    # 직전 결과 없이 조건 수정으로 읽히면 수정할 대상이 없다. 라우터와 같이 새 검색으로 본다
    종류 = RequestType.SEARCH if 읽은.request_type is RequestType.REFINE else 읽은.request_type
    return spec, ROUTE[종류], needs_clarification(읽은)


async def _a2(입력: dict) -> Outcome:
    """확신 점수 없이, 양식이 얼마나 비었는지를 보고 코드가 되물을지 정한다."""
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
        # 확률은 내보내는 시나리오에 표를 준 비율이다. 해석 실패가 받은 표는 넣지 않는다
        시나리오 = 답들[0][1]
        return Outcome(spec={}, scenario=시나리오, clarify_rule=True,
                       scenario_prob=표.count(시나리오) / len(표))

    # 값은 다수 답을 낸 첫 응답의 것을 쓴다
    spec, 시나리오, 되물음 = next(x for x in 답들 if x[0] is not None and x[1] == 답)
    return Outcome(spec=spec, scenario=시나리오, clarify_rule=되물음, scenario_prob=비율)


# ── Jev 를 쓰는 조건 ────────────────────────────────────────────────────────
#
# Jev 는 영어에서 가장 정확하다고 알려져 있어 질문과 보기 설명은 영어로 적는다.
# 사용자 질문은 한국어 그대로 넘긴다. 한국어 질문을 얼마나 잘 읽는지가 이 실험이
# 확인하려는 것이다. 아래 문장은 프롬프트와 같으므로 연습용 문제만 보고 고친다.

_요청_종류_질문 = "What kind of request is this Korean query to a cosmetics recommendation service?"
_요청_종류_보기 = {
    "SEARCH": (
        "Find products that match conditions such as product type, skin type, texture, or a price "
        "limit for a single product. Also when only a brand or a product type is named."
    ),
    "EVALUATE": (
        "Asks about one specific named product: whether it is good or suits the user, how two named "
        "products compare, or what could replace or resembles that named product."
    ),
    "BUNDLE": (
        "Wants several products for different steps put together within one total budget, "
        "such as a set or a routine. Also when several different product types are listed "
        "under one budget, or a set or routine is requested without stating a budget."
    ),
    "REFINE": "Changes or adds a condition to a recommendation result that was just shown.",
}
_막연함_질문 = (
    "Does the service have to ask a follow-up question before it can recommend anything? "
    "Yes when the query gives no product type, feature, condition, or budget at all; when it asks "
    "about a product referred to only by words like 'this' or 'that one'; or when it asks for a set "
    "or routine without a total budget."
)
_확인_질문 = (
    "A classifier assigned the request type in `predicted_request_type` to the Korean query in "
    "`query`. Is that request type correct? The request types are described in `request_types`."
)


def _jev_요청_종류(답: dict) -> tuple[str, float]:
    """Jev 가 고른 요청 종류와 그 확률."""
    종류 = 답["choice"]
    return 종류, float(답["probabilities"][종류])


def _시나리오(종류: str) -> str:
    """요청 종류가 가는 시나리오. 직전 결과 없이 조건 수정이면 라우터와 같이 새 검색으로 본다."""
    from contracts.query_spec import RequestType
    from graph.registry import ROUTE

    읽은 = RequestType(종류)
    return ROUTE[RequestType.SEARCH if 읽은 is RequestType.REFINE else 읽은]


async def _jev_판단(질문: str) -> tuple[str, float, float]:
    """요청 종류, 그 확률, 막연한 질문일 확률을 한 번의 호출로 받는다."""
    from services.llm.jev import ask, choice, noul

    답 = await ask(질문, {
        "request_type": choice(_요청_종류_질문, _요청_종류_보기),
        "vague": noul(_막연함_질문),
    })
    종류, 확률 = _jev_요청_종류(답["request_type"])
    return 종류, 확률, float(답["vague"]["noul"])


async def _둘_다_기다리기(*작업: Awaitable) -> list:
    """동시에 보낸 호출이 모두 끝난 뒤 결과를 돌려준다. 하나라도 실패했으면 그때 예외를 낸다.

    asyncio.gather 는 먼저 실패한 호출의 예외를 바로 내고 나머지를 기다리지 않는다. 그러면
    아직 도는 호출이 이 문제의 호출 수, 토큰, 시간 기록에서 빠지고 다음 문제와 겹친다.
    """
    결과들 = await asyncio.gather(*작업, return_exceptions=True)
    for 결과 in 결과들:
        if isinstance(결과, BaseException):
            raise 결과
    return 결과들


async def _a4(입력: dict) -> Outcome:
    """값 뽑기는 LLM, 요청 종류와 막연함 판단은 Jev. 두 호출을 동시에 보낸다."""
    if 입력.get("parent_job_id"):
        spec, 시나리오, _ = await _구조_규칙으로_해석(입력)
        return Outcome(spec=spec or {}, scenario=시나리오)

    (spec, _, _), (종류, 확률, 막연함) = await _둘_다_기다리기(
        _구조_규칙으로_해석(입력), _jev_판단(입력.get("raw_query") or ""),
    )
    return Outcome(
        # 값은 LLM 것을 쓰고 요청 종류만 Jev 것으로 바꾼다
        spec={**(spec or {}), "request_type": 종류},
        scenario=_시나리오(종류),
        # 값을 읽지 못했으면 추천할 재료가 없으므로 되묻는다
        clarify_rule=spec is None,
        scenario_prob=확률,
        vague_prob=막연함,
    )


# 요청 종류가 갈렸을 때 LLM 에 덧붙이는 말. 같은 질문을 그대로 다시 보내면 같은 답이
# 나오므로 두 후보를 함께 알려 준다.
_다시_해석_말 = (
    "\n\n[다시 해석] 이 질의의 요청 종류를 두고 판단이 갈렸다. 후보는 {하나} 와 {다른} 이다. "
    "위 규칙에 비추어 두 후보 중 어느 쪽이 맞는지 다시 판단하고, 고른 종류에 맞게 모든 값을 다시 채워라."
)


async def _a5(입력: dict) -> Outcome:
    """LLM 과 Jev 가 요청 종류를 따로 고른 뒤 견준다. 두 호출을 동시에 보낸다.

    같으면 확정한다. 다르면 LLM 에 두 후보를 알려 주고 한 번만 다시 해석하게 한다.
    그래도 다르면 사용자에게 어느 쪽인지 묻는다. 시나리오 확률은 내지 않는다.
    조건이 부족한지는 구조 규칙과 Jev 의 막연함 확률을 함께 본다.

    같은지는 요청 종류가 가는 시나리오로 견준다. 직전 결과 없는 조건 수정은 검색과
    같은 곳으로 가므로, 이 둘이 갈린 것은 다시 물을 일이 아니다.
    """
    if 입력.get("parent_job_id"):
        spec, 시나리오, _ = await _구조_규칙으로_해석(입력)
        return Outcome(spec=spec or {}, scenario=시나리오)

    (spec, 시나리오, 되물음), (jev_종류, _, 막연함) = await _둘_다_기다리기(
        _구조_규칙으로_해석(입력), _jev_판단(입력.get("raw_query") or ""),
    )
    jev_시나리오 = _시나리오(jev_종류)
    if spec is None:
        # 값을 읽지 못했으면 견줄 것이 없다. 경로만 Jev 것으로 두고 되묻는다
        return Outcome(spec={"request_type": jev_종류}, scenario=jev_시나리오,
                       clarify_rule=True, vague_prob=막연함)
    if 시나리오 == jev_시나리오:
        return Outcome(spec=spec, scenario=시나리오, clarify_rule=되물음,
                       vague_prob=막연함, agreement="same")

    다시 = await _구조_규칙으로_해석(입력, 덧붙일_말=_다시_해석_말.format(
        하나=spec["request_type"], 다른=jev_종류,
    ))
    if 다시[0] is not None:
        spec, 시나리오, 되물음 = 다시
    if 시나리오 == jev_시나리오:
        return Outcome(spec=spec, scenario=시나리오, clarify_rule=되물음,
                       vague_prob=막연함, agreement="resolved")
    return Outcome(spec=spec, scenario=시나리오, clarify_rule=True,
                   vague_prob=막연함, agreement="unresolved")


async def _a6(입력: dict) -> Outcome:
    """구조 규칙대로 해석한 다음, LLM 이 정한 요청 종류가 맞는지 Jev 에 예/아니오로 묻는다."""
    from services.llm.jev import ask, noul

    spec, 시나리오, 되물음 = await _구조_규칙으로_해석(입력)
    if 입력.get("parent_job_id") or spec is None:
        return Outcome(spec=spec or {}, scenario=시나리오, clarify_rule=되물음)

    답 = await ask(
        {
            "query": 입력.get("raw_query") or "",
            "predicted_request_type": spec["request_type"],
            "request_types": _요청_종류_보기,
        },
        {"correct": noul(_확인_질문)},
    )
    return Outcome(spec=spec, scenario=시나리오, clarify_rule=되물음,
                   scenario_prob=float(답["correct"]["noul"]))


async def _a7(입력: dict) -> Outcome:
    """Jev 에만 묻는다. 값 뽑기는 하지 못하므로 요청 종류와 되묻기 판단만 채점한다."""
    from contracts.query_spec import RequestType
    from graph.registry import ROUTE

    if 입력.get("parent_job_id"):
        return Outcome(spec={"request_type": "REFINE"}, scenario=ROUTE[RequestType.REFINE],
                       extracts_values=False)
    종류, 확률, 막연함 = await _jev_판단(입력.get("raw_query") or "")
    return Outcome(spec={"request_type": 종류}, scenario=_시나리오(종류),
                   scenario_prob=확률, vague_prob=막연함, extracts_values=False)


# 아래 기준값은 연습용 문제(v2 dev 240건)에서 정했다. 시나리오 확률 기준은 처리한 질문의
# 시나리오 일치율이 97% 이상이 되는 가장 낮은 값이고, 막연함 확률 기준은 되묻기
# 판단의 F1 이 가장 높은 값이다. 프롬프트나 문제가 바뀌면 --fit-target 으로 다시 정한다.

CONDITIONS: dict[str, Condition] = {
    "b0": Condition("b0", "B0. 규칙만", _b0),
    "a2": Condition("a2", "A2. LLM + 구조 규칙", _a2),
    # 다섯 번 중 세 번 이상 같은 답이면 처리한다
    "a3": Condition("a3", "A3. LLM + 구조 규칙 + 반복 질문", _a3, Thresholds(scenario=0.6)),
    "a4": Condition("a4", "A4. LLM 과 Jev 가 나눠 맡기", _a4, Thresholds(scenario=0.48, vague=0.63)),
    "a5": Condition("a5", "A5. LLM 과 Jev 의 이중 확인", _a5, Thresholds(vague=0.66)),
    "a6": Condition("a6", "A6. LLM 결과를 Jev 가 확인", _a6, Thresholds(scenario=0.11)),
    "a7": Condition("a7", "A7. Jev 만", _a7, Thresholds(scenario=0.5, vague=0.61)),
}
