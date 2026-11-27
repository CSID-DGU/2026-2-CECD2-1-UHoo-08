"""성분 읽기. DB 모듈을 가짜로 바꿔 끼워 키 없이 돈다."""
import sys
import types

import pytest

from services import ingredient_store as store


def test_성분_원문은_목록이_아니거나_비어도_안전하게_읽는다():
    assert store.raw_ingredients(None) == []
    assert store.raw_ingredients({"key_ingredient": None}) == []
    assert store.raw_ingredients({"key_ingredient": "레티놀"}) == ["레티놀"]
    assert store.raw_ingredients({"key_ingredient": ["판테놀", "", None]}) == ["판테놀"]


@pytest.fixture
def 가짜_DB(monkeypatch):
    기록 = {"alias": []}

    def get_product_features(ids):
        return {
            "p1": {"key_ingredient": ["Niacinamide", "판테놀"]},
            "p2": {"product_type": "토너"},
        }

    def get_alias_map(keys):
        기록["alias"].append(list(keys))
        return {"niacinamide": "나이아신아마이드"}

    monkeypatch.setitem(sys.modules, "db.product_reader",
                        types.SimpleNamespace(get_product_features=get_product_features))
    monkeypatch.setitem(sys.modules, "db.ingredient_alias_reader",
                        types.SimpleNamespace(get_alias_map=get_alias_map))
    return 기록


@pytest.mark.asyncio
async def test_상품_성분을_표준명으로_바꾸고_사전에_없는_것은_원문으로_둔다(가짜_DB):
    나옴 = await store.load_product_ingredients(["p1", "p2", "p9"])
    assert 나옴 == {"p1": ["나이아신아마이드", "판테놀"], "p2": []}
    # 별칭 사전은 한 번만 읽는다
    assert len(가짜_DB["alias"]) == 1


@pytest.mark.asyncio
async def test_상품이_없으면_DB를_부르지_않는다(monkeypatch):
    monkeypatch.setitem(sys.modules, "db.product_reader", None)
    assert await store.load_product_ingredients([]) == {}
