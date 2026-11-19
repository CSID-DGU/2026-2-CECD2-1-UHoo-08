"""검색 문장이 지켜야 할 성질.

질의와 상품 문장의 말투가 다르면 가까운 상품이 잡히지 않는다. 다른 사람 기준에서
요청한 사람의 과거 맥락을 붙이면 받을 사람에게 맞지 않는 상품이 잡힌다.
"""
import sys
import types

import pytest

from contracts.query_spec import QuerySpec, RequestType, Target
from services import search_text


def _스펙(**값) -> QuerySpec:
    return QuerySpec(request_type=RequestType.SEARCH, **값)


def test_원문과_특징_문장과_조건을_잇는다():
    문장 = search_text.build(
        _스펙(category="base", features={"finish": "매트"}, conditions=["여름 휴가용"]),
        "여름에 안 무너지는 쿠션", ["건조한 날씨"],
    )
    assert 문장.startswith("여름에 안 무너지는 쿠션 ")
    assert "매트" in 문장
    assert 문장.endswith("여름 휴가용 건조한 날씨")


def test_카테고리가_없으면_특징_문장은_생략한다():
    assert search_text.build(_스펙(features={"finish": "매트"}), "쿠션") == "쿠션"


def test_특징_문장을_못_만들면_생략한다(monkeypatch):
    def 터짐(category, features):
        raise KeyError("모르는 값")
    import services.feature_text_builder as 모듈
    monkeypatch.setattr(모듈, "build_product_text", 터짐)
    assert search_text.build(_스펙(category="base", features={"finish": "x"}), "쿠션") == "쿠션"


def test_빈_조각과_겹치는_조각은_뺀다():
    문장 = search_text.build(_스펙(conditions=["무향", " ", "무향"]), None, ["", "무향"])
    assert 문장 == "무향"


@pytest.fixture
def 임베딩(monkeypatch):
    """임베딩과 과거 맥락 검색을 가짜로 둔다."""
    def 세우기(맥락: list[str]):
        기록: dict = {"임베딩": [], "맥락": []}

        async def embed(text):
            기록["임베딩"].append(text)
            return [float(len(기록["임베딩"]))]

        def match_user_contexts(user_id, vec, category, count):
            기록["맥락"].append((user_id, vec, category, count))
            return [{"context_text": t, "similarity": 0.9} for t in 맥락]

        monkeypatch.setattr(search_text, "embed", embed)
        모듈 = types.SimpleNamespace(match_user_contexts=match_user_contexts)
        import db
        monkeypatch.setitem(sys.modules, "db.vector_search", 모듈)
        monkeypatch.setattr(db, "vector_search", 모듈, raising=False)
        return 기록

    return 세우기


@pytest.mark.asyncio
async def test_본인_기준이면_과거_맥락을_붙여_다시_임베딩한다(임베딩):
    기록 = 임베딩(["지난번 촉촉한 쿠션 조회", "건성 피부 크림 조회"])
    문장, 벡터 = await search_text.query_vector(_스펙(category="base"), "쿠션", user_id="u1")
    assert 문장 == "쿠션 지난번 촉촉한 쿠션 조회 건성 피부 크림 조회"
    assert 벡터 == [2.0]
    assert 기록["맥락"] == [("u1", [1.0], "base", 3)]


@pytest.mark.asyncio
async def test_찾은_맥락이_없으면_첫_벡터를_쓴다(임베딩):
    기록 = 임베딩([])
    문장, 벡터 = await search_text.query_vector(_스펙(), "쿠션", user_id="u1")
    assert (문장, 벡터) == ("쿠션", [1.0])
    assert len(기록["임베딩"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("기준", [Target.OTHER, Target.POPULAR])
async def test_본인_기준이_아니면_과거_맥락을_찾지_않는다(임베딩, 기준):
    기록 = 임베딩(["지난번 조회"])
    문장, _ = await search_text.query_vector(_스펙(target=기준), "쿠션", user_id="u1")
    assert 문장 == "쿠션"
    assert 기록["맥락"] == []


@pytest.mark.asyncio
async def test_검색할_말이_없으면_임베딩하지_않는다(임베딩):
    기록 = 임베딩(["지난번 조회"])
    assert await search_text.query_vector(_스펙(), "  ", user_id="u1") == ("", None)
    assert 기록["임베딩"] == []
