"""ProductMatcher v1 — LLM 추출 검사 · DB 후보 · 판정. LLM 은 가짜로 바꿔 끼운다."""
import pytest

from prompts.product_extract import EXTRACT_SYSTEM, VERIFY_SYSTEM
from rules.product_match import (
    MATCHED,
    REVIEW,
    accept_choice,
    auto_decide,
    brand_keys,
    brand_prefixes,
    rank_candidates,
    resolve_brand,
)
from services.product_extractor import ExtractCache, extract_post, parse_extraction
from services.product_matcher_v1 import match_post

PRODUCTS = [
    {"product_id": "hera-serum", "brand": "HERA", "name": "헤라 센슈얼 틴티드 샤인 립 세럼", "category": "lip"},
    {"product_id": "hera-stick", "brand": "HERA", "name": "헤라 센슈얼 틴티드 샤인 스틱", "category": "lip"},
    {"product_id": "hera-cushion", "brand": "HERA", "name": "헤라 블랙 쿠션 파운데이션", "category": "base"},
    {"product_id": "el-dw", "brand": "ESTEE LAUDER", "name": "더블웨어 파운데이션", "category": "base"},
    {"product_id": "saem-tip", "brand": "THE SAEM", "name": "더샘 커버 퍼펙션 팁 컨실러", "category": "base"},
    {"product_id": "saem-pot", "brand": "THE SAEM", "name": "더샘 커버 퍼펙션 트리플 팟 컨실러", "category": "base"},
    {"product_id": "pp-cheek", "brand": "PERIPERA", "name": "PERIPERA 06 MORNING SUNSHINE CHEEK", "category": "lip"},
    {"product_id": "pp-tint", "brand": "PERIPERA", "name": "페리페라 무드 블러 틴트", "category": "lip"},
    {"product_id": "romand-juicy", "brand": "ROM&ND", "name": "롬앤 더 쥬시 래스팅 틴트", "category": "lip"},
    {"product_id": "romand-blur", "brand": "ROM&ND", "name": "롬앤 블러 퍼지 틴트", "category": "lip"},
    {"product_id": "clio-kill", "brand": "CLIO", "name": "클리오 킬 커버 파운웨어 쿠션 올뉴", "category": "base"},
    {"product_id": "clio-glow", "brand": "CLIO", "name": "킬 커버 하이 글로우 쿠션", "category": "base"},
    {"product_id": "laneige-matte", "brand": "LANEIGE", "name": "네오 쿠션 매트", "category": "base"},
    {"product_id": "laneige-juice", "brand": "LANEIGE", "name": "라네즈 주스팝박스 립틴트", "category": "lip"},
]
PREFIXES = brand_prefixes(PRODUCTS)
KEYS = brand_keys(PRODUCTS, PREFIXES, {"herabeauty_official": "HERA"})


def mention(brand, name, category="lip", evidence=None, mention_type="product", specificity="exact"):
    return {"brand": brand, "product_name": name, "variant": None, "category": category,
            "evidence": evidence or f"{brand or ''} {name or ''}".strip(), "mention_type": mention_type, "specificity": specificity}


class FakeLLM:
    """시스템 프롬프트로 추출 · 판정을 가른다. 응답은 큐에서 순서대로 꺼낸다."""

    def __init__(self, extract=(), verify=()):
        self.extract, self.verify = list(extract), list(verify)
        self.calls = {"extract": 0, "verify": 0}

    async def chat_json(self, system, user, temperature=0.0, timeout=None):
        kind = "extract" if system == EXTRACT_SYSTEM else "verify"
        assert system in (EXTRACT_SYSTEM, VERIFY_SYSTEM)
        self.calls[kind] += 1
        q = self.extract if kind == "extract" else self.verify
        return q.pop(0) if q else None


async def run(caption, mentions, verify=()):
    llm = FakeLLM(extract=[{"mentions": mentions}], verify=list(verify))
    out = await match_post({"id": 1, "caption": caption, "username": "u"}, PRODUCTS, PREFIXES, KEYS, llm)
    return out, llm


