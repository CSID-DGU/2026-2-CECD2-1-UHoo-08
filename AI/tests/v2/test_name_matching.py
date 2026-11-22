"""읽은 브랜드와 이름으로 상품 후보를 고르는 규칙이 지켜야 할 성질.

사용자가 후보 중에서 고르므로 맞는 상품이 후보에 들어야 한다. 목록에 없는 제품을
비슷한 제품으로 억지로 맞히면 다른 제품을 등록하게 된다.
"""
import pytest

from rules import name_matching
from rules.name_matching import match

# 상품 목록의 모양을 따랐다. 브랜드는 영문, 이름은 한글이고 이름 앞에 한글 브랜드가 붙은 것과
# 붙지 않은 것이 섞여 있다
_상품 = [
    {"id": "neo-mui", "brand": "LANEIGE", "name": "라네즈 네오 쿠션 뮤이"},
    {"id": "neo-glow", "brand": "LANEIGE", "name": "네오 쿠션 글로우"},
    {"id": "mist", "brand": "LANEIGE", "name": "라네즈 크림 스킨 미스트"},
    {"id": "bare", "brand": "ROM&ND", "name": "롬앤 베어 워터 쿠션(단품)"},
    {"id": "juicy", "brand": "ROM&ND", "name": "쥬시 래스팅 틴트"},
    {"id": "redsun", "brand": "DR.G", "name": "닥터지 레드 블레미쉬 수딩 업 선"},
    {"id": "reedle", "brand": "VT COSMETICS", "name": "리들샷 100 에센스"},
    {"id": "bifida", "brand": "MA:NYO", "name": "비피다 바이옴 콤플렉스 앰플"},
    {"id": "studio", "brand": "MAC", "name": "MAC 스튜디오 픽스 플루이드"},
    {"id": "liar", "brand": "LILYBYRED", "name": "쥬시 라이어 워터 틴트"},
    {"id": "naming", "brand": "", "name": "네이밍 퍼펙테일 아이 펜슬"},
    {"id": "empty", "brand": None, "name": None},
]


def _고르기(**읽은):
    return match(읽은, _상품)


def _id들(후보들):
    return [후보.product["id"] for 후보 in 후보들]


def test_브랜드와_이름이_같으면_일치도가_1이다():
    후보들 = _고르기(brand="LANEIGE", brand_ko="라네즈",
                  product_name="NEO CUSHION MUI", product_name_ko="네오 쿠션 뮤이")
    첫째 = 후보들[0]
    assert 첫째.product is _상품[0]
    assert (첫째.confidence, 첫째.name_match, 첫째.brand_match) == (1.0, 1.0, 1.0)


# ── 이름 ──────────────────────────────────────────────────────

def test_포장에_영문_이름만_있어도_한글_표기로_찾는다():
    후보들 = _고르기(brand="rom&nd", product_name="BARE WATER CUSHION", product_name_ko="베어 워터 쿠션")
    assert _id들(후보들) == ["bare"]


def test_한글_표기가_없는_영문_이름은_한글_이름과_맞지_않는다():
    assert _고르기(brand="rom&nd", product_name="BARE WATER CUSHION") == []


@pytest.mark.parametrize("읽은_이름", ["주시 라스팅 틴트", "쥬시 레스팅 틴트", "쥬시래스팅 틴트"])
def test_표기가_조금_달라도_찾는다(읽은_이름):
    후보들 = _고르기(brand="rom&nd", product_name_ko=읽은_이름)
    assert 후보들[0].product["id"] == "juicy"
    assert 후보들[0].confidence >= 0.8


def test_띄어쓰기와_기호는_견주지_않는다():
    assert _고르기(brand_ko="라네즈", product_name_ko="네오쿠션-뮤이")[0].confidence == 1.0


def test_괄호_안의_말은_빼고_견준다():
    후보 = _고르기(brand_ko="롬앤", product_name_ko="베어 워터 쿠션")[0]
    assert (후보.product["id"], 후보.confidence) == ("bare", 1.0)


