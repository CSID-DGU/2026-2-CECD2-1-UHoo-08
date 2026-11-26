"""후보 검색 실험판(rules/candidate_search) · 실험 매처(services/product_matcher_exp). LLM 은 가짜로 바꿔 끼운다."""
import pytest

from rules.candidate_search import SearchConfig, V12, search_candidates, verify_pool_exp
from rules.product_match import MATCHED, REVIEW, brand_keys, brand_prefixes, rank_candidates_v12
from services.product_matcher_exp import match_post_exp

PRODUCTS = [
    {"product_id": "hera-serum", "brand": "HERA", "name": "헤라 센슈얼 틴티드 샤인 립 세럼", "category": "lip"},
    {"product_id": "hera-stick", "brand": "HERA", "name": "헤라 센슈얼 틴티드 샤인 스틱", "category": "lip"},
    {"product_id": "hera-cushion", "brand": "HERA", "name": "헤라 블랙 쿠션 파운데이션", "category": "base"},
    {"product_id": "saem-tip", "brand": "THE SAEM", "name": "더샘 커버 퍼펙션 팁 컨실러", "category": "base"},
    {"product_id": "saem-pot", "brand": "THE SAEM", "name": "더샘 커버 퍼펙션 트리플 팟 컨실러", "category": "base"},
    {"product_id": "esn-serum", "brand": "ES NATURE", "name": "에스네이처 딥 아쿠아 스쿠알란 베리어 세럼 50ml", "category": "skincare"},
    {"product_id": "esn-cream", "brand": "ES NATURE", "name": "에스네이처 아쿠아 스쿠알란 수분크림", "category": "skincare"},
    {"product_id": "esn-toner", "brand": "ES NATURE", "name": "에스네이처 아쿠아 오아시스 토너", "category": "skincare"},
    {"product_id": "laneige-mist", "brand": "LANEIGE", "name": "라네즈 크림 스킨 미스트", "category": "skincare"},
    {"product_id": "romand-juicy", "brand": "ROM&ND", "name": "롬앤 더 쥬시 래스팅 틴트", "category": "lip"},
    {"product_id": "romand-blur", "brand": "ROM&ND", "name": "롬앤 블러 퍼지 틴트", "category": "lip"},
]
PREFIXES = brand_prefixes(PRODUCTS)
KEYS = brand_keys(PRODUCTS, PREFIXES)


def mention(brand, name, category="lip", evidence=None, mention_type="product"):
    return {"brand": brand, "product_name": name, "variant": None, "category": category,
            "evidence": evidence or f"{brand or ''} {name or ''}".strip(), "mention_type": mention_type, "specificity": "exact"}


def ids(cands):
    return [c.product_id for c in cands]


# ── 기준선 보존 ───────────────────────────────────────────────

@pytest.mark.parametrize("m", [
    mention("헤라", "센슈얼 틴티드 샤인 립 세럼"),
    mention("에스네이처", "장벽천재세럼", category="skincare"),
    mention("라네즈", "크림 스킨 미스트", category="lip"),
    mention(None, "쥬시래스팅"),
])
def test_v12_설정은_rank_candidates_v12와_같은_후보를_낸다(m):
    emb = {"esn-serum": 0.8, "hera-stick": 0.5}
    want_brand, want = rank_candidates_v12(m, PRODUCTS, PREFIXES, KEYS, emb)
    brand, got = search_candidates(m, PRODUCTS, PREFIXES, KEYS, emb, V12)
    assert brand == want_brand and ids(got) == ids(want)


@pytest.mark.parametrize("m", [
    mention("에스네이처", "수분천재", category="other"),
    mention("모르는브랜드", "센슈얼 틴티드 샤인 립 세럼"),
])
def test_임베딩_설정도_범위_밖_언급과_모르는_브랜드는_v12와_같은_90점_바닥을_둔다(m):
    emb = {"esn-serum": 0.9, "esn-cream": 0.8, "hera-serum": 0.9}
    _, want = rank_candidates_v12(m, PRODUCTS, PREFIXES, KEYS, emb)
    _, got = search_candidates(m, PRODUCTS, PREFIXES, KEYS, emb, SearchConfig("embed", embed_k=3, embed_bypass=True))
    assert ids(got) == ids(want)


def test_브랜드만_언급이면_어느_설정이든_후보가_없다():
    for cfg in (V12, SearchConfig("soft", brand_filter="soft", category_filter="soft"), SearchConfig("all", brand_filter="brand_all")):
        assert search_candidates(mention("헤라", None, mention_type="brand_only"), PRODUCTS, PREFIXES, KEYS, {}, cfg) == (None, [])


def test_잘못된_설정은_거부한다():
    with pytest.raises(ValueError):
        SearchConfig("x", brand_filter="loose")


# ── 소프트 필터 ───────────────────────────────────────────────

def test_카테고리를_잘못_뽑아도_소프트_필터는_후보에_남긴다():
    m = mention("라네즈", "크림 스킨 미스트", category="lip")      # 추출이 카테고리를 틀림
    assert "laneige-mist" not in ids(search_candidates(m, PRODUCTS, PREFIXES, KEYS, {}, V12)[1])
    _, got = search_candidates(m, PRODUCTS, PREFIXES, KEYS, {}, SearchConfig("soft-cat", category_filter="soft"))
    c = next(c for c in got if c.product_id == "laneige-mist")
    assert not c.category_match and c.rank_score < c.name_score


