"""Retrieve 노드가 지켜야 할 성질.

경로마다 찾는 방법이 다르다. 잘못 고르면 예산 세트의 칸이 비거나, 조건 수정이
이전 결과와 이어지지 않는다.
"""
import sys
import types

import pytest

from graph.nodes import retrieve as 노드
from services import product_meta, search_text


@pytest.fixture
def 대역(monkeypatch):
    """임베딩, 상품 검색, 상품 정보를 가짜로 둔다.

    임베딩은 문장을 그대로 담은 벡터처럼 다룬다. 상품 검색은 (문장, 카테고리)마다
    정해 둔 결과를 돌려준다.
    """
    def 세우기(검색표: dict | None = None, 메타: dict | None = None, 맥락_벡터=None):
        기록: dict = {"임베딩": [], "검색": [], "맥락": []}
        검색표 = 검색표 or {}
        메타 = 메타 or {}

        async def embed(text):
            기록["임베딩"].append(text)
            return [text]

        async def query_vector(spec, raw_query, *, user_id, extra_conditions=()):
            문장 = search_text.build(spec, raw_query, extra_conditions)
            기록["맥락"].append((문장, user_id))
            return 문장, (맥락_벡터 if 맥락_벡터 is not None else ([문장] if 문장 else None))

        def match_products(vec, category, count, exclude_ids=None):
            기록["검색"].append((vec[0], category, count))
            return 검색표.get((vec[0], category), [])

        async def ensure(있던, ids):
            return {**있던, **{pid: 메타[pid] for pid in ids if pid in 메타}}

        monkeypatch.setattr(search_text, "embed", embed)
        monkeypatch.setattr(search_text, "query_vector", query_vector)
        monkeypatch.setattr(product_meta, "ensure", ensure)
        모듈 = types.SimpleNamespace(match_products=match_products)
        import db
        monkeypatch.setitem(sys.modules, "db.vector_search", 모듈)
        monkeypatch.setattr(db, "vector_search", 모듈, raising=False)
        return 기록

    return 세우기


def _찾은(*쌍):
    return [{"product_id": pid, "similarity": s} for pid, s in 쌍]


def _메타(*ids, **값):
    return {pid: {"name": pid, "price": 20000, "feature_json": {}, **값} for pid in ids}


@pytest.mark.asyncio
async def test_기본은_질의_문장으로_찾는다(대역):
    기록 = 대역({("쿠션", "base"): _찾은(("p1", 0.9), ("p2", 0.8))}, _메타("p1", "p2"))
    나옴 = await 노드.retrieve({
        "scenario": "S2_SEARCH", "raw_query": "쿠션", "user_id": "u1",
        "query_spec": {"request_type": "SEARCH", "category": "base"},
    })
    assert 기록["검색"] == [("쿠션", "base", 노드.기본_검색_수)]
    assert 나옴["candidates"] == [
        {"product_id": "p1", "source": "retrieve", "similarity": 0.9},
        {"product_id": "p2", "source": "retrieve", "similarity": 0.8},
    ]
    assert set(나옴["product_meta"]) == {"p1", "p2"}
    assert 나옴["intent_vector"] == ["쿠션"]


@pytest.mark.asyncio
async def test_찾은_후보에_예산_필터를_건다(대역):
    대역({("쿠션", None): _찾은(("p1", 0.9), ("p2", 0.8))},
         {**_메타("p1", price=40000), **_메타("p2", price=20000)})
    나옴 = await 노드.retrieve({
        "scenario": "S2_SEARCH", "raw_query": "쿠션",
        "query_spec": {"request_type": "SEARCH", "budget": {"max": 30000}},
    })
    assert [c["product_id"] for c in 나옴["candidates"]] == ["p2"]


@pytest.mark.asyncio
async def test_검색할_말이_없으면_후보_없이_넘긴다(대역):
    기록 = 대역()
    나옴 = await 노드.retrieve({"scenario": "S2_SEARCH", "raw_query": ""})
    assert 나옴 == {"candidates": [], "intent_vector": None}
    assert 기록["검색"] == []


@pytest.mark.asyncio
async def test_환경_요청이면_필요한_기능을_검색_문장에_더한다(대역):
    기록 = 대역()
    await 노드.retrieve({
        "scenario": "S2_SEARCH", "raw_query": "선크림",
        "query_spec": {"request_type": "SEARCH", "use_env": True},
        "env_summary": {"needs": [{"key": "UV_PROTECT", "conditions": ["자외선 차단"]}]},
    })
    assert 기록["맥락"][0][0] == "선크림 자외선 차단"


@pytest.mark.asyncio
async def test_환경을_쓰지_않는_요청이면_환경_조건을_더하지_않는다(대역):
    기록 = 대역()
    await 노드.retrieve({
        "scenario": "S2_SEARCH", "raw_query": "선크림",
        "query_spec": {"request_type": "SEARCH"},
        "env_summary": {"needs": [{"key": "UV_PROTECT", "conditions": ["자외선 차단"]}]},
    })
    assert 기록["맥락"][0][0] == "선크림"


@pytest.mark.asyncio
async def test_조건_수정_재정렬은_새로_찾지_않고_이전_후보를_거른다(대역):
    기록 = 대역(메타={**_메타("p1", price=40000), **_메타("p2")})
    나옴 = await 노드.retrieve({
        "scenario": "S7_REFINE", "refine_mode": "RERANK", "raw_query": "더 저렴한 걸로",
        "query_spec": {"request_type": "REFINE", "budget": {"max": 30000}},
        "candidates": [{"product_id": "p1", "source": "retrieve", "similarity": 0.9},
                       {"product_id": "p2", "source": "retrieve", "similarity": 0.8}],
    })
    assert 기록["검색"] == []
    assert 나옴["candidates"] == [{"product_id": "p2", "source": "rerank", "similarity": 0.8}]
    assert 나옴["intent_vector"] == ["더 저렴한 걸로"]


