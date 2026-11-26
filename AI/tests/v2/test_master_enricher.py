"""마스터 확충 에이전트 — 글로우픽 페이지는 가짜로 바꿔 끼운다. 네트워크 · DB 를 쓰지 않는다."""
import pytest

from services.master_enricher import Glowpick, MasterEnricher, brand_items, brand_title, product_info

BRAND_PAGE = (
    '<title>베라모어 VERAMORE 추천 제품 TOP20</title>'
    '"name":"1위 베라모어 | 포어타이트닝 스피큘 300앰플","image":"x","url":"https://www.glowpick.com/products/111",'
    '"idProduct":222,"idBrand":12879,"productTitle":"블러링 쿠션  [SPF50+/PA++++]","volume":"13g","price":40000,'
)
PRODUCT_PAGE = 'href="/brands/12879" "idProduct":111,"idBrand":12879,"productTitle":"포어타이트닝 스피큘 300앰플","volume":"50ml","price":35000'


def fake_gp(tmp_path, pages):
    calls = []

    def fetch(path):
        calls.append(path)
        return pages.get(path.split("?")[0], "")
    return Glowpick(tmp_path, fetch, delay=0), calls


def test_리뷰가_없는_신상품도_브랜드_페이지에서_읽는다():
    items = {it["id"]: it for it in brand_items(BRAND_PAGE)}
    assert items[111]["name"] == "포어타이트닝 스피큘 300앰플"
    assert items[222]["price"] == 40000          # 평점 목록에는 없고 상품 JSON 에만 있다
    assert brand_title(BRAND_PAGE) == ("베라모어", "VERAMORE")
    assert product_info(PRODUCT_PAGE)["brand_id"] == 12879


def test_검색_경로는_robots_가_막아_부르지_않는다(tmp_path):
    gp, _ = fake_gp(tmp_path, {})
    with pytest.raises(ValueError):
        gp.get("/searches?query=x")


def test_같은_페이지는_한_번만_받는다(tmp_path):
    gp, calls = fake_gp(tmp_path, {"/brands/1": "a"})
    gp.get("/brands/1"); gp.get("/brands/1")
    assert calls == ["/brands/1"]


@pytest.mark.asyncio
async def test_카탈로그에서_브랜드_번호를_찾고_이름이_같은_제품을_후보로_낸다(tmp_path):
    gp, _ = fake_gp(tmp_path, {"/products/111": PRODUCT_PAGE, "/brands/12879": BRAND_PAGE})
    en = MasterEnricher(gp, {}, [{"id": 111, "brand": "베라모어", "name": "포어타이트닝 스피큘 300앰플"}])
    m = {"brand": "베라모어", "product_name": "블러링 쿠션", "category": "base", "mention_type": "product", "evidence": "베라모어 블러링 쿠션"}
    res = await en.resolve(m, None)
    assert res["status"] == "found" and res["candidate"]["glow_id"] == 222
    assert res["candidate"]["name"] == "베라모어 블러링 쿠션  [SPF50+/PA++++]" and res["candidate"]["db_brand"] == "VERAMORE"


@pytest.mark.asyncio
async def test_부분_이름은_판정_LLM_없이는_후보로_내지_않는다(tmp_path):
    gp, _ = fake_gp(tmp_path, {"/brands/12879": BRAND_PAGE})
    en = MasterEnricher(gp, {"VERAMORE": 12879}, [])
    m = {"brand": "베라모어", "product_name": "300 앰플", "category": "skincare", "mention_type": "product", "evidence": "300 앰플"}
    res = await en.resolve(m, "VERAMORE")
    assert res["status"] == "no_product"


@pytest.mark.asyncio
async def test_브랜드를_모르면_찾지_않는다(tmp_path):
    gp, calls = fake_gp(tmp_path, {})
    en = MasterEnricher(gp, {}, [])
    m = {"brand": "없는브랜드", "product_name": "어떤 세럼", "category": "skincare", "mention_type": "product", "evidence": "x"}
    assert (await en.resolve(m, None))["status"] == "no_brand" and calls == []
