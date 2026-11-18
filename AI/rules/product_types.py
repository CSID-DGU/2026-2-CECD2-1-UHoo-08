"""제품 종류(feature_json.product_type)의 표준 목록과 비교 규칙.

상품 추출, 질의 해석, 검색 필터, 점수, 평가가 모두 이 목록을 쓴다. 목록이 파일마다
따로 있으면 상품을 넣는 경로마다 다른 값이 들어가고, 질의의 종류와 상품의 종류가
글자가 달라 맞지 않는다.

    종류        카테고리마다 허용하는 표준 이름. 톤업크림처럼 두 카테고리에 다 있는 것도 있다
    동의어      다른 표기를 표준 이름으로 바꾼다. 예: 스킨은 토너, 선세럼은 선에센스
    묶음        질의 종류가 묶음 이름이면 묶음 안의 종류도 맞는다. 예: 크림으로 찾으면 젤크림도 맞다
                반대로는 맞지 않는다. 젤크림으로 찾을 때 그냥 크림은 맞지 않는다
    여러 종류   경계가 모호한 상품은 종류를 두 개까지 목록으로 가진다. 하나라도 맞으면 맞는다
                예: 틴티드 립세럼은 ["립세럼", "틴트"]

공백과 대소문자는 따지지 않는다. "선 크림"과 "선크림"은 같다.

DB, LLM 없이 받은 값만으로 판단한다.
"""
from __future__ import annotations

from typing import Any

# 카테고리마다 허용하는 표준 종류. 상품에는 이 이름으로 저장한다
CATEGORY_TYPES: dict[str, tuple[str, ...]] = {
    "base": (
        "쿠션", "파운데이션", "스킨틴트", "비비크림", "씨씨크림", "톤업크림",
        "메이크업베이스", "프라이머", "컨실러", "컬러코렉터", "파우더", "팩트",
        "메이크업픽서",
    ),
    "sun": (
        "선크림", "선로션", "선젤", "선밀크", "선에센스", "선스틱", "선쿠션",
        "선스프레이", "선파우더",
    ),
    "lip": (
        "틴트", "립스틱", "립글로스", "립밤", "립오일", "립세럼", "립라이너", "립펜슬",
        "립베이스", "립마스크", "립스크럽", "립플럼퍼",
    ),
    "skincare": (
        "토너", "패드", "미스트", "부스터", "에센스", "세럼", "앰플", "로션", "크림",
        "젤크림", "아이크림", "톤업크림", "밤", "오일", "시트마스크", "슬리핑팩",
        "워시오프팩", "스팟패치", "클렌징폼", "클렌징젤", "클렌징오일", "클렌징밤",
        "클렌징워터", "클렌징밀크", "립앤아이리무버", "필링", "스크럽",
    ),
    "eye": ("아이섀도", "아이라이너", "마스카라", "아이브로우", "아이프라이머"),
    "cheek": ("블러셔", "하이라이터", "쉐딩"),
}

# 카테고리마다 묶음 이름과 그 안의 종류. 묶음 이름이 종류이기도 하면(크림) 그 종류도 맞는다.
# 클렌저, 마스크팩은 질의에서만 쓰는 이름이라 상품에 저장하지 않는다
GROUPS: dict[str, dict[str, tuple[str, ...]]] = {
    "sun": {
        "선크림": ("선로션", "선젤", "선밀크", "선에센스"),
    },
    "skincare": {
        "크림": ("젤크림", "아이크림", "톤업크림", "밤"),
        "세럼": ("앰플",),
        "클렌저": (
            "클렌징폼", "클렌징젤", "클렌징오일", "클렌징밤", "클렌징워터", "클렌징밀크",
            "립앤아이리무버",
        ),
        "마스크팩": ("시트마스크", "슬리핑팩", "워시오프팩"),
    },
}

