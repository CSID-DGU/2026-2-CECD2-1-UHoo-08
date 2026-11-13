"""트렌드 상품 고르기와 환경 기능 일치 판정이 지켜야 할 성질.

언급 몇 건으로 튄 지수에 배지를 달면 안 된다. 환경 배지는 상품이 그 기능을 실제로
채울 때만 달아야 한다.
"""
import sys
import types
from datetime import date

import pytest

from db import trend_reader
from rules.env_match import meets


def _행(pid, 지수, 언급, 날="2026-11-10"):
    return {"product_id": pid, "date": 날, "trend_score": 지수, "mention_count": 언급}


def test_며칠치_지수와_언급을_합쳐_고른다():
    행들 = [_행("p1", 1.0, 1), _행("p1", 2.0, 2, "2026-11-11"), _행("p2", 2.5, 5)]
    assert trend_reader.rank_trending(행들) == {"p1", "p2"}


def test_언급이_모자라면_지수가_높아도_뺀다():
    assert trend_reader.rank_trending([_행("p1", 9.0, 2), _행("p2", 1.0, 3)]) == {"p2"}


def test_상위_순위_밖은_뺀다():
    행들 = [_행(f"p{i:02d}", float(i), 10) for i in range(25)]
    고른 = trend_reader.rank_trending(행들, top_n=20)
    assert len(고른) == 20
    assert "p04" not in 고른 and "p24" in 고른


def test_지수가_비어_있으면_0으로_본다():
    assert trend_reader.rank_trending([_행("p1", None, 3), _행("p2", None, None)]) == {"p1"}


def test_테이블이_비어_있으면_빈_집합이다():
    assert trend_reader.rank_trending([]) == set()


@pytest.fixture
def 가짜_DB(monkeypatch):
    """페이지마다 정해 둔 행을 돌려준다. 받은 조건을 남긴다."""
    def 세우기(쪽들: list[list[dict]]):
        기록: dict = {"gte": [], "range": []}

        class 쿼리:
            def table(self, 이름):
                return self

            def select(self, *a):
                return self

            def gte(self, 칼럼, 값):
                기록["gte"].append((칼럼, 값))
                return self

            def order(self, *a, **k):
                return self

            def range(self, 시작, 끝):
                기록["range"].append((시작, 끝))
                self.시작 = 시작
                return self

            def execute(self):
                순번 = len(기록["range"]) - 1
                return types.SimpleNamespace(data=쪽들[순번] if 순번 < len(쪽들) else [])

        모듈 = types.SimpleNamespace(get_supabase=lambda: 쿼리())
        import db
        monkeypatch.setitem(sys.modules, "db.supabase_client", 모듈)
        monkeypatch.setattr(db, "supabase_client", 모듈, raising=False)
        return 기록

    return 세우기


def test_최근_7일을_나눠_읽어_고른다(가짜_DB, monkeypatch):
    monkeypatch.setattr(trend_reader, "_페이지_크기", 2)
    기록 = 가짜_DB([[_행("p1", 3.0, 2), _행("p2", 1.0, 1)], [_행("p1", 1.0, 2)]])
    고른 = trend_reader.get_trending_product_ids(today=date(2026, 11, 14))
    assert 고른 == {"p1"}
    # 오늘을 넣어 7일. 쪽마다 같은 조건으로 읽는다
    assert set(기록["gte"]) == {("date", "2026-11-08")}
    assert 기록["range"] == [(0, 1), (2, 3), (3, 4)]


# 환경 기능 일치

_자외선 = {"key": "UV_PROTECT", "category": "sun", "features": {"product_type": "선크림"}}


def test_카테고리와_특징이_모두_같으면_채운다():
    assert meets(_자외선, {"category": "sun", "feature_json": {"product_type": "선크림"}})


def test_카테고리가_다르거나_특징이_다르면_채우지_않는다():
    assert not meets(_자외선, {"category": "base", "feature_json": {"product_type": "선크림"}})
    assert not meets(_자외선, {"category": "sun", "feature_json": {"product_type": "선스틱"}})


def test_상품에_그_특징이_없으면_채우지_않는다():
    assert not meets(_자외선, {"category": "sun", "feature_json": {}})
    assert not meets(_자외선, {"category": "sun"})


def test_목록_조건은_모두_들어_있어야_한다():
    필요 = {"category": "skincare", "features": {"skin_concern": ["보습", "진정"]}}
    assert meets(필요, {"category": "skincare", "feature_json": {"skin_concern": ["진정", "보습", "미백"]}})
    assert not meets(필요, {"category": "skincare", "feature_json": {"skin_concern": ["보습"]}})


def test_참거짓_조건은_값이_같아야_한다():
    필요 = {"category": "sun", "features": {"white_cast": False}}
    assert meets(필요, {"category": "sun", "feature_json": {"white_cast": False}})
    assert not meets(필요, {"category": "sun", "feature_json": {"white_cast": True}})


def test_카테고리와_특징이_없는_기능은_모든_상품이_채운다():
    assert meets({"key": "X", "category": None, "features": {}}, {"category": "lip"})
