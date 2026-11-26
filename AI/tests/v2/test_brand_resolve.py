"""브랜드 보정 · 쇼핑 검색어 (rules/brand_resolve) · v2 추출 응답 검사 (services/product_extractor_v2)."""
import pytest

from rules.brand_resolve import BrandDictionary, resolve
from services.product_extractor_v2 import extract_products, mentions_for_post, parse_products

D = BrandDictionary([
    {"ko": "투쿨포스쿨", "en": "too cool for school", "aliases": ["투쿨포스쿨", "too cool for school", "toocoolforschool"]},
    {"ko": "에스네이처", "en": "S.NATURE", "db_brand": "ES NATURE", "aliases": ["에스네이처", "ES NATURE"]},
    {"ko": "헤라", "en": "HERA", "db_brand": "HERA", "aliases": ["헤라", "HERA"]},
    {"ko": "맥", "en": "MAC", "db_brand": "MAC", "aliases": ["맥", "MAC"]},
    {"ko": "롬앤", "en": "rom&nd", "db_brand": "ROM&ND", "aliases": ["롬앤", "rom&nd", "romand"]},
])


def test_영문_계정명으로_적힌_브랜드도_한글_대표명으로_검색한다():
    r = resolve({"brand": "toocoolforschool_official", "product_name": "무드 스위치 팔레트"}, "", D)
    assert (r.query, r.brand_from) == ("투쿨포스쿨 무드 스위치 팔레트", "llm")


def test_띄어_쓴_영문_브랜드도_잇는다():
    assert resolve({"brand": "Too Cool For School", "product_name": "팔레트 X"}, "", D).brand.ko == "투쿨포스쿨"


def test_브랜드가_비면_캡션의_유일한_사전_브랜드로_채운다():
    r = resolve({"brand": None, "product_name": "장벽천재세럼"}, "에스네이처 신상!\n#장벽천재세럼", D)
    assert (r.query, r.brand_from) == ("에스네이처 장벽천재세럼", "caption")


def test_캡션에_브랜드가_여럿이면_제품명과_가까운_브랜드로_채운다():
    cap = "헤라 센슈얼 샤인 틴트 너무 좋고\n롬앤 쥬시래스팅틴트도 샀어요"
    assert resolve({"brand": None, "product_name": "쥬시래스팅틴트"}, cap, D).brand.ko == "롬앤"


def test_LLM_이_낸_브랜드가_사전에_없으면_캡션의_다른_브랜드로_덮지_않는다():
    cap = "⑫ 리브러쉬 - 무알콜 과즙 구강 스프레이\n⑬ 헤라 - 블랙 쿠션"
    r = resolve({"brand": "리브러쉬", "product_name": "무알콜 과즙 구강 스프레이"}, cap, D)
    assert (r.query_kind, r.brand_from) == ("name_only", "llm_raw")


def test_판매처는_브랜드로_쓰지_않는다():
    d = BrandDictionary([{"ko": "올리브영", "en": "OLIVE YOUNG", "aliases": ["올리브영"]}])
    r = resolve({"brand": None, "product_name": "립 시럽"}, "10월 1일 올리브영 선런칭", d)
    assert r.query_kind == "name_only"


def test_콜라보_표기와_계정명_꼬리_여러_개를_처리한다():
    d = BrandDictionary([{"ko": "라네즈", "en": "LANEIGE", "aliases": ["라네즈"]}, {"ko": "루나", "en": "LUNA", "aliases": ["루나", "luna"]}])
    assert d.exact("라네즈 X 마뗑킴").ko == "라네즈"
    assert d.exact("luna_makeup_official").ko == "루나"


def test_사전에_없는_브랜드는_그대로_두고_제품명만으로_검색한다():
    r = resolve({"brand": "아로셀", "product_name": "슈퍼콜라겐 마스크"}, "④ 아로셀 - 슈퍼콜라겐 마스크", D)
    assert (r.query, r.query_kind, r.brand_from) == ("슈퍼콜라겐 마스크", "name_only", "llm_raw")


def test_제품명이_없으면_매칭에서_뺀다():
    r = resolve({"brand": "헤라", "product_name": None}, "헤라 최고", D)
    assert r.query is None and r.query_kind == "skip"


def test_제품명_자리에_브랜드만_있으면_뺀다():
    assert resolve({"brand": "Prada Beauty", "product_name": "Prada Beauty"}, "", D).query_kind == "skip"
    assert resolve({"brand": None, "product_name": "헤라"}, "헤라", D).query_kind == "skip"


def test_제품명_앞에_붙은_브랜드는_뗀다():
    assert resolve({"brand": "투쿨포스쿨", "product_name": "투쿨포스쿨 무드 스위치 팔레트"}, "", D).query == "투쿨포스쿨 무드 스위치 팔레트"


def test_짧은_한글_브랜드는_다른_말의_일부거나_띄어쓰기를_건너면_잡지_않는다():
    assert D.find("맥주 한잔") == []
    assert [b.ko for _, b in D.find("맥 립스틱")] == ["맥"]
    assert D.find("헤 라") == []


def test_응답_틀이_깨지면_None_이고_빈_제품명은_뺀다():
    assert parse_products({"mentions": []}) is None
    assert parse_products({"products": [{"brand": "헤라", "product_name": ""}, {"brand": None, "product_name": " 립  세럼 "},
                                        {"brand": None, "product_name": "립 세럼"}]}) == [{"brand": None, "product_name": "립 세럼"}]


class FakeLLM:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), 0

    async def chat_json(self, system, user, temperature=0.0, timeout=None):
        self.calls += 1
        return self.responses.pop(0) if self.responses else None


@pytest.mark.asyncio
async def test_틀이_깨지면_다시_묻고_세번_모두_실패하면_failed():
    llm = FakeLLM(None, {"x": 1}, None)
    out = await extract_products({"id": 1, "caption": "헤라 틴트", "username": "u"}, llm)
    assert out["failed"] and llm.calls == 3


@pytest.mark.asyncio
async def test_검색어가_하나도_없으면_매칭_대상이_아니다():
    llm = FakeLLM({"products": []})
    out = await mentions_for_post({"id": 2, "caption": "광주 맛집 추천", "username": "u"}, llm, D)
    assert out["matchable"] is False and out["mentions"] == []
    llm = FakeLLM({"products": [{"brand": "MAC", "product_name": "피지 필스 립밤"}]})
    out = await mentions_for_post({"id": 3, "caption": "MAC 피지 필스 립밤", "username": "u"}, llm, D)
    assert out["matchable"] and out["mentions"][0]["query"] == "맥 피지 필스 립밤"


# ── 뷰티 무관 게시물 거르기 (rules/beauty_filter) ─────────────────

from rules.beauty_filter import beauty_signal  # noqa: E402


def test_브랜드도_종류_말도_뷰티_해시태그도_없으면_뷰티가_아니다():
    assert not beauty_signal("광주 맛집 부탁드려요!! 애호박찌개 유명하죠", D).is_beauty
    assert not beauty_signal("", D).is_beauty


def test_신호가_하나라도_있으면_LLM_에_보낸다():
    assert beauty_signal("오늘은 헤라", D).brands == ["헤라"]
    assert beauty_signal("요즘 쓰는 쿠션", D).type_words == ["쿠션"]
    assert beauty_signal("가을 #데일리메이크업", D).beauty_tags == ["데일리메이크업"]