# ── 추출 응답 검사 ────────────────────────────────────────────

def test_원문에_없는_근거의_항목은_버린다():
    cap = "오늘 립은 롬앤 더 쥬시 래스팅 틴트 23호"
    kept, dropped = parse_extraction({"mentions": [
        mention("롬앤", "더 쥬시 래스팅 틴트", evidence="롬앤 더 쥬시 래스팅 틴트"),
        mention("롬앤", "블러 퍼지 틴트", evidence="롬앤 블러 퍼지 틴트"),  # 캡션에 없다
    ]}, cap)
    assert [m["product_name"] for m in kept] == ["더 쥬시 래스팅 틴트"]
    assert dropped[0]["why"] == "evidence 가 캡션에 없음"


def test_공백_줄바꿈_차이는_근거로_인정한다():
    kept, _ = parse_extraction({"mentions": [mention("롬앤", "쥬시래스팅", evidence="롬앤  쥬시\n래스팅")]}, "롬앤 쥬시래스팅 최애")
    assert len(kept) == 1


def test_스키마가_틀리거나_유형과_필드가_어긋나면_버린다():
    cap = "헤라 신상 립 보러 감"
    kept, dropped = parse_extraction({"mentions": [
        {"brand": "헤라", "product_name": None, "evidence": "헤라", "mention_type": "product", "specificity": "exact"},
        {"brand": "헤라", "product_name": "샤인 립", "evidence": "헤라", "mention_type": "brand_only", "specificity": "exact"},
        {"brand": "헤라", "product_name": None, "evidence": "헤라", "mention_type": "weird", "specificity": "exact"},
        {"brand": "헤라", "product_name": None, "category": None, "evidence": "헤라", "mention_type": "brand_only", "specificity": "exact"},
    ]}, cap)
    assert len(kept) == 1 and kept[0]["mention_type"] == "brand_only"
    assert len(dropped) == 3


def test_응답_틀이_깨지면_None_이다():
    assert parse_extraction(None, "x") is None
    assert parse_extraction({"items": []}, "x") is None
    assert parse_extraction(["a"], "x") is None


def test_같은_제품을_두번_뽑아도_한번만_남긴다():
    cap = "롬앤 블러 퍼지 틴트 · 롬앤 블러 퍼지 틴트 21호도"
    kept, _ = parse_extraction({"mentions": [mention("롬앤", "블러 퍼지 틴트")] * 2}, cap)
    assert len(kept) == 1


@pytest.mark.asyncio
async def test_틀이_깨지면_다시_묻고_세번_모두_실패하면_실패로_남긴다(tmp_path):
    post = {"id": 7, "caption": "롬앤 블러 퍼지 틴트", "username": "u"}
    ok = await extract_post(post, FakeLLM(extract=[None, {"mentions": [mention("롬앤", "블러 퍼지 틴트")]}]))
    assert ok["attempts"] == 2 and not ok["failed"] and len(ok["mentions"]) == 1
    bad = await extract_post(post, FakeLLM(extract=[None, None, None]))
    assert bad["failed"] and bad["attempts"] == 3 and bad["mentions"] == []


@pytest.mark.asyncio
async def test_같은_게시물_같은_프롬프트는_캐시에서_꺼낸다(tmp_path):
    cache = ExtractCache(tmp_path / "c.jsonl")
    post = {"id": 7, "caption": "롬앤 블러 퍼지 틴트", "username": "u"}
    llm = FakeLLM(extract=[{"mentions": [mention("롬앤", "블러 퍼지 틴트")]}])
    first = await extract_post(post, llm, cache)
    again = await extract_post(post, llm, ExtractCache(tmp_path / "c.jsonl"))
    assert llm.calls["extract"] == 1 and again["cached"] and again["mentions"] == first["mentions"]
    # 캡션이 바뀌면 다시 부른다
    changed = await extract_post({**post, "caption": "롬앤 블러 퍼지 틴트 재구매"}, FakeLLM(extract=[{"mentions": []}]), cache)
    assert not changed["cached"]