def test_소프트_브랜드_필터는_다른_브랜드를_깎은_점수로_뒤에_둔다():
    m = mention("헤라", "블러 퍼지 틴트")
    _, got = search_candidates(m, PRODUCTS, PREFIXES, KEYS, {}, SearchConfig("soft-brand", brand_filter="soft", top_k=10))
    blur = next(c for c in got if c.product_id == "romand-blur")
    assert not blur.brand_match and blur.rank_score == blur.name_score - 15


# ── Top K · 브랜드 전체 · 임베딩 경로 ─────────────────────────

def test_top_k를_늘리면_후보가_늘어난다():
    m = mention(None, "틴트")
    small = search_candidates(m, PRODUCTS, PREFIXES, KEYS, {}, SearchConfig("k1", category_filter="soft", top_k=1, embed_k=0))[1]
    big = search_candidates(m, PRODUCTS, PREFIXES, KEYS, {}, SearchConfig("k20", category_filter="soft", top_k=20, embed_k=0))[1]
    assert len(small) == 1 and len(big) > 1 and ids(big)[0] == ids(small)[0]


def test_브랜드_전체는_이름_점수가_낮은_그_브랜드_상품도_후보로_둔다():
    m = mention("에스네이처", "장벽천재세럼", category="skincare")
    cfg = SearchConfig("brand-all", brand_filter="brand_all")
    _, got = search_candidates(m, PRODUCTS, PREFIXES, KEYS, {}, cfg)
    assert set(ids(got)) == {"esn-serum", "esn-cream", "esn-toner"}
    pool = verify_pool_exp(got, cfg)
    assert set(ids(pool)) == {"esn-serum", "esn-cream", "esn-toner"}
    # v1.2 는 이름 점수 60 아래를 판정 후보에서 뺀다
    _, base = search_candidates(m, PRODUCTS, PREFIXES, KEYS, {}, V12)
    assert verify_pool_exp(base, V12) == []


def test_임베딩_경로는_이름_점수_60_미만이어도_판정_후보에_남는다():
    m = mention("에스네이처", "장벽천재세럼", category="skincare")
    emb = {"esn-serum": 0.71, "esn-cream": 0.40}
    on = SearchConfig("embed-bypass", embed_k=1, embed_bypass=True)
    off = SearchConfig("embed", embed_k=1, embed_bypass=False)
    _, got = search_candidates(m, PRODUCTS, PREFIXES, KEYS, emb, on)
    serum = next(c for c in got if c.product_id == "esn-serum")
    assert "embed" in serum.via and serum.name_score < 60
    assert ids(verify_pool_exp(got, on)) == ["esn-serum"]
    assert verify_pool_exp(search_candidates(m, PRODUCTS, PREFIXES, KEYS, emb, off)[1], off) == []


# ── 실험 매처 ─────────────────────────────────────────────────

class FakeLLM:
    def __init__(self, mentions):
        self.mentions = mentions

    async def chat_json(self, system, user, temperature=0.0, timeout=None):
        return {"mentions": self.mentions}


def fake_verify(choice):
    calls = []

    async def fn(caption, m, cands):
        calls.append([c["product_id"] for c in cands])
        return {"choice": choice, "reason": "테스트"}
    return fn, calls


async def run(caption, mentions, cfg, choice=None, emb=None):
    fn, calls = fake_verify(choice)
    search = (lambda qs: [emb or {} for _ in qs]) if emb is not None else None
    out = await match_post_exp({"id": 1, "caption": caption, "username": "u"}, PRODUCTS, PREFIXES, KEYS, FakeLLM(mentions),
                               cfg, fn, embed_search=search)
    return out["rows"], calls


@pytest.mark.asyncio
async def test_실험_매처도_규칙_확정은_LLM을_부르지_않는다():
    rows, calls = await run("헤라 센슈얼 틴티드 샤인 립 세럼 323", [mention("헤라", "센슈얼 틴티드 샤인 립 세럼")], V12)
    assert rows[0]["status"] == MATCHED and rows[0]["method"] == "rule" and calls == []


@pytest.mark.asyncio
async def test_인정_규칙이_막은_답은_blocked에_남는다():
    cap = "THE SAEM 커버 퍼펙션 컨실러 펜슬"
    m = mention("THE SAEM", "커버 퍼펙션 컨실러 펜슬", category="base", evidence=cap)
    rows, calls = await run(cap, [m], V12, choice="saem-tip")
    assert calls and rows[0]["status"] == REVIEW and rows[0]["llm_choice"] == "saem-tip" and rows[0]["blocked"]


@pytest.mark.asyncio
async def test_판정_후보가_없으면_LLM을_부르지_않는다():
    rows, calls = await run("에스네이처 장벽천재세럼", [mention("에스네이처", "장벽천재세럼", category="skincare")], V12)
    assert calls == [] and rows[0]["status"] == "unmatched"


@pytest.mark.asyncio
async def test_임베딩_경로로_들어온_후보를_LLM이_고를_수_있다():
    cap = "에스네이처 장벽천재세럼"
    cfg = SearchConfig("embed-bypass", embed_k=1, embed_bypass=True)
    rows, calls = await run(cap, [mention("에스네이처", "장벽천재세럼", category="skincare", evidence=cap)], cfg,
                            choice="esn-serum", emb={"esn-serum": 0.71})
    assert calls == [["esn-serum"]]
    # 추출명 단어("장벽천재세럼")가 후보 이름에 없어 v1.2 인정 규칙은 막는다. 막힌 것으로 남아야 한다
    assert rows[0]["status"] == REVIEW and rows[0]["blocked"]
