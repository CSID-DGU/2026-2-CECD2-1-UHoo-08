"""제품 종류 목록과 비교 규칙이 지켜야 할 성질.

목록 자체가 어긋나면(동의어가 없는 종류를 가리키거나, 묶음에 다른 카테고리 종류가 섞이면)
비교가 조용히 틀린다. 그래서 목록의 짜임새부터 본다.
"""
import pytest

from rules.product_types import (
    CATEGORY_NAMES,
    CATEGORY_TYPES,
    GROUPS,
    MAX_TYPES,
    SYNONYMS,
    allowed_types,
    canonical,
    matches,
    mentioned,
    product_types,
)

_모든_종류 = {종류 for 종류들 in CATEGORY_TYPES.values() for 종류 in 종류들}


def test_카테고리_안에_같은_종류가_두_번_나오지_않는다():
    for 카테고리, 종류들 in CATEGORY_TYPES.items():
        assert len(종류들) == len(set(종류들)), 카테고리


def test_동의어는_있는_종류를_가리키고_표준_이름과_겹치지_않는다():
    for 다른_표기, 표준 in SYNONYMS.items():
        assert 표준 in _모든_종류, 다른_표기
        assert 다른_표기 not in _모든_종류, 다른_표기


def test_묶음_안의_종류는_그_카테고리의_종류다():
    for 카테고리, 묶음들 in GROUPS.items():
        for 이름, 안 in 묶음들.items():
            assert set(안) <= set(CATEGORY_TYPES[카테고리]), 이름


def test_카테고리_이름은_모든_카테고리에_있다():
    assert set(CATEGORY_NAMES) == set(CATEGORY_TYPES)


def test_톤업크림은_베이스와_스킨케어_둘_다에_있다():
    assert "톤업크림" in allowed_types("base")
    assert "톤업크림" in allowed_types("skincare")


def test_새_카테고리_eye_cheek_이_있다():
    assert "아이라이너" in allowed_types("eye")
    assert "블러셔" in allowed_types("cheek")
    assert allowed_types("blush") == ()
    assert allowed_types(None) == ()


@pytest.mark.parametrize("값, 표준", [
    ("토너", "토너"),
    ("선 크림", "선크림"),
    ("스킨", "토너"),
    ("선세럼", "선에센스"),
    ("겔 크림", "젤크림"),
    ("블러쉬", "블러셔"),
    ("비비", "비비크림"),
    ("BB크림", "비비크림"),
    ("씨씨", "씨씨크림"),
    ("CC 크림", "씨씨크림"),
    ("크림", "크림"),
    ("클렌저", "클렌저"),
])
def test_공백을_무시하고_동의어를_표준_이름으로_바꾼다(값, 표준):
    assert canonical(값) == 표준


@pytest.mark.parametrize("값", [None, "", "  ", "핸드크림", 3, ["토너"]])
def test_목록에_없거나_문자열이_아니면_None(값):
    assert canonical(값) is None


def test_카테고리를_주면_그_카테고리의_종류와_묶음만_받는다():
    assert canonical("쿠션", "skincare") is None
    assert canonical("쿠션", "base") == "쿠션"
    assert canonical("톤업크림", "base") == "톤업크림"
    assert canonical("크림", "skincare") == "크림"
    assert canonical("크림", "base") is None
    assert canonical("선크림", "sun") == "선크림"


def test_상품_종류는_하나든_목록이든_표준_목록으로_읽는다():
    assert product_types({"product_type": "스킨"}) == ["토너"]
    assert product_types({"product_type": ["립세럼", "틴트"]}) == ["립세럼", "틴트"]


def test_상품_종류에서_모르는_값은_버리고_겹치면_한_번만_최대_개수까지():
    assert product_types({"product_type": ["핸드크림", "크림", "수분크림"]}) == ["크림"]
    assert product_types({"product_type": ["토너", "패드", "미스트"]}) == ["토너", "패드"]
    assert MAX_TYPES == 2


@pytest.mark.parametrize("feature_json", [None, {}, {"product_type": None}, {"product_type": "핸드크림"}])
def test_종류를_모르면_빈_목록(feature_json):
    assert product_types(feature_json) == []


