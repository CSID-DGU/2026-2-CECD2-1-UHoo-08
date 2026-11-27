"""Inventory 가 지켜야 할 성질. DB 없이 돈다.

DB 를 읽는 함수(_owned, _metas, _canonicalize)를 바꿔 끼운다. 실제 db.* 모듈은
한 번도 불러오지 않는다.
"""
import pytest

from graph.nodes import inventory as inv


def _터짐(*a, **k):
    raise AssertionError("DB 를 부르면 안 된다")


@pytest.fixture
def 보유(monkeypatch):
    """보유 행 3개. p3 은 상품 마스터에 없다."""
    행들 = [
        {"id": "up1", "product_id": "p1", "usage_type": "USING", "rating": 4,
         "opened_at": "2026-09-01", "remaining_pct": 60, "expiry_date": None, "pao_months": 12},
        {"id": "up2", "product_id": "p2", "usage_type": "USING", "rating": None,
         "opened_at": None, "remaining_pct": None, "expiry_date": "2027-01-01", "pao_months": None},
        {"id": "up3", "product_id": "p3", "usage_type": "USING"},
    ]
    메타 = {
        "p1": {"name": "레티놀 세럼", "brand": "A", "category": "skincare", "price": 30000,
               "feature_json": {"product_type": "세럼", "key_ingredient": ["Retinol", "판테놀"]}},
        "p2": {"name": "선크림", "brand": "B", "category": "sun", "price": 18000,
               "feature_json": {"product_type": "선크림"}},
    }
    기록 = {}

    async def metas(ids):
        기록["ids"] = list(ids)
        return {pid: 메타[pid] for pid in ids if pid in 메타}

    async def canonicalize(raw):
        기록["raw"] = raw
        별칭 = {"Retinol": "레티놀"}
        return {pid: [별칭.get(n, n) for n in names] for pid, names in raw.items()}

    monkeypatch.setattr(inv, "_owned", lambda user_id: 행들)
    monkeypatch.setattr(inv, "_metas", metas)
    monkeypatch.setattr(inv, "_canonicalize", canonicalize)
    return 기록


@pytest.mark.asyncio
async def test_user_id가_없으면_빈_목록이고_DB를_부르지_않는다(monkeypatch):
    monkeypatch.setattr(inv, "_owned", _터짐)
    assert await inv.inventory({}) == {"inventory": []}


@pytest.mark.asyncio
async def test_다른_사람_기준이면_요청한_사람의_보유_제품을_넣지_않는다(monkeypatch):
    monkeypatch.setattr(inv, "_owned", _터짐)
    상태 = {"user_id": "u1", "query_spec": {"target": "OTHER"}}
    assert await inv.inventory(상태) == {"inventory": []}


@pytest.mark.asyncio
async def test_보유_제품이_없으면_빈_목록이다(monkeypatch):
    monkeypatch.setattr(inv, "_owned", lambda user_id: [])
    monkeypatch.setattr(inv, "_metas", _터짐)
    assert await inv.inventory({"user_id": "u1"}) == {"inventory": []}


@pytest.mark.asyncio
async def test_상품_정보와_보유_정보와_표준_성분을_한_항목에_담는다(보유):
    나옴 = (await inv.inventory({"user_id": "u1"}))["inventory"]

    첫 = 나옴[0]
    assert 첫["user_product_id"] == "up1" and 첫["product_id"] == "p1"
    assert (첫["name"], 첫["category"], 첫["price"]) == ("레티놀 세럼", "skincare", 30000)
    assert 첫["feature_json"]["product_type"] == "세럼"
    assert (첫["rating"], 첫["opened_at"], 첫["remaining_pct"], 첫["pao_months"]) == (4, "2026-09-01", 60, 12)
    assert 첫["ingredients"] == ["레티놀", "판테놀"]
    # 성분이 없는 상품은 빈 목록
    assert 나옴[1]["ingredients"] == []


@pytest.mark.asyncio
async def test_상품_마스터에_없는_보유_행은_뺀다(보유):
    나옴 = (await inv.inventory({"user_id": "u1"}))["inventory"]
    assert [i["user_product_id"] for i in 나옴] == ["up1", "up2"]


@pytest.mark.asyncio
async def test_상품과_성분은_한_번에_읽는다(보유):
    await inv.inventory({"user_id": "u1"})
    assert 보유["ids"] == ["p1", "p2", "p3"]
    assert set(보유["raw"]) == {"p1", "p2"}