@pytest.mark.parametrize("읽은_이름, 기대", [
    ("라네즈 네오 쿠션 뮤이", "neo-mui"),     # 상품 이름에도 브랜드가 붙어 있다
    ("라네즈 네오 쿠션 글로우", "neo-glow"),  # 상품 이름에는 브랜드가 없다
])
def test_이름에_브랜드를_붙여_읽어도_같은_이름이다(읽은_이름, 기대):
    후보 = _고르기(brand="LANEIGE", brand_ko="라네즈", product_name_ko=읽은_이름)[0]
    assert (후보.product["id"], 후보.confidence) == (기대, 1.0)


def test_이름을_읽지_못하면_브랜드만으로는_후보가_없다():
    assert _고르기(brand="LANEIGE", brand_ko="라네즈") == []


@pytest.mark.parametrize("읽은", [
    {},
    {"brand": None, "product_name": None, "product_name_ko": None},
    {"product_name": "", "product_name_ko": "   "},
    {"product_name": "!!! ---"},
    {"product_name": 123, "product_name_ko": ["네오 쿠션"], "brand": {"a": 1}},
])
def test_아무것도_읽지_못하면_후보가_없다(읽은):
    assert match(읽은, _상품) == []


# ── 브랜드 ────────────────────────────────────────────────────

@pytest.mark.parametrize("읽은_브랜드, 읽은_이름, 기대_id, 기대_일치", [
    ("rom&nd", "쥬시 래스팅 틴트", "juicy", 1.0),                # 대소문자, 기호
    ("Dr.G", "닥터지 레드 블레미쉬 수딩 업 선", "redsun", 1.0),
    ("VT", "리들샷 100 에센스", "reedle", 0.9),                  # 앞 단어만 적힌 로고
    ("MANYO FACTORY", "비피다 바이옴 콤플렉스 앰플", "bifida", 0.9),
    ("LANEICE", "네오 쿠션 글로우", "neo-glow", 0.8),             # 한 글자를 잘못 읽었다
])
def test_브랜드_표기가_달라도_같은_브랜드로_본다(읽은_브랜드, 읽은_이름, 기대_id, 기대_일치):
    후보 = _고르기(brand=읽은_브랜드, product_name_ko=읽은_이름)[0]
    assert (후보.product["id"], 후보.brand_match) == (기대_id, 기대_일치)


def test_다른_브랜드의_앞_글자와_같다고_같은_브랜드가_아니다():
    """MACQUEEN 은 MAC 이 아니다. 단어가 통째로 같을 때만 앞 단어로 본다."""
    후보 = _고르기(brand="MACQUEEN", product_name_ko="스튜디오 픽스 플루이드")[0]
    assert (후보.product["id"], 후보.brand_match) == ("studio", 0.0)
    assert 후보.confidence < _고르기(brand="MAC", product_name_ko="스튜디오 픽스 플루이드")[0].confidence


def test_한글로_읽은_브랜드는_이름_앞의_브랜드와_견준다():
    후보 = _고르기(brand="라네즈", product_name="네오 쿠션 뮤이")[0]
    assert (후보.product["id"], 후보.confidence, 후보.brand_match) == ("neo-mui", 1.0, 1.0)


def test_이름에_브랜드가_없는_상품도_같은_브랜드의_다른_상품으로_알아본다():
    """라네즈로 시작하는 이름이 LANEIGE 상품에 있으므로 LANEIGE 상품은 모두 라네즈다."""
    후보 = _고르기(brand="라네즈", product_name="네오 쿠션 글로우")[0]
    assert (후보.product["id"], 후보.confidence, 후보.brand_match) == ("neo-glow", 1.0, 1.0)


def test_상품에_브랜드가_비어_있어도_이름_앞의_브랜드로_맞춘다():
    후보 = _고르기(brand="NAMING", brand_ko="네이밍", product_name_ko="퍼펙테일 아이 펜슬")[0]
    assert (후보.product["id"], 후보.confidence) == ("naming", 1.0)


