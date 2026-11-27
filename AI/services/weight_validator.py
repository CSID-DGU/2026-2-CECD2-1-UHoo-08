"""
LLM 가중치 출력 검증·정규화.

Qwen-Plus가 반환한 4요소 가중치 dict가 다음 조건을 만족하는지 확인:
- 4개 키(budget_fit, price_value, review_score, personalization) 모두 존재
- 값이 0~1 사이 float
- 합이 0이 아님

검증 통과 시 합을 1.0으로 정규화해 반환. 실패 시 기본 가중치(균등 0.25) 반환.

점수 v2 는 가중치 대신 항목별 배수를 받는다. validate_multipliers 가 그 값을
검증한다. 잘못된 값은 배수 1.0, 곧 보정하지 않은 것으로 본다.
"""
from typing import Any, Dict, Iterable

DEFAULT_WEIGHTS: Dict[str, float] = {
    "budget_fit": 0.25,
    "price_value": 0.25,
    "review_score": 0.25,
    "personalization": 0.25,
}

REQUIRED_KEYS = set(DEFAULT_WEIGHTS.keys())


def validate_and_normalize(raw: Any) -> Dict[str, float]:
    """
    LLM 출력 검증·정규화.

    잘못된 출력이면 DEFAULT_WEIGHTS 반환 (점수 계산 중단되지 않도록).
    """
    if not isinstance(raw, dict):
        return dict(DEFAULT_WEIGHTS)

    # 키 누락 체크
    if not REQUIRED_KEYS.issubset(raw.keys()):
        return dict(DEFAULT_WEIGHTS)

    # 값 타입·범위 체크
    parsed: Dict[str, float] = {}
    for k in REQUIRED_KEYS:
        v = raw[k]
        if not isinstance(v, (int, float)):
            return dict(DEFAULT_WEIGHTS)
        if v < 0 or v > 1:
            return dict(DEFAULT_WEIGHTS)
        parsed[k] = float(v)

    total = sum(parsed.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)

    # 합 1.0으로 정규화
    return {k: v / total for k, v in parsed.items()}

# 점수 v2 가중치 보정 배수의 범위. 이 밖이면 보정하지 않는다.
배수_최소 = 0.5
배수_최대 = 2.0


def validate_multipliers(raw: Any, keys: Iterable[str]) -> Dict[str, float]:
    """LLM 이 준 항목별 배수를 검증한다. keys 마다 배수 하나를 돌려준다.

    JSON 객체가 아니거나, 값이 숫자가 아니거나, 범위를 벗어나면 그 항목은 1.0 이다.
    keys 에 없는 항목은 버린다. 한 항목이 이상해도 나머지 항목의 보정은 살린다.
    """
    원본 = raw if isinstance(raw, dict) else {}
    결과: Dict[str, float] = {}
    for 키 in keys:
        값 = 원본.get(키)
        if (
            isinstance(값, (int, float))
            and not isinstance(값, bool)
            and 배수_최소 <= 값 <= 배수_최대
        ):
            결과[키] = float(값)
        else:
            결과[키] = 1.0
    return 결과