def test_상품_종류도_카테고리를_주면_그_카테고리_것만_남긴다():
    assert product_types({"product_type": ["쿠션", "토너"]}, "base") == ["쿠션"]


def test_같은_종류면_맞는다():
    assert matches("쿠션", ["쿠션"]) is True
    assert matches("쿠션", ["파운데이션"]) is False


@pytest.mark.parametrize("상품", ["크림", "젤크림", "아이크림", "톤업크림", "밤"])
def test_크림으로_찾으면_묶음_안의_종류도_맞는다(상품):
    assert matches("크림", [상품], "skincare") is True


@pytest.mark.parametrize("상품", ["선크림", "선로션", "선젤", "선밀크", "선에센스"])
def test_선크림으로_찾으면_묶음_안의_종류도_맞는다(상품):
    assert matches("선크림", [상품], "sun") is True


def test_묶음은_한쪽으로만_넓힌다():
    assert matches("젤크림", ["크림"], "skincare") is False
    assert matches("선크림", ["선스틱"], "sun") is False


def test_질의에서만_쓰는_묶음_이름도_찾을_수_있다():
    assert matches("클렌저", ["클렌징오일"], "skincare") is True
    assert matches("마스크팩", ["슬리핑팩"]) is True


def test_종류가_여러_개인_상품은_하나라도_맞으면_맞는다():
    assert matches("틴트", ["립세럼", "틴트"]) is True
    assert matches("립세럼", ["립세럼", "틴트"]) is True
    assert matches("립밤", ["립세럼", "틴트"]) is False


def test_질의_종류도_동의어를_표준_이름으로_보고_비교한다():
    assert matches("스킨", ["토너"]) is True
    assert matches("선세럼", ["선에센스"], "sun") is True


def test_상품_종류를_모르면_None():
    assert matches("쿠션", []) is None


def test_질의_종류가_목록에_없으면_글자가_같은_것만_맞는다():
    assert matches("핸드 크림", ["토너"]) is False


def test_카테고리_계약과_종류_목록의_카테고리가_같다():
    from contracts.query_spec import Category

    assert {c.value for c in Category} == set(CATEGORY_TYPES)


def test_질의_해석_프롬프트에_모든_카테고리와_종류가_들어간다():
    from prompts.query_normalize import QUERY_NORMALIZE_SYSTEM

    assert "__" not in QUERY_NORMALIZE_SYSTEM
    for 카테고리, 종류들 in CATEGORY_TYPES.items():
        줄 = next(
            줄 for 줄 in QUERY_NORMALIZE_SYSTEM.splitlines()
            if 줄.startswith(f"{카테고리}: product_type(")
        )
        for 종류 in 종류들:
            assert f"|{종류}|" in 줄.replace("(", "|").replace(")", "|"), (카테고리, 종류)
    for 묶음들 in GROUPS.values():
        for 이름 in 묶음들:
            assert 이름 in QUERY_NORMALIZE_SYSTEM


@pytest.mark.parametrize("종류, category, 넓힌", [
    ("젤크림", "skincare", "크림"),
    ("밤", None, "크림"),
    ("선로션", "sun", "선크림"),
    ("클렌징폼", "skincare", "클렌저"),
    ("크림", "skincare", "크림"),
    ("쿠션", "base", "쿠션"),
    ("톤업크림", "base", "톤업크림"),
])
def test_묶음에_든_종류는_묶음_이름으로_넓힌다(종류, category, 넓힌):
    from rules.product_types import broader

    assert broader(종류, category) == 넓힌


@pytest.mark.parametrize("종류, 문장, 있다", [
    ("크림", "더 촉촉한 걸로", False),
    ("쿠션", "쿠 션으로 바꿔줘", True),
    ("토너", "스킨으로", True),
    ("젤크림", "크림으로", True),
    ("없는종류", "없는종류로", False),
    ("크림", None, False),
])
def test_문장에_종류_이름이_있는지_본다(종류, 문장, 있다):
    assert mentioned(종류, 문장) is 있다