@pytest.mark.asyncio
async def test_조건_수정이어도_다시_찾기면_새로_찾는다(대역):
    기록 = 대역()
    await 노드.retrieve({
        "scenario": "S7_REFINE", "refine_mode": "RESEARCH", "raw_query": "무향 쿠션",
        "query_spec": {"request_type": "REFINE"},
        "candidates": [{"product_id": "p1", "source": "retrieve", "similarity": 0.9}],
    })
    assert len(기록["검색"]) == 1


@pytest.mark.asyncio
async def test_예산_세트는_칸마다_찾고_칸을_표시한다(대역):
    기록 = 대역({
        ("토너 토너", "skincare"): _찾은(("t1", 0.9), ("t2", 0.8)),
        ("크림 크림", "skincare"): _찾은(("c1", 0.7), ("t1", 0.6)),
    }, {**_메타("t1", "t2", feature_json={"product_type": "토너"}),
        **_메타("c1", feature_json={"product_type": "크림"})})
    나옴 = await 노드.retrieve({
        "scenario": "S6_BUNDLE", "raw_query": "10만원으로 스킨케어 세트",
        "query_spec": {"request_type": "BUNDLE", "budget": {"total": 100000}},
        "budget_plan": [
            {"slot_key": "toner", "label": "토너", "category": "skincare",
             "product_type": "토너", "amount": 30000},
            {"slot_key": "cream", "label": "크림", "category": "skincare",
             "product_type": "크림", "amount": 50000},
        ],
    })
    assert [c[2] for c in 기록["검색"]] == [노드.칸_검색_수, 노드.칸_검색_수]
    # 크림 칸에 걸린 토너(t1)는 칸의 제품 종류가 달라 빠진다
    assert [(c["product_id"], c["slot_key"]) for c in 나옴["candidates"]] == [
        ("t1", "toner"), ("t2", "toner"), ("c1", "cream")]
    assert 나옴["intent_vector"] == ["10만원으로 스킨케어 세트"]


@pytest.mark.asyncio
async def test_홈은_덮이지_않은_기능마다_찾는다(대역):
    기록 = 대역({
        ("선크림 제품", "sun"): _찾은(("s1", 0.9)),
    }, _메타("s1"))
    필요 = [
        {"key": "UV_PROTECT", "label": "자외선 차단", "category": "sun",
         "features": {}, "conditions": ["선크림 제품"]},
        {"key": "HYDRATION", "label": "보습", "category": "skincare",
         "features": {}, "conditions": ["보습 크림"]},
    ]
    나옴 = await 노드.retrieve({
        "scenario": "HOME_ENV", "user_id": "u1",
        "env_summary": {"needs": 필요},
        "env_conditions": [{"key": "UV_PROTECT", "covered": False},
                           {"key": "HYDRATION", "covered": True}],
    })
    assert 기록["검색"] == [("선크림 제품", "sun", 노드.홈_검색_수)]
    assert 나옴["candidates"] == [{"product_id": "s1", "source": "env:UV_PROTECT", "similarity": 0.9}]
    assert 나옴["intent_vector"] == ["자외선 차단"]


@pytest.mark.asyncio
async def test_홈에서_모두_덮였으면_빈_후보다(대역):
    기록 = 대역()
    나옴 = await 노드.retrieve({
        "scenario": "HOME_ENV",
        "env_summary": {"needs": [{"key": "UV_PROTECT", "conditions": ["선크림"]}]},
        "env_conditions": [{"key": "UV_PROTECT", "covered": True}],
    })
    assert 나옴 == {"candidates": [], "intent_vector": None}
    assert 기록["검색"] == []


@pytest.fixture
def 성분_부품(monkeypatch):
    async def load_product_ingredients(ids):
        return {"p1": ["레티놀"], "p2": []}

    import services
    모듈 = types.SimpleNamespace(load_product_ingredients=load_product_ingredients)
    monkeypatch.setitem(sys.modules, "services.ingredient_store", 모듈)
    monkeypatch.setattr(services, "ingredient_store", 모듈, raising=False)


@pytest.mark.asyncio
async def test_제외_성분이_든_후보를_뺀다(대역, 성분_부품):
    대역({("쿠션", None): _찾은(("p1", 0.9), ("p2", 0.8))}, _메타("p1", "p2"))
    나옴 = await 노드.retrieve({
        "scenario": "S2_SEARCH", "raw_query": "쿠션",
        "query_spec": {"request_type": "SEARCH", "exclude_ingredients": ["레티놀"]},
    })
    assert [c["product_id"] for c in 나옴["candidates"]] == ["p2"]


@pytest.mark.asyncio
async def test_성분_부품이_없으면_제외_성분은_건너뛴다(대역, monkeypatch):
    monkeypatch.setitem(sys.modules, "services.ingredient_store", None)
    대역({("쿠션", None): _찾은(("p1", 0.9))}, _메타("p1"))
    나옴 = await 노드.retrieve({
        "scenario": "S2_SEARCH", "raw_query": "쿠션",
        "query_spec": {"request_type": "SEARCH", "exclude_ingredients": ["레티놀"]},
    })
    assert [c["product_id"] for c in 나옴["candidates"]] == ["p1"]
