"""되물어야 하는 질의인지를 양식이 얼마나 비었는지로 정한다.

LLM 이 스스로 매긴 확신 점수는 쓰지 않는다. 그 숫자는 실제 정답률과 맞지 않았고,
왜 그 값인지 설명할 수도 없었다(eval/reports/experiments/a_router). 여기서는 누가 봐도
같은 답이 나오는 규칙만 쓴다.

되묻는 경우는 셋이다.
1. 요청 유형에 꼭 필요한 값이 비었다.
2. 상품 평가인데 기준 제품 자리의 말이 어떤 제품인지 알려 주지 않는다.
3. 찾을 단서가 하나도 없다.
"""
from __future__ import annotations

from contracts.query_spec import QuerySpec, RequestType
from rules.product_types import CATEGORY_TYPES, canonical

# 제품을 가리키기만 하고 이름은 알려 주지 않는 말
_이름_없는_말 = frozenset({
    "이", "그", "저", "이거", "그거", "저거", "이것", "그것", "저것", "요거", "고거",
    "이런", "그런", "방금", "아까", "저번", "제품", "상품", "거", "것",
})
_종류_이름 = frozenset(종류 for 목록 in CATEGORY_TYPES.values() for 종류 in 목록)
# 낱말 앞뒤에 붙는 문장부호
_문장부호 = "?!.,~…·\"'“”‘’()[]"
# 낱말 끝에 붙는 조사. 긴 것부터 본다
_조사 = tuple(sorted(
    ("은", "는", "이", "가", "을", "를", "도", "만", "요", "로", "으로", "의", "랑", "이랑",
     "은요", "는요", "이요", "이랑은", "하고"),
    key=len, reverse=True,
))


def _이름이_아닌_낱말(낱말: str) -> bool:
    """가리키는 말이나 종류 이름인가. 문장부호와 끝에 붙은 조사를 떼고도 본다.

    조사는 떼고 남은 말이 목록에 있을 때만 뗀다. 상품 이름의 끝 글자를 조사로 잘못
    떼어 이름을 지우지 않게 하려는 것이다.
    """
    글 = 낱말.strip(_문장부호)
    if not 글:
        return True
    후보들 = [글, *(글[: -len(조사)] for 조사 in _조사 if 글.endswith(조사) and len(글) > len(조사))]
    return any(
        후보 in _이름_없는_말 or 후보 in _종류_이름 or canonical(후보) is not None
        for 후보 in 후보들
    )


def names_a_product(기준_제품: str | None) -> bool:
    """기준 제품 자리의 말이 어떤 제품인지 알려 주는가.

    "이거", "그 선크림"처럼 가리키는 말과 종류 이름뿐이면 어떤 제품인지 알 수 없다.
    "그 선크림?", "그 쿠션은"처럼 문장부호나 조사가 붙어도 같다.
    LLM 은 이런 말도 기준 제품 자리에 그대로 옮겨 적으므로, 자리가 찼는지만 보면
    되물어야 할 질문을 놓친다.
    """
    return any(not _이름이_아닌_낱말(낱말) for 낱말 in (기준_제품 or "").split())


def is_underspecified(spec: QuerySpec) -> bool:
    """찾을 단서가 하나도 없는가.

    카테고리, 특징, 조건, 예산, 기준 제품이 모두 비었으면 무엇을 추천할지 정할 수 없다.
    """
    return not any((
        spec.category,
        spec.features,
        spec.conditions,
        spec.budget.max is not None,
        spec.budget.total is not None,
        spec.base_product_ref,
    ))


def missing_fields(spec: QuerySpec) -> tuple[str, ...]:
    """되물어야 할 필드. 비어 있는 필수 값에, 어떤 제품인지 알 수 없는 기준 제품을 더한다."""
    빠진 = list(spec.missing_required())
    if (
        spec.request_type is RequestType.EVALUATE
        and "base_product_ref" not in 빠진
        and not names_a_product(spec.base_product_ref)
    ):
        빠진.append("base_product_ref")
    return tuple(빠진)


def needs_clarification(spec: QuerySpec) -> bool:
    """되물어야 하는 질의인가."""
    return bool(missing_fields(spec)) or is_underspecified(spec)
