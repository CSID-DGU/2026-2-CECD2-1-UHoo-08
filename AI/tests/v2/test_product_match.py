"""ProductMatcher v0 — 캡션 → 상품 문자열 유사도 매칭."""
from rules.product_match import (
    MATCHED,
    REVIEW,
    brand_prefixes,
    core_name,
    match_caption,
    search_names,
)

PRODUCTS = [
    {"product_id": "romand-juicy", "brand": "ROM&ND", "name": "롬앤 더 쥬시 래스팅 틴트"},
    {"product_id": "romand-blur", "brand": "ROM&ND", "name": "롬앤 블러 퍼지 틴트"},
    {"product_id": "fwee-gloss", "brand": "FWEE", "name": "퓌 3D 볼류밍 글로스"},
    {"product_id": "fwee-tint", "brand": "FWEE", "name": "3D 볼류밍 틴트"},
    {"product_id": "hera-black", "brand": "HERA", "name": "블랙 쿠션 파운데이션"},
    {"product_id": "hera-black-set", "brand": "HERA", "name": "블랙 쿠션 파운데이션 기획 (15g+15g)"},
    {"product_id": "hera-serum", "brand": "HERA", "name": "헤라 센슈얼 틴티드 샤인 립 세럼"},
    {"product_id": "hera-stick", "brand": "HERA", "name": "헤라 센슈얼 틴티드 샤인 스틱"},
    {"product_id": "nuse-gloss", "brand": "NUSE", "name": "누즈 리쥬 립 글로스 07 쇼콜라 티"},
]


def ids(cands, status=MATCHED):
    return {c.product_id for c in cands if c.status == status}


def test_제품명이_그대로_있으면_자동으로_잇는다():
    cands = match_caption("오늘 립은\n롬앤 더 쥬시 래스팅 틴트 23호!", PRODUCTS)
    assert ids(cands) == {"romand-juicy"}
    assert "쥬시 래스팅" in cands[0].matched_text


def test_띄어쓰기가_달라도_잇는다():
    assert ids(match_caption("롬앤 더쥬시래스팅 틴트 최애", PRODUCTS)) == {"romand-juicy"}
    # '더' 가 빠져 정확 포함은 아니어도 후보로는 잡힌다
    assert "romand-juicy" in {c.product_id for c in match_caption("롬앤 쥬시래스팅틴트 최애", PRODUCTS)}


def test_브랜드_표기를_뗀_이름으로도_찾는다():
    # 같은 브랜드 상품 둘 이상이 '롬앤' 으로 시작하므로 '롬앤' 은 브랜드 표기로 본다
    assert "롬앤" in brand_prefixes(PRODUCTS)["ROM&ND"]
    assert "더 쥬시 래스팅 틴트" in search_names(PRODUCTS[0], brand_prefixes(PRODUCTS))
    assert ids(match_caption("💄 더 쥬시 래스팅 틴트 #21 바이스베리", PRODUCTS)) == {"romand-juicy"}


def test_오타가_있으면_검토로_넘긴다():
    cands = match_caption("롬앤 더 쥬시 레스팅 틴트 발색", PRODUCTS)
    assert "romand-juicy" in {c.product_id for c in cands}
    assert all(c.status in (MATCHED, REVIEW) for c in cands)


def test_한_게시물의_여러_제품을_모두_찾는다():
    caption = "오늘 메이크업 정보\n베이스: 블랙 쿠션 파운데이션\n립: 롬앤 블러 퍼지 틴트"
    assert ids(match_caption(caption, PRODUCTS)) == {"hera-black", "romand-blur"}


def test_일반_단어만_겹치면_잇지_않는다():
    assert ids(match_caption("요즘 틴트랑 쿠션 뭐 쓰세요? 립 글로스 추천해줘요", PRODUCTS)) == set()


def test_제품_언급이_없으면_빈_목록이다():
    assert match_caption("오늘 날씨 너무 좋다 ☀️ #일상", PRODUCTS) == []
    assert match_caption("", PRODUCTS) == []


def test_단품과_기획은_같은_제품군으로_묶어_단품에_잇는다():
    cands = match_caption("헤라 블랙 쿠션 파운데이션 기획 세트 받았어요", PRODUCTS)
    matched = [c for c in cands if c.status == MATCHED]
    assert [c.product_id for c in matched] == ["hera-black"]
    assert "hera-black-set" in matched[0].family


def test_더_구체적인_이름이_이긴다():
    # '3D 볼류밍 글로스' 가 있으면 같은 자리의 '3D 볼류밍 틴트' 는 따로 잇지 않는다
    cands = match_caption("퓌 3D 볼류밍 글로스 신상", PRODUCTS)
    assert ids(cands) == {"fwee-gloss"}
    assert "fwee-tint" not in ids(cands)


