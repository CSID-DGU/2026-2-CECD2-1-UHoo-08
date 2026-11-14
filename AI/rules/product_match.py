"""상품 정보와 조건을 비교하는 순수 계산.

예전 점수 에이전트(agents/score_agent)와 상품 특징 검색(services/feature_matcher)이
쓰던 계산을 여기로 모았다. 그 모듈들은 DB, LLM 모듈을 최상단에서 불러오기
때문에, 점수 항목이 그대로 가져다 쓰면 키 없이는 점수 항목을 불러오지도 못한다.
계산은 한 곳에만 두고 예전 모듈도 이 함수를 부른다.
"""
from __future__ import annotations

from typing import Any

# 순서가 있는 특징 값. 거리가 멀수록 덜 맞는다.
_순서형: dict[str, dict[str, int]] = {
    "coverage":      {"가벼운": 1, "중간": 2, "높음": 3},
    "lasting_power": {"낮음": 1, "중간": 2, "높음": 3},
    "texture":       {"가벼운": 1, "중간": 2, "진한": 3},
}
# 순서형 값이 한 칸 멀어질 때마다 깎는 비율
_순서_한_칸_감점 = 0.4

# 할인율 점수. 할인이 없으면 이 점수, 상한 할인율 이상이면 100
할인_없음_점수 = 50
할인_상한 = 0.5

# 사용자 프로필 값(BE) → 상품 feature_json 값
_피부_타입 = {
    "OILY": "지성",
    "DRY": "건성",
    "NORMAL": "중성",
    "COMBINATION": "복합",
    "OILY_DEHYDRATED": "복합",   # BE 가 보내는 값
    "DEHYDRATED_OILY": "복합",   # 예전 값. 이미 저장된 프로필을 위해 남긴다
    "SENSITIVE": "민감",
}
_피부_고민 = {
    # BE 가 보내는 값. 상품 feature_json 의 skin_concern 에 있는 말로 바꾼다
    "SENSITIVE": "진정",
    "DEHYDRATED": "보습",
    "WRINKLE": "주름",
    "BRIGHTENING": "미백",
    "PORE": "모공",
    # 예전 값. 이미 저장된 프로필을 위해 남긴다
    "SENSITIVITY": "민감",
    "ACNE": "트러블",
    "ATOPY": "진정",
    "WHITENING": "미백",
    "SEBUM": "모공",
    "DARK_CIRCLE": "다크서클",
}


def has_comparable_features(query_feat: dict[str, Any], product_feat: dict[str, Any]) -> bool:
    """조건 특징 중 상품에도 값이 있는 항목이 하나라도 있는지."""
    return any(
        qval is not None and product_feat.get(key) is not None
        for key, qval in query_feat.items()
    )


def feature_match_ratio(query_feat: dict[str, Any], product_feat: dict[str, Any]) -> float:
    """조건 특징과 상품 특징이 맞는 정도 0~1. 비교할 항목이 없으면 0."""
    total = matched = 0.0

    for key, qval in query_feat.items():
        if qval is None:
            continue
        pval = product_feat.get(key)
        if pval is None:
            continue
        total += 1

        if key in _순서형:
            q = _순서형[key].get(str(qval), 0)
            p = _순서형[key].get(str(pval), 0)
            if q and p:
                matched += max(0.0, 1.0 - abs(q - p) * _순서_한_칸_감점)
        elif isinstance(qval, list) and isinstance(pval, list):
            overlap = len(set(qval) & set(pval))
            matched += overlap / max(len(qval), 1)
        elif isinstance(qval, bool) or isinstance(pval, bool):
            matched += 1.0 if qval == pval else 0.0
        else:
            matched += 1.0 if str(qval) == str(pval) else 0.0

    return matched / total if total > 0 else 0.0


def discount_score(lowest_price: int | None, original_price: int | None) -> int | None:
    """할인율 점수. 할인 0% → 50, 50% 이상 → 100, 사이 선형. 가격이 없으면 None."""
    if lowest_price is None or original_price is None or original_price <= 0:
        return None
    if lowest_price >= original_price:
        return 할인_없음_점수
    비율 = 1 - lowest_price / original_price
    if 비율 >= 할인_상한:
        return 100
    return int(할인_없음_점수 + 비율 * (100 - 할인_없음_점수) / 할인_상한)


def _퍼스널_컬러(value: str | None) -> str | None:
    """SPRING_WARM, AUTUMN_MUTE → 웜톤, SUMMER_COOL, WINTER_COOL → 쿨톤, 그 밖 → 뉴트럴."""
    if not value:
        return None
    v = value.upper()
    if "WARM" in v or "AUTUMN" in v:
        return "웜톤"
    if "COOL" in v:
        return "쿨톤"
    return "뉴트럴"


def norm_skin_type(value: str | None) -> str | None:
    if not value:
        return None
    return _피부_타입.get(value.upper())


def norm_concerns(values: list[str]) -> list[str]:
    return [_피부_고민.get(v.upper(), v) for v in values]


def profile_checks(user_profile: dict[str, Any], feature_json: dict[str, Any] | None) -> list[bool]:
    """프로필과 상품 특징을 비교한 결과. 양쪽에 값이 있는 항목만 담는다.

    퍼스널 컬러는 같거나 상품이 뉴트럴이면 맞다. 피부 고민은 하나라도 겹치면 맞다.
    """
    if not feature_json:
        return []

    결과: list[bool] = []

    색 = _퍼스널_컬러(user_profile.get("personal_color"))
    상품_색 = feature_json.get("personal_color")
    if 색 and 상품_색:
        결과.append(색 == 상품_색 or 상품_색 == "뉴트럴")

    피부 = norm_skin_type(user_profile.get("skin_type"))
    상품_피부 = feature_json.get("skin_type")
    if 피부 and 상품_피부:
        결과.append(피부 == 상품_피부)

    고민 = set(norm_concerns(user_profile.get("skin_concerns") or []))
    상품_고민 = set(feature_json.get("skin_concern") or [])
    if 고민 and 상품_고민:
        결과.append(bool(고민 & 상품_고민))

    return 결과
