"""프롬프트에 넣는 카테고리와 제품 종류 목록 문장.

목록은 rules/product_types.py 의 상수로 만든다. 상품 추출, 크롤러, 제품 등록, 질의 해석이
목록을 각자 손으로 적어 두면, 상품을 넣는 경로마다 다른 종류 이름이 저장되고 질의의
종류와 글자가 맞지 않는다.
"""
from __future__ import annotations

from rules.product_types import CATEGORY_NAMES, CATEGORY_TYPES, GROUPS, MAX_TYPES

# 질의 해석에서 카테고리마다 product_type 외의 특징 키와 값
QUERY_FEATURES: dict[str, str] = {
    "base": "coverage(가벼운|중간|높음), finish(매트|세미매트|글로우|촉촉), skin_type(건성|지성|복합|민감), skin_concern(배열:[모공,잡티,칙칙함,트러블]), personal_color(웜톤|쿨톤|뉴트럴), lasting_power(낮음|중간|높음)",
    "sun": "finish(매트|세미매트|촉촉), skin_type(건성|지성|복합|민감), skin_concern(배열:[진정,보습,미백]), lasting_power(낮음|중간|높음), white_cast(true|false)",
    "lip": "finish(매트|세미매트|글로우|촉촉), personal_color(웜톤|쿨톤|뉴트럴), lasting_power(낮음|중간|높음), moisturizing(true|false), skin_concern(배열:[보습,각질])",
    "skincare": "texture(가벼운|중간|진한), skin_type(건성|지성|복합|민감), skin_concern(배열:[보습,미백,주름,진정,모공]), key_ingredient(배열), fragrance_free(true|false)",
    "eye": "finish(매트|쉬머|글리터), lasting_power(낮음|중간|높음), waterproof(true|false)",
    "cheek": "finish(매트|글로우|쉬머), personal_color(웜톤|쿨톤|뉴트럴), lasting_power(낮음|중간|높음)",
}

# 질의 해석의 카테고리 판단에 보여 줄 대표 종류. 전체 종류는 특징 표에 있다.
# 카테고리 판단에 모든 종류를 늘어놓았더니, 종류 이름 없이 피부 타입만 말하는 세트
# ("13만원으로 건성 피부 세트")에서 카테고리와 세트 단계를 비우는 일이 늘었다
CATEGORY_EXAMPLES: dict[str, tuple[str, ...]] = {
    "base": ("쿠션", "파운데이션", "비비크림", "프라이머", "컨실러"),
    "sun": ("선크림", "선스틱", "선쿠션", "선스프레이"),
    "lip": ("틴트", "립스틱", "립글로스", "립밤"),
    "skincare": ("토너", "에센스", "세럼", "크림", "오일", "로션", "클렌저", "마스크팩"),
    "eye": ("아이섀도", "아이라이너", "마스카라", "아이브로우"),
    "cheek": ("블러셔", "하이라이터", "쉐딩"),
}

# 종류 이름 말고도 카테고리를 알려 주는 말
CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "sun": ("자외선차단",),
}

# 상품의 종류를 적는 규칙. 상품 추출과 크롤러가 같이 쓴다
PRODUCT_TYPE_RULE = (
    "- product_type 은 허용값 중 하나를 글자 그대로 쓴다. 맞는 종류가 없으면 null\n"
    f'- 두 종류의 경계에 걸친 상품만 ["립세럼", "틴트"] 처럼 {MAX_TYPES}개까지 배열로 쓴다. '
    "대부분의 상품은 하나다"
)


def type_choices(category: str) -> str:
    """상품에 저장할 종류의 허용값. 예: "쿠션 | 파운데이션 | 스킨틴트 | ..." """
    return " | ".join(CATEGORY_TYPES[category])


def category_label(category: str) -> str:
    """카테고리 이름과 종류. 예: "선케어 (선크림, 선로션, ...)" """
    return f"{CATEGORY_NAMES[category]} ({', '.join(CATEGORY_TYPES[category])})"


def category_lines() -> str:
    """카테고리 판단 기준. 한 줄에 카테고리 하나와 그 종류, 카테고리를 알려 주는 말."""
    return "\n".join(
        f"- {카테고리}: {', '.join([*종류들, *CATEGORY_HINTS.get(카테고리, ())])}"
        for 카테고리, 종류들 in CATEGORY_TYPES.items()
    )


def query_category_lines() -> str:
    """질의 해석의 카테고리 판단 기준. 카테고리마다 대표 종류와 카테고리를 알려 주는 말."""
    return "\n".join(
        f"- {카테고리}: {', '.join([*CATEGORY_EXAMPLES[카테고리], *CATEGORY_HINTS.get(카테고리, ())])}"
        for 카테고리 in CATEGORY_TYPES
    )


def query_type_values(category: str) -> list[str]:
    """질의의 product_type 에 쓸 수 있는 값. 묶음 이름(크림, 클렌저)도 넣는다."""
    값들 = list(CATEGORY_TYPES[category])
    값들 += [이름 for 이름 in GROUPS.get(category, {}) if 이름 not in 값들]
    return 값들


def query_feature_lines() -> str:
    """질의 해석의 카테고리별 특징 키와 값. 한 줄에 카테고리 하나."""
    return "\n".join(
        f"{카테고리}: product_type({'|'.join(query_type_values(카테고리))}), {QUERY_FEATURES[카테고리]}"
        for 카테고리 in CATEGORY_TYPES
    )


def group_text() -> str:
    """묶음 이름과 그 안의 종류. 예: "크림(젤크림, 아이크림, 톤업크림, 밤), ..." """
    return ", ".join(
        f"{이름}({', '.join(안)})"
        for 묶음들 in GROUPS.values() for 이름, 안 in 묶음들.items()
    )
