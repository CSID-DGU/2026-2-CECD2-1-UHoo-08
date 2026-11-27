"""궁합 확인 API 의 실제 판정. 성분 · 보유 제품 읽기를 바꿔 끼워 DB 없이 돈다."""
import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.internal.v2 import router

app = FastAPI()
app.include_router(router, prefix="/internal")
client = TestClient(app)

P1, P2, P9 = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", "99999999-9999-9999-9999-999999999999"
_성분 = {P1: ["레티놀", "판테놀"], P2: ["히알루론산"]}
_규칙 = [
    {"ingredient_a": "글라이콜릭애씨드", "ingredient_b": "레티놀", "level": "AVOID", "advice": "같이 쓰면 자극"},
    {"ingredient_a": "레티놀", "ingredient_b": "비타민C", "level": "SEPARATE", "advice": "아침 비타민C, 저녁 레티놀"},
]
_보유 = [
    {"user_product_id": "u1", "product_id": "o1", "name": "AHA 토너", "ingredients": ["글라이콜릭애씨드"]},
    {"user_product_id": "u2", "product_id": "o2", "name": "비타C 세럼", "ingredients": ["비타민C"]},
    {"user_product_id": "u3", "product_id": "o3", "name": "수분크림", "ingredients": ["세라마이드"]},
]


@pytest.fixture(autouse=True)
def 가짜(monkeypatch):
    async def load_product_ingredients(ids):
        return {pid: _성분[pid] for pid in ids if pid in _성분}

    async def load_rules():
        return _규칙

    async def inventory(state):
        return {"inventory": _보유}

    monkeypatch.setitem(sys.modules, "services.ingredient_store", types.SimpleNamespace(
        load_product_ingredients=load_product_ingredients, load_rules=load_rules))
    import graph.nodes.inventory as 노드
    monkeypatch.setattr(노드, "inventory", inventory)


def test_보유_제품과_걸린_쌍을_센_것부터_주고_단계는_가장_센_것이다():
    응답 = client.post("/internal/compatibility/check", json={"userId": "me", "productId": P1}).json()
    assert 응답["level"] == "AVOID" and 응답["stub"] is False
    assert [(p["userProductId"], p["level"]) for p in 응답["pairs"]] == [("u1", "AVOID"), ("u2", "SEPARATE")]
    assert 응답["pairs"][0]["advice"] == "같이 쓰면 자극"
    assert 응답["pairs"][1]["schedule"] == "아침과 저녁으로 나눠 쓰세요"


def test_걸린_쌍이_없으면_OK다():
    응답 = client.post("/internal/compatibility/check", json={"userId": "me", "productId": P2}).json()
    assert 응답 == {"level": "OK", "pairs": [], "stub": False}


def test_없는_상품이거나_id_형식이_틀리면_404다():
    assert client.post("/internal/compatibility/check", json={"userId": "me", "productId": P9}).status_code == 404
    assert client.post("/internal/compatibility/check", json={"userId": "me", "productId": "p1"}).status_code == 404