@pytest.mark.asyncio
async def test_실패한_추출은_캐시하지_않는다(tmp_path):
    cache = ExtractCache(tmp_path / "c.jsonl")
    await extract_post({"id": 1, "caption": "x 립", "username": "u"}, FakeLLM(extract=[None, None, None]), cache)
    assert cache.data == {}


# ── 브랜드 · 후보 ─────────────────────────────────────────────

def test_한글_영문_공식계정_표기를_브랜드로_잇는다():
    assert resolve_brand("롬앤", KEYS) == "ROM&ND"
    assert resolve_brand("rom&nd", KEYS) == "ROM&ND"
    assert resolve_brand("헤라", KEYS) == "HERA"
    assert resolve_brand("herabeauty_official", KEYS) == "HERA"
    assert resolve_brand("데코르테", KEYS) is None


def test_브랜드와_카테고리가_다른_후보는_뺀다():
    brand, cands = rank_candidates(mention("헤라", "블랙 쿠션", category="base"), PRODUCTS, PREFIXES, KEYS)
    assert brand == "HERA"
    assert {c.product_id for c in cands} == {"hera-cushion"}


def test_DB에_없는_브랜드면_후보가_없다():
    assert rank_candidates(mention("DECORTE", "젠 웨어 파운데이션", category="base"), PRODUCTS, PREFIXES, KEYS) == (None, [])


def test_범위_밖_카테고리는_후보가_없다():
    assert rank_candidates(mention("페리페라", "브이 쉐딩", category="other"), PRODUCTS, PREFIXES, KEYS)[1] == []


def test_임베딩_점수가_높은_상품을_후보에_더한다():
    _, cands = rank_candidates(mention("롬앤", "쥬시틴트"), PRODUCTS, PREFIXES, KEYS, {"romand-juicy": 0.9, "romand-blur": 0.1})
    assert "romand-juicy" in {c.product_id for c in cands}


def test_브랜드만_언급이면_제품을_확정하지_않는다():
    m = mention("PERIPERA", None, mention_type="brand_only", evidence="peripera")
    assert rank_candidates(m, PRODUCTS, PREFIXES, KEYS) == (None, [])
    assert auto_decide(m, None, [])[0] == "brand_only"


def test_판정_LLM이_후보_밖의_ID를_고르면_review다():
    _, cands = rank_candidates(mention("더샘", "커버 퍼펙션 컨실러", category="base"), PRODUCTS, PREFIXES, KEYS)
    assert accept_choice("made-up-id", cands) == (REVIEW, None)
    assert accept_choice(None, cands) == (REVIEW, None)
    # 추출명에 없는 '트리플 · 팟' 이 붙은 후보는 LLM 이 골라도 사람이 본다
    assert accept_choice("saem-pot", cands) == (REVIEW, None)
    assert accept_choice("unmatched", cands) == ("unmatched", None)


# ── 기존 오탐 4건 (v0.1 회귀) ─────────────────────────────────

@pytest.mark.asyncio
async def test_회귀1_브랜드명만_있으면_제품으로_잇지_않는다():
    out, llm = await run("오늘 립은 peripera 잉크 무드", [mention("peripera", None, mention_type="brand_only", evidence="peripera")])
    assert [r["status"] for r in out["rows"]] == ["brand_only"]
    assert llm.calls["verify"] == 0


@pytest.mark.asyncio
async def test_회귀2_다른_브랜드의_비슷한_이름에_잇지_않는다():
    cap = "📘 DECORTE - 젠 웨어 파운데이션 [N16 / 74,000]"
    out, _ = await run(cap, [mention("DECORTE", "젠 웨어 파운데이션", category="base", evidence="DECORTE - 젠 웨어 파운데이션")])
    assert out["rows"][0]["status"] == "unmatched" and out["rows"][0]["product_id"] is None


