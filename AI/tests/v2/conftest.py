"""tests/v2 공통 대역.

보유 제품 단계(graph/nodes/inventory.py)는 실제 DB(user_products)를 읽는다. 경로를 끝까지
돌리는 시험이 사용자 id 를 넣으면 그 단계가 DB 를 부르므로, 기본은 "보유 제품 없음"으로
막는다. 보유 제품이 필요한 시험은 db.user_product_reader 를 다시 바꿔 끼운다.
"""
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _보유_제품_없음(monkeypatch):
    import db
    모듈 = types.SimpleNamespace(get_owned_user_products=lambda user_id: [])
    monkeypatch.setitem(sys.modules, "db.user_product_reader", 모듈)
    monkeypatch.setattr(db, "user_product_reader", 모듈, raising=False)
