"""상품 목록 전체 조회가 1,000행 제한에 잘리지 않는지 본다.

가짜 DB도 실제처럼 한 번에 1,000행까지만 돌려준다. 첫 응답만 쓰면 뒤쪽 상품은 사진으로
찾을 수 없게 된다.
"""
import importlib
import sys
import types

import pytest

한번에_돌려주는_행 = 1000


class 가짜쿼리:
    def __init__(self, 요청들, 행들, 상한):
        self.요청 = {"select": None, "gt": [], "order": [], "limit": None}
        요청들.append(self.요청)
        self.행들 = 행들
        self.상한 = 상한

    def select(self, 열들):
        self.요청["select"] = 열들
        return self

    def gt(self, 열, 값):
        self.요청["gt"].append((열, 값))
        self.행들 = [행 for 행 in self.행들 if 행[열] > 값]
        return self

    def order(self, 열, **_):
        self.요청["order"].append(열)
        self.행들 = sorted(self.행들, key=lambda 행: 행[열])
        return self

    def limit(self, 수):
        self.요청["limit"] = 수
        return self

    def execute(self):
        return types.SimpleNamespace(data=self.행들[: min(self.요청["limit"], self.상한)])


@pytest.fixture
def 읽기(monkeypatch):
    """대역 DB를 물린 product_reader 와 요청 기록을 돌려준다. 끝나면 대역을 물린 모듈을 치운다."""
    import db

    모듈 = types.SimpleNamespace(get_supabase=None)
    monkeypatch.setitem(sys.modules, "db.supabase_client", 모듈)
    monkeypatch.setattr(db, "supabase_client", 모듈, raising=False)
    sys.modules.pop("db.product_reader", None)
    product_reader = importlib.import_module("db.product_reader")

    def 세우기(행들, 상한=한번에_돌려주는_행):
        요청들: list = []
        테이블들: list[str] = []

        def 테이블(이름):
            테이블들.append(이름)
            return 가짜쿼리(요청들, 행들, 상한)

        monkeypatch.setattr(product_reader, "get_supabase", lambda: types.SimpleNamespace(table=테이블))
        return product_reader, 요청들, 테이블들

    yield 세우기
    sys.modules.pop("db.product_reader", None)
    if hasattr(db, "product_reader"):
        del db.product_reader


def 상품(수):
    return [
        {"product_id": f"p{번호:05d}", "name": f"상품 {번호}", "brand": "BRAND", "category": "base",
         "image_url": None, "original_price": 10000 + 번호}
        for 번호 in range(수)
    ]


@pytest.mark.parametrize("수, 요청_수", [(0, 1), (325, 2), (1000, 2), (1001, 3), (2500, 4)])
def test_상품을_끝까지_읽는다(읽기, 수, 요청_수):
    product_reader, 요청들, 테이블들 = 읽기(상품(수))

    결과 = product_reader.list_products_meta()

    assert [행["id"] for 행 in 결과] == [f"p{번호:05d}" for 번호 in range(수)]
    assert len(요청들) == 요청_수
    assert set(테이블들) == {"products"}


def test_상품_메타의_모양으로_돌려준다(읽기):
    product_reader, _, _ = 읽기(상품(1))

    assert product_reader.list_products_meta() == [{
        "id": "p00000", "name": "상품 0", "brand": "BRAND", "category": "base",
        "image_url": None, "price": 10000,
    }]


def test_페이지마다_정렬하고_마지막_id_다음부터_요청한다(읽기):
    product_reader, 요청들, _ = 읽기(상품(1500))

    product_reader.list_products_meta()

    assert [요청["gt"] for 요청 in 요청들] == [
        [], [("product_id", "p00999")], [("product_id", "p01499")],
    ]
    assert all(요청["order"] == ["product_id"] and 요청["limit"] == 1000 for 요청 in 요청들)


def test_서버_상한이_낮아도_끝까지_읽는다(읽기):
    product_reader, 요청들, _ = 읽기(상품(700), 상한=300)

    assert len(product_reader.list_products_meta()) == 700
    assert len(요청들) == 4
