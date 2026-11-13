"""상품 이름 해석이 지켜야 할 성질.

못 찾은 것을 비슷한 상품으로 메우면 사용자가 묻지 않은 상품을 평가하게 된다.
"""
import re
import sys
import types

import pytest

from services import product_resolver

_ID = "11111111-1111-1111-1111-111111111111"


def _상품(pid, name, brand):
    return {"id": pid, "name": name, "brand": brand, "category": "base",
            "image_url": None, "price": 30000}


@pytest.fixture
def 상품들(monkeypatch):
    """상품 조회를 가짜로 둔다. 이름 검색에 불린 단어를 남긴다."""
    def 세우기(목록: list[dict]):
        불린: list[str] = []

        def get_product_meta(pid):
            return next((p for p in 목록 if p["id"] == pid), None)

        def search_products_by_name(keyword, limit=20):
            불린.append(keyword)
            # DB 의 ILIKE 처럼 % 는 아무 글자나 대신한다
            패턴 = re.compile(".*".join(map(re.escape, keyword.split("%"))), re.IGNORECASE)
            return [p for p in 목록
                    if 패턴.search(p["name"]) or 패턴.search(p["brand"])][:limit]

        모듈 = types.SimpleNamespace(
            get_product_meta=get_product_meta,
            search_products_by_name=search_products_by_name,
        )
        import db
        monkeypatch.setitem(sys.modules, "db.product_reader", 모듈)
        monkeypatch.setattr(db, "product_reader", 모듈, raising=False)
        return 불린

    return 세우기


@pytest.mark.asyncio
async def test_있는_상품_id는_그대로_돌려준다(상품들):
    상품들([_상품(_ID, "네오 쿠션 매트", "라네즈")])
    assert await product_resolver.resolve(_ID) == _ID


@pytest.mark.asyncio
async def test_없는_상품_id는_찾지_못한다(상품들):
    상품들([])
    assert await product_resolver.resolve(_ID) is None


@pytest.mark.asyncio
async def test_브랜드를_빼고_남은_단어가_이름에_모두_있으면_찾는다(상품들):
    상품들([
        _상품("p1", "워터뱅크 크림", "라네즈"),
        _상품("p2", "네오 쿠션 매트", "라네즈"),
    ])
    assert await product_resolver.resolve("라네즈 네오쿠션") == "p2"


@pytest.mark.asyncio
async def test_호수_표기는_비교에서_뺀다(상품들):
    상품들([_상품("p2", "네오 쿠션 매트", "라네즈")])
    assert await product_resolver.resolve("라네즈 네오쿠션 21호") == "p2"
    assert await product_resolver.resolve("네오쿠션 #13 N20") == "p2"


@pytest.mark.asyncio
async def test_여러_개가_맞으면_덧붙은_말이_가장_적은_상품을_고른다(상품들):
    상품들([
        _상품("p3", "네오 쿠션 글로우 리필", "라네즈"),
        _상품("p2", "네오 쿠션 매트", "라네즈"),
    ])
    assert await product_resolver.resolve("네오쿠션") == "p2"


@pytest.mark.asyncio
async def test_단어_하나라도_이름에_없으면_고르지_않는다(상품들):
    """비슷한 상품으로 추측하지 않는다."""
    상품들([_상품("p2", "네오 쿠션 매트", "라네즈")])
    assert await product_resolver.resolve("라네즈 네오쿠션 글로우") is None


@pytest.mark.asyncio
async def test_브랜드만_말하면_고르지_않는다(상품들):
    상품들([_상품("p2", "네오 쿠션 매트", "라네즈")])
    assert await product_resolver.resolve("라네즈") is None


@pytest.mark.asyncio
async def test_긴_단어부터_찾아본다(상품들):
    불린 = 상품들([_상품("p2", "네오쿠션 매트", "라네즈")])
    await product_resolver.resolve("라네즈 네오쿠션")
    assert 불린 == ["네오쿠션"]


@pytest.mark.asyncio
async def test_띄어쓰기가_달라도_검색으로_찾는다(상품들):
    """그대로 찾아 없을 때만 띄어쓰기를 무시하고 다시 찾는다."""
    불린 = 상품들([_상품("p2", "네오 쿠션 매트", "다른브랜드")])
    assert await product_resolver.resolve("네오쿠션") == "p2"
    assert 불린 == ["네오쿠션", "네%오%쿠%션"]


@pytest.mark.asyncio
@pytest.mark.parametrize("ref", [None, "", "   ", "21호"])
async def test_비교할_말이_없으면_찾지_않는다(상품들, ref):
    불린 = 상품들([_상품("p2", "네오 쿠션 매트", "라네즈")])
    assert await product_resolver.resolve(ref) is None
    assert 불린 == []
