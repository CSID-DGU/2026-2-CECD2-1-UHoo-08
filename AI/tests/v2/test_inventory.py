"""Inventory 가 지켜야 할 성질.

DB 모듈은 함수 안에서 가져오므로(README 규칙), 노드 자신의 private 함수
(`_fetch_*`)를 monkeypatch 한다. 그래야 supabase 가 없는 tests/v2 환경에서도
돈다 — 실제 db.* 모듈은 한 번도 import 되지 않는다.
"""
import pytest

from graph.nodes import inventory as inv


@pytest.mark.asyncio
async def test_user_id가_없으면_빈_목록이고_DB를_부르지_않는다(monkeypatch):
    def 터짐(*a, **k):
        raise AssertionError("user_id 가 없는데 DB를 불렀다")

    monkeypatch.setattr(inv, "_fetch_owned", 터짐)

    나옴 = await inv.inventory({})
    assert 나옴 == {"inventory": []}


@pytest.mark.asyncio
async def test_보유_제품이_없으면_빈_목록이다(monkeypatch):
    monkeypatch.setattr(inv, "_fetch_owned", lambda user_id: [])

    나옴 = await inv.inventory({"user_id": "u1"})
    assert 나옴 == {"inventory": []}


@pytest.mark.asyncio
async def test_메타와_성분을_합쳐_표준명으로_돌려준다(monkeypatch):
    monkeypatch.setattr(inv, "_fetch_owned", lambda user_id: [
        {"id": "up1", "product_id": "p1", "usage_type": "USING",
         "opened_at": "2026-09-01", "remaining_pct": 60,
         "expiry_date": None, "pao_months": 12},
    ])
    monkeypatch.setattr(inv, "_fetch_product_metas", lambda ids: {
        "p1": {"name": "레티놀 세럼", "brand": "A", "category": "skincare"},
    })
    monkeypatch.setattr(inv, "_fetch_product_features", lambda ids: {
        "p1": {"key_ingredient": ["니아신아마이드", "레티놀"]},
    })
    monkeypatch.setattr(inv, "_fetch_alias_map", lambda keys: {
        "니아신아마이드": "나이아신아마이드",
    })

    나옴 = await inv.inventory({"user_id": "u1"})
    항목 = 나옴["inventory"][0]
    assert 항목["user_product_id"] == "up1"
    assert 항목["name"] == "레티놀 세럼"
    assert 항목["ingredients"] == ["나이아신아마이드", "레티놀"]


@pytest.mark.asyncio
async def test_성분_조회는_상품당_한_번이_아니라_한_번에_합쳐_부른다(monkeypatch):
    """보유 제품이 많아질수록 이 노드가 느려지면 안 된다."""
    monkeypatch.setattr(inv, "_fetch_owned", lambda user_id: [
        {"id": "up1", "product_id": "p1", "usage_type": "USING"},
        {"id": "up2", "product_id": "p2", "usage_type": "ONBOARDING"},
    ])
    monkeypatch.setattr(inv, "_fetch_product_metas", lambda ids: {
        "p1": {"name": "A"}, "p2": {"name": "B"},
    })
    monkeypatch.setattr(inv, "_fetch_product_features", lambda ids: {
        "p1": {"key_ingredient": ["글리세린"]},
        "p2": {"key_ingredient": ["세라마이드"]},
    })

    호출_횟수 = {"n": 0}

    def alias_map(keys):
        호출_횟수["n"] += 1
        assert set(keys) == {"글리세린", "세라마이드"}
        return {}

    monkeypatch.setattr(inv, "_fetch_alias_map", alias_map)

    await inv.inventory({"user_id": "u1"})
    assert 호출_횟수["n"] == 1


@pytest.mark.asyncio
async def test_성분이_없는_제품도_빈_목록으로_들어간다(monkeypatch):
    monkeypatch.setattr(inv, "_fetch_owned", lambda user_id: [
        {"id": "up1", "product_id": "p1", "usage_type": "USING"},
    ])
    monkeypatch.setattr(inv, "_fetch_product_metas", lambda ids: {"p1": {"name": "A"}})
    monkeypatch.setattr(inv, "_fetch_product_features", lambda ids: {})
    monkeypatch.setattr(inv, "_fetch_alias_map", lambda keys: {})

    나옴 = await inv.inventory({"user_id": "u1"})
    assert 나옴["inventory"][0]["ingredients"] == []