def test_비슷한_라인의_다른_제품은_자동으로_잇지_않는다():
    cands = match_caption("헤라 센슈얼 틴티드 샤인 립 세럼 323 체리온탑", PRODUCTS)
    assert ids(cands) == {"hera-serum"}
    assert "hera-stick" not in ids(cands)


def test_호수_꼬리는_떼고_비교한다():
    assert core_name("누즈 리쥬 립 글로스 07 쇼콜라 티") == "누즈 리쥬 립 글로스"
    assert core_name("블랙 쿠션 파운데이션 기획 (15g+15g)") == "블랙 쿠션 파운데이션"
    assert ids(match_caption("누즈 리쥬 립 글로스 01 넛츠 바른 날", PRODUCTS)) == {"nuse-gloss"}


def test_호수를_떼고_브랜드만_남으면_떼지_않는다():
    # 'PERIPERA 06 MORNING SUNSHINE CHEEK' 이 'peripera' 한 단어로 줄어 브랜드명만으로 잇던 오류
    products = [{"product_id": "pp-cheek", "brand": "PERIPERA", "name": "PERIPERA 06 MORNING SUNSHINE CHEEK"}]
    assert core_name(products[0]["name"]) == "peripera 06 morning sunshine cheek"
    assert ids(match_caption("오늘 립은 peripera 잉크 무드", products)) == set()


def test_단어_안의_구성_표기는_떼지_않는다():
    # '더블웨어' 의 '더블' 을 기획 표기로 지워 '젠 웨어 파운데이션' 에 잇던 오류
    products = [{"product_id": "el-dw", "brand": "ESTEE LAUDER", "name": "더블웨어 파운데이션"}]
    assert core_name("더블웨어 파운데이션") == "더블웨어 파운데이션"
    assert core_name("수분크림 60ml 더블기획") == "수분크림"
    assert ids(match_caption("📘 DECORTE - 젠 웨어 파운데이션 [N16 / 74,000]", products)) == set()


def test_같은_브랜드의_비슷한_다른_제품은_검토로_넘긴다():
    products = [{"product_id": "saem-tip", "brand": "THE SAEM", "name": "더샘 커버 퍼펙션 팁 컨실러"}]
    cands = match_caption("📗 THE SAEM - 커버 퍼펙션 컨실러 펜슬 [0.5호 / 7,000]", products)
    assert ids(cands) == set()


BRANDS = ["HERA", "TORRIDEN", "FWEE", "RISKY BEAUTY", "ISNtree", "CLIO", "LANEIGE"]


def test_공식_계정명을_브랜드에_잇는다():
    from rules.product_match import brand_from_handle, find_handles
    assert find_handles("광고 herabeauty_official\n립 - riskybeauty_official / 치크- fwee_makeup") == [
        "herabeauty_official", "riskybeauty_official", "fwee_makeup"]
    assert brand_from_handle("herabeauty_official", BRANDS) == "HERA"
    assert brand_from_handle("torriden_official", BRANDS) == "TORRIDEN"
    assert brand_from_handle("riskybeauty_official", BRANDS) == "RISKY BEAUTY"
    assert brand_from_handle("isntree_kr", BRANDS) == "ISNtree"
    # 아는 브랜드가 들어 있지 않으면 잇지 않는다
    assert brand_from_handle("juvelook_skin_official", BRANDS) is None


def test_브랜드가_확인되면_자동_기준을_90으로_낮춘다():
    products = [{"product_id": "clio-kill", "brand": "CLIO", "name": "클리오 킬 커버 파운웨어 쿠션 올뉴"},
                {"product_id": "clio-glow", "brand": "CLIO", "name": "클리오 킬 커버 하이 글로우 쿠션"}]
    # '올뉴' 가 빠져 100점은 아니지만 같은 줄에 '클리오' 가 있다
    cands = match_caption("베이스: 클리오 킬 커버 파운웨어 쿠션 21호", products)
    assert ids(cands) == {"clio-kill"}
    assert cands[0].brand_confirmed


def test_브랜드가_있어도_제품명_단어가_빠지면_검토다():
    # 더샘 '팁' 컨실러 ↔ 캡션의 컨실러 '펜슬'. 브랜드는 같아도 다른 제품이다
    products = [{"product_id": "saem-tip", "brand": "THE SAEM", "name": "더샘 커버 퍼펙션 팁 컨실러"},
                {"product_id": "saem-pot", "brand": "THE SAEM", "name": "더샘 커버 퍼펙션 트리플 팟 컨실러"}]
    cands = match_caption("📗 THE SAEM - 커버 퍼펙션 컨실러 펜슬 [0.5호 / 7,000]", products)
    assert ids(cands) == set()
    assert any("팁" in c.missing for c in cands if c.product_id == "saem-tip")