@pytest.mark.asyncio
async def test_회귀3_같은_브랜드_다른_제품은_규칙으로_확정하지_않는다():
    cap = "📗 THE SAEM - 커버 퍼펙션 컨실러 펜슬 [0.5호 / 7,000]"
    m = mention("THE SAEM", "커버 퍼펙션 컨실러 펜슬", category="base", evidence="THE SAEM - 커버 퍼펙션 컨실러 펜슬")
    out, llm = await run(cap, [m], verify=[{"choice": "unmatched", "reason": "펜슬은 후보에 없다"}])
    row = out["rows"][0]
    assert llm.calls["verify"] == 1 and row["method"] == "llm"
    assert row["status"] == "unmatched" and row["product_id"] is None


@pytest.mark.asyncio
async def test_회귀4_비슷한_라인_중_정확한_제품을_규칙으로_확정한다():
    cap = "헤라 센슈얼 틴티드 샤인 립 세럼 323 체리온탑"
    out, llm = await run(cap, [mention("헤라", "센슈얼 틴티드 샤인 립 세럼", evidence="헤라 센슈얼 틴티드 샤인 립 세럼")])
    row = out["rows"][0]
    assert row["status"] == MATCHED and row["product_id"] == "hera-serum" and row["method"] == "rule"
    assert llm.calls["verify"] == 0


@pytest.mark.asyncio
async def test_판정_LLM이_고른_후보는_확정하고_방법을_남긴다():
    cap = "롬앤 쥬시래스팅 최애"
    out, llm = await run(cap, [mention("롬앤", "쥬시래스팅", evidence="롬앤 쥬시래스팅", specificity="partial")],
                         verify=[{"choice": "romand-juicy", "reason": "줄임말"}])
    row = out["rows"][0]
    assert row["method"] == "llm" and row["status"] == MATCHED and row["product_id"] == "romand-juicy"


# ── v1 보완: 판정 LLM 억지 선택 막기 · 한글 브랜드 표기 ────────────────

def test_LLM이_고른_후보에서_종류_단어만_빠지면_인정한다():
    _, cands = rank_candidates(mention("롬앤", "쥬시래스팅"), PRODUCTS, PREFIXES, KEYS)
    assert accept_choice("romand-juicy", cands) == (MATCHED, "romand-juicy")


@pytest.mark.asyncio
async def test_마무리가_다른_제품은_LLM이_골라도_review다():
    cap = "라네즈 네오쿠션 뮤이 21N"
    out, llm = await run(cap, [mention("라네즈", "네오쿠션 뮤이", category="base", evidence="라네즈 네오쿠션 뮤이")],
                         verify=[{"choice": "laneige-matte", "reason": "같은 라인"}])
    row = out["rows"][0]
    assert llm.calls["verify"] == 1 and row["status"] == REVIEW and row["product_id"] is None


@pytest.mark.asyncio
async def test_이름이_비슷한_후보가_없으면_LLM을_부르지_않는다():
    out, llm = await run("롬앤 신상 한글날 에디션", [mention("롬앤", "한글날 에디션", evidence="롬앤 신상 한글날 에디션")])
    assert out["rows"][0]["status"] == "unmatched" and llm.calls["verify"] == 0


def test_한글_브랜드명으로_시작하는_상품이_하나뿐이어도_브랜드로_잇는다():
    from rules.product_match import weak_brand_keys
    weak = weak_brand_keys(PRODUCTS)
    assert resolve_brand("클리오", KEYS) is None          # 확인된 표기에는 없다
    assert resolve_brand("클리오", KEYS, weak) == "CLIO"  # 상품명 첫 단어로 짐작한 표기
    assert resolve_brand("라네즈", KEYS, weak) == "LANEIGE"
    assert "더블웨어" not in weak                          # 두 단어 이름의 첫 단어는 라인일 수 있다


@pytest.mark.asyncio
async def test_클리오_쿠션은_규칙으로_확정한다():
    cap = "베이스: 클리오 킬 커버 파운웨어 쿠션 21호"
    out, llm = await run(cap, [mention("클리오", "킬 커버 파운웨어 쿠션", category="base", evidence="클리오 킬 커버 파운웨어 쿠션")])
    row = out["rows"][0]
    assert row["status"] == MATCHED and row["product_id"] == "clio-kill" and row["method"] == "rule"


