"""설정 파일이 필요한 모듈의 카테고리, 제품 종류 목록.

제품 등록 파서와 크롤러는 불러올 때 설정을 읽어 CI 의 v2 테스트에서는 볼 수 없다.
여기서 프롬프트 속 목록이 상수와 같은지, 종류가 목록인 상품을 키오스크 경로가 읽는지 본다.
"""
import types

import pytest

from prompts.product_types_text import PRODUCT_TYPE_RULE, category_label, category_lines
from rules.product_types import CATEGORY_TYPES


@pytest.mark.parametrize("모듈_이름", [
    "agents.input_agent.text_parser",
    "agents.input_agent.image_parser",
])
def test_제품_등록_파서는_상수로_만든_카테고리_목록을_쓴다(모듈_이름):
    import importlib

    프롬프트 = importlib.import_module(모듈_이름).PROMPT
    assert category_lines() in 프롬프트
    assert "__" not in 프롬프트
    assert "기타 스킨케어" not in 프롬프트


def test_크롤러는_모든_카테고리를_받고_상품_추출과_같은_스키마를_쓴다():
    from prompts.gemini_extraction import FEATURE_SCHEMAS
    from services.product_crawler import _CATEGORY_LABEL, _make_prompt

    assert _CATEGORY_LABEL == {카테고리: category_label(카테고리) for 카테고리 in CATEGORY_TYPES}
    프롬프트 = _make_prompt("eye", 3)
    assert FEATURE_SCHEMAS["eye"] in 프롬프트
    assert PRODUCT_TYPE_RULE in 프롬프트


def test_예전_검색은_새_카테고리도_받는다():
    from services.query_parser import _VALID_CATEGORIES

    assert _VALID_CATEGORIES == set(CATEGORY_TYPES)


def test_리뷰_수집은_모든_카테고리를_받는다():
    from services.review_collector import _CATEGORY_LABEL

    assert set(_CATEGORY_LABEL) == set(CATEGORY_TYPES)


@pytest.mark.parametrize("종류, 문장", [
    (["립세럼", "틴트"], "촉촉하게 마무리되는 립세럼"),
    ("틴트", "촉촉하게 마무리되는 틴트"),
    ([], "촉촉하게 마무리되는"),
])
def test_키오스크_한_줄_설명은_종류가_목록이면_첫_번째를_쓴다(종류, 문장):
    from services.iot.recommend_rules import product_blurb

    assert product_blurb({"product_type": 종류, "finish": "글로우"}).startswith(문장)


class _가짜_조회:
    def __init__(self, 행들):
        self.행들 = 행들

    def table(self, 이름):
        return self

    def select(self, *인자):
        return self

    def in_(self, *인자):
        return self

    def limit(self, 수):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self.행들)


def test_분류로_찾기는_종류가_목록이거나_동의어여도_맞는다(monkeypatch):
    import db.product_reader as 모듈

    def 행(pid, 종류):
        return {"product_id": pid, "name": pid, "brand": "B", "category": "skincare",
                "feature_json": {"product_type": 종류}}

    행들 = [행("다름", "세럼"), 행("목록", ["미스트", "토너"]), 행("동의어", "스킨"), 행("모름", None)]
    monkeypatch.setattr(모듈, "get_supabase", lambda: _가짜_조회(행들))

    찾은 = 모듈.search_products_by_traits(categories=["skincare"], product_types=["토너"])
    assert [상품["id"] for 상품 in 찾은] == ["목록", "동의어"]