# 다른 표기 → 표준 이름
SYNONYMS: dict[str, str] = {
    "픽서": "메이크업픽서",
    "세팅스프레이": "메이크업픽서",
    "선세럼": "선에센스",
    "선미스트": "선스프레이",
    "선팩트": "선쿠션",
    "썬크림": "선크림",
    "선스크린": "선크림",
    "썬스크린": "선크림",
    "립에센스": "립세럼",
    "립프라이머": "립베이스",
    "립틴트": "틴트",
    "스킨": "토너",
    "토너패드": "패드",
    "에멀전": "로션",
    "에멀젼": "로션",
    "모이스처라이저": "로션",
    "겔크림": "젤크림",
    "수분크림": "크림",
    "퍼스트에센스": "부스터",
    "시트팩": "시트마스크",
    "수면팩": "슬리핑팩",
    "섀도": "아이섀도",
    "쉐도우": "아이섀도",
    "아이쉐도우": "아이섀도",
    "눈썹펜슬": "아이브로우",
    "브로우": "아이브로우",
    "블러쉬": "블러셔",
    "치크": "블러셔",
    "컨투어": "쉐딩",
}

# 상품 하나가 가질 수 있는 종류 수. 경계가 모호한 상품만 두 개를 쓴다
MAX_TYPES = 2


def _열쇠(값: str) -> str:
    return "".join(값.split()).casefold()


def _표준_사전() -> dict[str, str]:
    사전: dict[str, str] = {}
    for 종류들 in CATEGORY_TYPES.values():
        for 종류 in 종류들:
            사전[_열쇠(종류)] = 종류
    for 묶음들 in GROUPS.values():
        for 이름 in 묶음들:
            사전[_열쇠(이름)] = 이름
    for 다른_표기, 표준 in SYNONYMS.items():
        사전[_열쇠(다른_표기)] = 표준
    return 사전


_표준 = _표준_사전()


def allowed_types(category: str | None) -> tuple[str, ...]:
    """그 카테고리에서 상품에 저장할 수 있는 종류. 모르는 카테고리면 빈 튜플."""
    return CATEGORY_TYPES.get(category or "", ())


def _카테고리에_있다(종류: str, category: str | None) -> bool:
    if category is None:
        return True
    return 종류 in allowed_types(category) or 종류 in GROUPS.get(category, {})


def canonical(값: Any, category: str | None = None) -> str | None:
    """표준 종류 이름. 동의어는 표준 이름으로 바꾸고, 목록에 없으면 None 이다.

    category 를 주면 그 카테고리의 종류나 묶음 이름만 받는다. 질의는 묶음 이름(크림,
    클렌저)으로 찾을 수 있으므로 묶음 이름도 돌려준다.
    """
    if not isinstance(값, str) or not 값.strip():
        return None
    표준 = _표준.get(_열쇠(값))
    if 표준 is None or not _카테고리에_있다(표준, category):
        return None
    return 표준


def product_types(feature_json: dict[str, Any] | None, category: str | None = None) -> list[str]:
    """상품의 표준 종류 목록. 종류를 모르면 빈 목록이다.

    product_type 은 문자열 하나이거나, 경계가 모호한 상품이면 목록이다. 목록에 없는
    값은 버리고, 같은 종류는 한 번만 남기고, 앞에서부터 MAX_TYPES 개까지 쓴다.
    """
    값 = (feature_json or {}).get("product_type")
    값들 = 값 if isinstance(값, list) else [값]
    종류들: list[str] = []
    for 하나 in 값들:
        표준 = canonical(하나, category)
        if 표준 and 표준 not in 종류들:
            종류들.append(표준)
    return 종류들[:MAX_TYPES]


def _넓힌_종류(원하는: str, category: str | None) -> set[str]:
    if category is not None:
        묶음 = GROUPS.get(category, {}).get(원하는, ())
    else:
        묶음 = next((묶음들[원하는] for 묶음들 in GROUPS.values() if 원하는 in 묶음들), ())
    return {원하는, *묶음}


def matches(원하는: Any, 상품_종류: list[str], category: str | None = None) -> bool | None:
    """질의 종류에 상품이 맞는지. 상품의 종류를 모르면 None 이다.

    상품_종류 는 product_types 가 돌려준 목록이다. 질의 종류가 목록에 없는 값이면
    글자가 같은 상품만 맞는다.
    """
    if not 상품_종류:
        return None
    표준 = canonical(원하는, category)
    if 표준 is None:
        글자 = _열쇠(str(원하는))
        return any(_열쇠(종류) == 글자 for 종류 in 상품_종류)
    return bool(_넓힌_종류(표준, category) & set(상품_종류))
