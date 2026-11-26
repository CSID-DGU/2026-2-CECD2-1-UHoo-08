"""캡션 → 브랜드 · 제품명 규칙 추출 (rules/mention_extract)."""
from rules.mention_extract import BrandLexicon, build_brand_lexicon, extract

LEX = build_brand_lexicon(
    [{"brand": "PERIPERA"}, {"brand": "TORRIDEN"}, {"brand": "LANEIGE"}, {"brand": "ES NATURE"}, {"brand": "MAC"},
     {"brand": "AMUSE"}, {"brand": "HERA"}],
    {"PERIPERA": {"페리페라"}, "TORRIDEN": {"토리든"}, "LANEIGE": {"라네즈"}, "ES NATURE": {"에스네이처"}, "MAC": {"맥"},
     "AMUSE": {"어뮤즈"}, "HERA": {"헤라"}},
)


def queries(caption):
    return [m.query for m in extract(caption, LEX).mentions]


def test_번호_목록의_브랜드_제품명_줄을_뽑는다():
    cap = "① 페리페라 - 무드 블러 틴트 ✅\n⑤ 토리든 -  다이브인 저분자 히알루론산 인텐시브 크림"
    assert queries(cap) == ["PERIPERA 무드 블러 틴트", "TORRIDEN 다이브인 저분자 히알루론산 인텐시브 크림"]


def test_사전에_없는_브랜드도_구분자_줄이면_뽑고_범위_밖도_남긴다():
    ex = extract("⑨ 라보에이치 - 두피강화샴푸\n⑧ 퓌 - 치크칩", LEX)
    got = {(m.brand, m.name, m.category, m.in_scope) for m in ex.mentions}
    assert ("라보에이치", "두피강화샴푸", "hair", False) in got
    assert ("퓌", "치크칩", "cheek", False) in got


def test_콜라보_표기는_앞_브랜드로_하고_쉼표로_나눈다():
    assert queries("⑥ 라네즈 X 마뗑킴 - 네오쿠션 뮤이, 에센셜 블러링 피니시 파우더") == [
        "LANEIGE 네오쿠션 뮤이", "LANEIGE 에센셜 블러링 피니시 파우더"]


def test_본문의_브랜드_바로_뒤_명사구를_뽑고_조사와_수식어에서_끊는다():
    assert queries("이번 어뮤즈 젤핏 글로스 무조건 사야해") == ["AMUSE 젤핏 글로스"]
    assert queries("진짜 촉촉한 쿠션에 300 앰플 떨어트려") == ["300 앰플"]      # "쿠션에" 에서 끊는다


def test_글에_브랜드가_하나뿐이면_해시태그_제품에_그_브랜드를_쓴다():
    ex = extract("에스네이처 신상 나왔어요\n#에스네이처 #장벽천재세럼", LEX)
    m = ex.mentions[0]
    assert (m.brand, m.name, m.brand_from) == ("ES NATURE", "장벽천재세럼", "context")


def test_추천_해시태그와_종류_말만은_제품이_아니다():
    ex = extract("#선크림추천 #립추천 #틴트", LEX)
    assert ex.mentions == [] and ex.post_kind == "beauty"


def test_뷰티와_무관한_글은_non_beauty다():
    assert extract("광주 맛집 부탁드려요!! 애호박찌개 유명하죠", LEX).post_kind == "non_beauty"
    assert extract("", LEX).post_kind == "non_beauty"


def test_두_글자_한글_브랜드는_다른_말의_일부면_잡지_않는다():
    assert extract("맥주 한잔", LEX).brands_seen == []
    assert extract("맥 립스틱 최고", LEX).brands_seen == ["MAC"]


def test_컬러_호수_목록_줄은_제품으로_뽑지_않는다():
    assert queries("12 오트 살구\n13 라일락 크림\n이번 어뮤즈 젤핏 글로스") == ["AMUSE 젤핏 글로스"]


def test_목록_줄_괄호_호수는_이름에서_뗀다():
    ex = extract("헤라 샤인 립 모음\n✅센슈얼 틴티드 샤인 립 세럼 (323 체리온탑)", LEX)
    m = next(x for x in ex.mentions if x.source == "list")
    assert (m.brand, m.name, m.category, m.variant) == ("HERA", "센슈얼 틴티드 샤인 립 세럼", "lip", "323 체리온탑")


def test_같은_입력이면_같은_결과():
    cap = "① 페리페라 - 무드 블러 틴트\n#페리페라무드블러틴트"
    assert queries(cap) == queries(cap)
    assert isinstance(LEX, BrandLexicon)