@pytest.mark.asyncio
async def test_브랜드_표기를_모르면_이름이_거의_같은_후보만_판정_LLM에_넘긴다():
    cap = "클리오코스메틱 킬 커버 파운웨어 쿠션 써봄"
    out, llm = await run(cap, [mention("클리오코스메틱", "킬 커버 파운웨어 쿠션", category="base", evidence="클리오코스메틱 킬 커버 파운웨어 쿠션")],
                         verify=[{"choice": "clio-kill", "reason": "올뉴는 버전 표기"}])
    row = out["rows"][0]
    assert row["method"] == "llm" and row["status"] == MATCHED and row["product_id"] == "clio-kill"
    assert {c["product_id"] for c in row["candidates"]} == {"clio-kill"}


# ── v1.1 실험: 판정 LLM 이 고른 후보의 빠진 단어 검사 완화 ────────────────
from rules.product_match import accept_choice_v1_1, verify_pool  # noqa: E402

V11_PRODUCTS = PRODUCTS + [
    {"product_id": "fwee-gloss", "brand": "FWEE", "name": "퓌 3D 볼류밍 글로스", "category": "lip"},
    {"product_id": "boj-sun", "brand": "BEAUTY OF JOSEON", "name": "[화잘먹] 조선미녀 맑은쌀 선크림 50ml+20ml 증정 기획", "category": "sun"},
    {"product_id": "boj-aqua", "brand": "BEAUTY OF JOSEON", "name": "맑은쌀선크림 아쿠아 프레쉬", "category": "sun"},
    {"product_id": "mac-air", "brand": "MAC", "name": "MAC 립글라스 에어 논-스틱 글로스 4 Colors", "category": "lip"},
    {"product_id": "lf-01", "brand": "LOVEFLEUR", "name": "러브플레르 에버라스팅 립라이너 01 누디버터", "category": "lip"},
    {"product_id": "lf-03", "brand": "LOVEFLEUR", "name": "러브플레르 에버라스팅 립라이너 03 실루엣", "category": "lip"},
]
V11_PREFIXES = brand_prefixes(V11_PRODUCTS)
V11_KEYS = brand_keys(V11_PRODUCTS, V11_PREFIXES)
V11_ALIASES = {"FWEE": {"퓌"}, "BEAUTY OF JOSEON": {"조선미녀"}}


def v11(m, choice):
    _, cands = rank_candidates(m, V11_PRODUCTS, V11_PREFIXES, V11_KEYS)
    return accept_choice_v1_1(choice, verify_pool(cands), m, V11_ALIASES)[:2]


def test_v11_한글_브랜드_표기만_빠지면_인정한다():
    assert v11(mention("fwee", "볼류밍 글로스"), "fwee-gloss") == (MATCHED, "fwee-gloss")
    assert v11(mention("BEAUTY OF JOSEON", "맑은쌀선크림", category="sun"), "boj-sun") == (MATCHED, "boj-sun")


def test_v11_하이픈으로_붙은_말은_한_단어로_본다():
    # "논-스틱" 이 "논 / 스틱" 으로 쪼개지면 "스틱"(마무리 말)이 빠진 것처럼 보인다
    assert v11(mention("MAC", "립글라스 에어"), "mac-air") == (MATCHED, "mac-air")


def test_v11_호수만_다른_후보는_원문의_호수로_가른다():
    m = mention("러브플레르", "립라이너", evidence="[러브플레르] 립라이너 누디버터 컬러")
    assert v11(m, "lf-01") == (MATCHED, "lf-01")
    assert v11(m, "lf-03")[0] == REVIEW        # 원문은 누디버터인데 실루엣을 골랐다
    assert v11(mention("러브플레르", "립라이너", evidence="러브플레르 립라이너"), "lf-01")[0] == REVIEW


