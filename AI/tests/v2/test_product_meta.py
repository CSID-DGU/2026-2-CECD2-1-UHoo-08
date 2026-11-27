"""노드끼리 함께 쓰는 상품 정보가 지켜야 할 성질.

이미 읽은 상품을 다시 읽으면 노드가 늘 때마다 조회가 늘어난다. 가격을 노드마다
다르게 고르면 화면의 가격과 점수에 쓴 가격이 달라진다.
"""
import importlib
import sys
import types

import pytest

from services import product_meta


@pytest.fixture
def 조회(monkeypatch):
    """get_products_full 을 가짜로 둔다. 불린 id 묶음을 남긴다."""
    def 세우기(상품들: dict):
        불린: list[list[str]] = []

        def get_products_full(ids):
            불린.append(list(ids))
            return {pid: 상품들[pid] for pid in ids if pid in 상품들}

        모듈 = types.SimpleNamespace(get_products_full=get_products_full)
        import db
        monkeypatch.setitem(sys.modules, "db.product_reader", 모듈)
        monkeypatch.setattr(db, "product_reader", 모듈, raising=False)
        return 불린

    return 세우기


def _행(**값):
    return {
        "name": "쿠션", "brand": "브랜드", "category": "base", "image_url": None,
        "original_price": 30000, "lowest_price": None, "feature_json": {},
        "average_score": 4.5, "review_count": 10, **값,
    }


@pytest.mark.asyncio
async def test_없는_상품만_읽어_합친다(조회):
    불린 = 조회({"p2": _행(name="토너")})
    있던 = {"p1": {"name": "쿠션", "price": 1000}}

    합친 = await product_meta.ensure(있던, ["p1", "p2"])

    assert 불린 == [["p2"]]
    assert 합친["p1"] == {"name": "쿠션", "price": 1000}
    assert 합친["p2"]["name"] == "토너"


@pytest.mark.asyncio
async def test_모두_있으면_읽지_않는다(조회):
    불린 = 조회({})
    합친 = await product_meta.ensure({"p1": {"name": "쿠션"}}, ["p1"])
    assert 불린 == []
    assert 합친 == {"p1": {"name": "쿠션"}}


@pytest.mark.asyncio
async def test_받은_dict는_바꾸지_않는다(조회):
    조회({"p2": _행()})
    있던 = {"p1": {"name": "쿠션"}}
    await product_meta.ensure(있던, ["p2"])
    assert 있던 == {"p1": {"name": "쿠션"}}


@pytest.mark.asyncio
async def test_가격은_최저가가_있으면_최저가다(조회):
    조회({"p1": _행(original_price=30000, lowest_price=21000)})
    합친 = await product_meta.ensure({}, ["p1"])
    assert 합친["p1"]["price"] == 21000
    assert 합친["p1"]["original_price"] == 30000


@pytest.mark.asyncio
async def test_최저가가_없으면_정가다(조회):
    조회({"p1": _행(original_price=30000, lowest_price=None)})
    합친 = await product_meta.ensure({}, ["p1"])
    assert 합친["p1"]["price"] == 30000


@pytest.mark.asyncio
async def test_최저가가_0원이어도_최저가를_쓴다(조회):
    """0 을 거짓으로 보면 무료 증정 상품이 정가로 보인다."""
    조회({"p1": _행(original_price=30000, lowest_price=0)})
    합친 = await product_meta.ensure({}, ["p1"])
    assert 합친["p1"]["price"] == 0


@pytest.mark.asyncio
async def test_많으면_나눠_읽고_같은_id는_한_번만_읽는다(조회):
    ids = [f"p{i}" for i in range(250)]
    불린 = 조회({pid: _행() for pid in ids})

    합친 = await product_meta.ensure({}, ids + ["p0", "p1"])

    assert [len(묶음) for 묶음 in 불린] == [100, 100, 50]
    assert len(합친) == 250


@pytest.mark.asyncio
async def test_DB에_없는_상품은_담지_않는다(조회):
    조회({})
    합친 = await product_meta.ensure({}, ["없는것"])
    assert 합친 == {}


class 가짜테이블:
    def __init__(self, 기록, 행들):
        self.기록 = 기록
        self.행들 = 행들

    def select(self, 칼럼):
        self.기록["select"] = 칼럼
        return self

    def in_(self, 칼럼, 값):
        self.기록["in"] = (칼럼, list(값))
        return self

    def execute(self):
        return types.SimpleNamespace(data=self.행들)


@pytest.fixture
def 상품_조회(monkeypatch):
    """product_reader 는 최상단에서 DB 클라이언트를 가져온다. 가짜를 먼저 넣고 새로 불러온다."""
    def 세우기(행들):
        import db

        기록: dict = {}
        가짜 = types.SimpleNamespace(
            get_supabase=lambda: types.SimpleNamespace(table=lambda 이름: 가짜테이블(기록, 행들))
        )
        monkeypatch.setitem(sys.modules, "db.supabase_client", 가짜)
        monkeypatch.setattr(db, "supabase_client", 가짜, raising=False)
        monkeypatch.delitem(sys.modules, "db.product_reader", raising=False)
        monkeypatch.setattr(db, "product_reader", None, raising=False)
        return importlib.import_module("db.product_reader").get_products_full, 기록

    return 세우기


def test_상품_정보를_한_번에_읽고_feature_json을_파싱한다(상품_조회):
    get_products_full, 기록 = 상품_조회([
        {"product_id": "p1", "name": "쿠션", "brand": "B", "category": "base",
         "image_url": "u", "original_price": 30000, "lowest_price": 21000,
         "feature_json": '{"product_type": "쿠션"}', "average_score": 4.5, "review_count": 3},
        {"product_id": "p2", "name": "토너", "brand": "B", "category": "skincare",
         "feature_json": "깨진 값"},
    ])

    읽은 = get_products_full(["p1", "p2"])

    assert 기록["in"] == ("product_id", ["p1", "p2"])
    assert 읽은["p1"]["feature_json"] == {"product_type": "쿠션"}
    assert 읽은["p1"]["lowest_price"] == 21000
    assert 읽은["p1"]["review_count"] == 3
    assert 읽은["p2"]["feature_json"] == {}
    assert 읽은["p2"]["average_score"] is None


def test_빈_목록이면_조회하지_않는다(상품_조회):
    get_products_full, 기록 = 상품_조회([])
    assert get_products_full([]) == {}
    assert 기록 == {}