def test_브랜드를_읽지_못하면_이름만으로_매긴다():
    후보 = _고르기(product_name_ko="쥬시 래스팅 틴트")[0]
    assert (후보.product["id"], 후보.confidence, 후보.brand_match) == ("juicy", 1.0, None)


def test_브랜드가_다르면_이름이_같아도_일치도가_낮다():
    후보 = _고르기(brand="ETUDE", product_name_ko="쥬시 래스팅 틴트")[0]
    assert (후보.product["id"], 후보.brand_match) == ("juicy", 0.0)
    assert 후보.confidence == pytest.approx(1 - name_matching.브랜드_비중)


# ── 후보로 내지 않는 것 ───────────────────────────────────────

def test_같은_브랜드라도_이름이_다른_상품은_후보가_아니다():
    후보들 = _고르기(brand="LANEIGE", brand_ko="라네즈", product_name_ko="네오 쿠션 뮤이")
    # 이름이 비슷한 같은 브랜드 상품은 낮은 일치도로 남고, 이름이 다른 미스트는 빠진다
    assert _id들(후보들) == ["neo-mui", "neo-glow"]
    assert 후보들[1].confidence < 0.7


@pytest.mark.parametrize("읽은", [
    {"brand": "ETUDE", "brand_ko": "에뛰드", "product_name_ko": "픽싱 틴트"},               # 브랜드도 없다
    {"brand": "LANEIGE", "brand_ko": "라네즈", "product_name_ko": "워터 슬리핑 마스크"},     # 브랜드만 있다
    {"product_name_ko": "틴트"},                                                          # 종류만 읽었다
])
def test_목록에_없는_제품은_후보가_없다(읽은):
    assert match(읽은, _상품) == []


def test_후보마다_일치도가_기준_이상이고_0과_1_사이다():
    for 읽은 in (
        {"brand": "LANEIGE", "product_name_ko": "네오 쿠션"},
        {"product_name_ko": "쥬시 틴트"},
        {"brand": "ROM&ND", "brand_ko": "롬앤", "product_name_ko": "베어 워터 쿠션 리필"},
    ):
        for 후보 in match(읽은, _상품):
            assert name_matching.최소_일치도 <= 후보.confidence <= 1.0
            assert 0.0 <= 후보.name_match <= 1.0


# ── 순서와 개수 ───────────────────────────────────────────────

_크림 = [
    {"id": f"c{번호}", "brand": "AESTURA", "name": 이름}
    for 번호, 이름 in enumerate([
        "아토베리어 365 크림",
        "아토베리어 365 크림 미스트",
        "아토베리어 365 로션",
        "아토베리어 365 하이드로 크림",
        "아토베리어 365 크림 80ml 기획",
    ])
]


def test_후보는_일치도가_높은_순으로_세_개까지다():
    후보들 = match({"brand": "AESTURA", "product_name_ko": "아토베리어 365 크림"}, _크림)
    assert len(후보들) == name_matching.후보_수 == 3
    assert 후보들[0].product["id"] == "c0"
    assert [후보.confidence for 후보 in 후보들] == sorted((후보.confidence for 후보 in 후보들), reverse=True)


def test_후보_수를_정해_부를_수_있다():
    assert _id들(match({"brand": "AESTURA", "product_name_ko": "아토베리어 365 크림"}, _크림, limit=1)) == ["c0"]


def test_일치도가_같으면_덧붙은_말이_적은_이름이_먼저고_그다음은_id_순이다():
    쌍둥이 = [
        {"id": "c", "brand": "HERA", "name": "헤라 블랙 쿠션"},
        {"id": "b", "brand": "HERA", "name": "블랙 쿠션"},
        {"id": "a", "brand": "HERA", "name": "블랙 쿠션"},
    ]
    후보들 = match({"brand": "HERA", "brand_ko": "헤라", "product_name_ko": "블랙 쿠션"}, 쌍둥이)
    assert _id들(후보들) == ["a", "b", "c"]
    assert {후보.confidence for 후보 in 후보들} == {1.0}


def test_상품이_없으면_후보도_없다():
    assert match({"brand": "LANEIGE", "product_name_ko": "네오 쿠션"}, []) == []
