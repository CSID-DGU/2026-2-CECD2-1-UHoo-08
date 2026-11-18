"""프롬프트 속 카테고리와 제품 종류 목록이 상수와 같은지.

목록을 손으로 다시 적으면 상품을 넣는 경로마다 다른 종류 이름이 저장된다. 그래서 상품
추출, 예전 검색의 질의 해석이 상수로 만든 목록을 그대로 담는지 본다. 설정 파일이 필요한
제품 등록 파서와 크롤러는 tests/test_product_type_lists.py 에서 본다.
"""
import re

import pytest

from prompts.product_types_text import (
    PRODUCT_TYPE_RULE,
    category_label,
    category_lines,
    query_feature_lines,
    type_choices,
)
from rules.product_types import CATEGORY_NAMES, CATEGORY_TYPES, MAX_TYPES


def _종류_허용값(스키마: str) -> list[str]:
    줄 = next(줄 for 줄 in 스키마.splitlines() if '"product_type"' in 줄)
    return re.search(r'"product_type": "(.*)"', 줄).group(1).split(" | ")


def test_카테고리_판단_기준은_카테고리마다_한_줄이고_모든_종류가_있다():
    줄들 = category_lines().splitlines()
    assert len(줄들) == len(CATEGORY_TYPES)
    for 줄, (카테고리, 종류들) in zip(줄들, CATEGORY_TYPES.items()):
        assert 줄.startswith(f"- {카테고리}: ")
        assert set(종류들) <= set(줄.split(": ", 1)[1].split(", "))


def test_카테고리_이름표에_이름과_종류가_다_들어간다():
    for 카테고리, 종류들 in CATEGORY_TYPES.items():
        이름표 = category_label(카테고리)
        assert 이름표.startswith(CATEGORY_NAMES[카테고리])
        assert all(종류 in 이름표 for 종류 in 종류들)


def test_종류_규칙은_최대_개수와_배열_예시를_적는다():
    assert f"{MAX_TYPES}개까지 배열" in PRODUCT_TYPE_RULE
    assert '["립세럼", "틴트"]' in PRODUCT_TYPE_RULE


@pytest.mark.parametrize("카테고리", list(CATEGORY_TYPES))
def test_상품_추출_스키마의_종류_허용값은_상수_그대로다(카테고리):
    from prompts.gemini_extraction import FEATURE_SCHEMAS

    assert _종류_허용값(FEATURE_SCHEMAS[카테고리]) == list(CATEGORY_TYPES[카테고리])
    assert type_choices(카테고리) in FEATURE_SCHEMAS[카테고리]


def test_상품_추출_스키마는_모든_카테고리에_있고_열린_표현이_없다():
    from prompts.gemini_extraction import FEATURE_SCHEMAS

    assert set(FEATURE_SCHEMAS) == set(CATEGORY_TYPES)
    for 스키마 in FEATURE_SCHEMAS.values():
        assert all(not 값.endswith(" 등") for 값 in _종류_허용값(스키마))


def test_상품_추출_프롬프트에_종류_규칙과_그_카테고리_스키마가_들어간다():
    from prompts.gemini_extraction import FEATURE_SCHEMAS, build_prompt

    프롬프트 = build_prompt("상품", "브랜드", "cheek", "블러셔", "", "", "")
    assert PRODUCT_TYPE_RULE in 프롬프트
    assert FEATURE_SCHEMAS["cheek"] in 프롬프트


def test_상품_추출은_모르는_카테고리면_스킨케어_스키마를_쓴다():
    from prompts.gemini_extraction import FEATURE_SCHEMAS, build_prompt

    assert FEATURE_SCHEMAS["skincare"] in build_prompt("상품", "브랜드", "blush", "", "", "", "")


def test_새_카테고리의_특징은_질의_해석과_상품_추출이_같은_키를_쓴다():
    from prompts.gemini_extraction import FEATURE_SCHEMAS
    from prompts.product_types_text import QUERY_FEATURES

    for 카테고리 in ("eye", "cheek"):
        질의_키 = set(re.findall(r"(\w+)\(", QUERY_FEATURES[카테고리]))
        상품_키 = set(re.findall(r'"(\w+)":', FEATURE_SCHEMAS[카테고리])) - {"product_type"}
        assert 질의_키 == 상품_키, 카테고리


def test_예전_검색의_질의_해석도_같은_목록을_쓴다():
    from prompts.query_extraction import QUERY_EXTRACTION_SYSTEM

    assert "__" not in QUERY_EXTRACTION_SYSTEM
    assert category_lines() in QUERY_EXTRACTION_SYSTEM
    assert query_feature_lines() in QUERY_EXTRACTION_SYSTEM


def test_필요한_기능_조건의_카테고리_이름이_모든_카테고리에_있다():
    from graph.nodes.coverage import 카테고리_이름

    assert set(카테고리_이름) == set(CATEGORY_TYPES)