def test_v11_마무리가_다른_제품은_여전히_review다():
    assert v11(mention("라네즈", "네오쿠션 뮤이", category="base", evidence="라네즈 네오쿠션 뮤이"), "laneige-matte")[0] == REVIEW
    assert v11(mention("라네즈", "네오 쿠션", category="base", evidence="라네즈 네오 쿠션"), "laneige-matte")[0] == REVIEW  # 매트


def test_v11_다른_후보와_가르는_말이_빠지면_review다():
    # 맑은쌀선크림 원본과 아쿠아 프레쉬: 추출명에 없는 "아쿠아 프레쉬" 를 고르면 막는다
    assert v11(mention("BEAUTY OF JOSEON", "맑은쌀선크림", category="sun"), "boj-aqua")[0] == REVIEW
    # 컨실러 펜슬을 팁 · 트리플 팟 컨실러로 고르면 막는다 (회귀3)
    m = mention("THE SAEM", "커버 퍼펙션 컨실러 펜슬", category="base", evidence="THE SAEM - 커버 퍼펙션 컨실러 펜슬")
    assert v11(m, "saem-tip")[0] == REVIEW
    assert v11(m, "saem-pot")[0] == REVIEW


@pytest.mark.asyncio
async def test_v11_기존_오탐_4건은_그대로다():
    out, _ = await run("오늘 립은 peripera 잉크 무드", [mention("peripera", None, mention_type="brand_only", evidence="peripera")])
    assert out["rows"][0]["status"] == "brand_only" and out["rows"][0]["v1_1"] is None
    out, _ = await run("📘 DECORTE - 젠 웨어 파운데이션", [mention("DECORTE", "젠 웨어 파운데이션", category="base", evidence="DECORTE - 젠 웨어 파운데이션")])
    assert out["rows"][0]["status"] == "unmatched" and out["rows"][0]["v1_1"] is None
    cap = "📗 THE SAEM - 커버 퍼펙션 컨실러 펜슬 [0.5호 / 7,000]"
    m = mention("THE SAEM", "커버 퍼펙션 컨실러 펜슬", category="base", evidence="THE SAEM - 커버 퍼펙션 컨실러 펜슬")
    for wrong in ("saem-tip", "saem-pot"):   # LLM 이 틀리게 골라도 v1.1 은 막는다
        out, _ = await run(cap, [m], verify=[{"choice": wrong, "reason": "비슷함"}])
        assert out["rows"][0]["v1_1"]["status"] == REVIEW and out["rows"][0]["v1_1"]["product_id"] is None
    out, _ = await run("헤라 센슈얼 틴티드 샤인 립 세럼 323 체리온탑", [mention("헤라", "센슈얼 틴티드 샤인 립 세럼", evidence="헤라 센슈얼 틴티드 샤인 립 세럼")])
    assert out["rows"][0]["product_id"] == "hera-serum" and out["rows"][0]["method"] == "rule"


@pytest.mark.asyncio
async def test_v11_뮤이를_매트로_골라도_review다():
    out, _ = await run("라네즈 네오쿠션 뮤이 21N", [mention("라네즈", "네오쿠션 뮤이", category="base", evidence="라네즈 네오쿠션 뮤이")],
                       verify=[{"choice": "laneige-matte", "reason": "같은 라인"}])
    row = out["rows"][0]
    assert row["status"] == REVIEW and row["llm_choice"] == "laneige-matte"
    assert row["v1_1"]["status"] == REVIEW


def test_v12_호수_꼬리를_뗀_짧은_이름이_언급에_들어_있어도_같은_제품이_아니다():
    from rules.product_match import score_name_v12
    p = {"product_id": "x", "brand": "ES NATURE", "name": "에스네이처 아쿠아 365 유브이 선크림 [SPF50+/PA++++]", "category": "skincare"}
    s, _, _ = score_name_v12("아쿠아 오아시스 블루 카밍 앰플", p, {"ES NATURE": {"에스네이처"}})
    assert s < 90
    q = {"product_id": "y", "brand": "SENSEL", "name": "센슬 퀵틴트", "category": "lip"}
    assert score_name_v12("퀵 틴트 샌디아워", q, {"SENSEL": {"센슬"}})[0] == 100
