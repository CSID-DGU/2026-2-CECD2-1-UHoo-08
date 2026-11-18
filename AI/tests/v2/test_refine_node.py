"""조건 수정 노드가 지켜야 할 성질.

이전 질의와 이어지지 않으면 "더 저렴하게"를 눌러도 전혀 다른 결과가 나온다.
"""
import sys
import types

import pytest

from graph.nodes import refine as 노드
from services import product_meta

_후보 = [{"product_id": "p1", "source": "retrieve", "similarity": 0.9}]


@pytest.fixture
def 대역(monkeypatch):
    """job 저장소, 다시 해석, 상품 정보를 가짜로 둔다."""
    def 세우기(이전: dict | None, 선택지=(), 해석: dict | None = None, 메타: dict | None = None):
        기록: dict = {"읽기": [], "해석": []}

        async def load_job(job_id, columns="id"):
            기록["읽기"].append((job_id, columns))
            if job_id == "parent":
                return 이전
            return {"id": job_id, "refine_presets": list(선택지) or None}

        async def normalize(state):
            기록["해석"].append(state["raw_query"])
            return {"query_spec": {"request_type": "SEARCH", **(해석 or {})}}

        async def ensure(있던, ids):
            return {**있던, **{pid: (메타 or {})[pid] for pid in ids if pid in (메타 or {})}}

        저장소 = types.SimpleNamespace(load_job=load_job)
        import services
        monkeypatch.setitem(sys.modules, "services.job_store", 저장소)
        monkeypatch.setattr(services, "job_store", 저장소, raising=False)
        from graph.nodes import normalize as 해석_노드
        monkeypatch.setattr(해석_노드, "normalize", normalize)
        monkeypatch.setattr(product_meta, "ensure", ensure)
        return 기록

    return 세우기


def _이전(scenario="S2_SEARCH", 후보=_후보, **스펙):
    return {
        "id": "parent", "scenario": scenario,
        "query_spec": {"request_type": "SEARCH", "category": "base", "target": "SELF",
                       "features": {"product_type": "쿠션"}, "conditions": ["여름"], **스펙},
        "result": {"items": [{"productId": "p1", "price": 30000}]},
        "state_snapshot": {"candidates": 후보},
    }


def _상태(raw_query="더 저렴한 제품으로"):
    return {"job_id": "this", "parent_job_id": "parent", "raw_query": raw_query,
            # 관문이 문장 전체를 해석한 값. 쓰지 않는다
            "query_spec": {"request_type": "REFINE", "category": "lip"}}


@pytest.mark.asyncio
async def test_이전_질의에_선택지를_합치고_재정렬한다(대역):
    기록 = 대역(_이전(budget={"max": 30000}), 선택지=["CHEAPER"])
    나옴 = await 노드.refine(_상태())

    스펙 = 나옴["query_spec"]
    assert 스펙["request_type"] == "REFINE" and 스펙["confidence"] == 1.0
    assert 스펙["category"] == "base" and 스펙["budget"]["max"] == 24000
    assert 스펙["features"] == {"product_type": "쿠션"} and 스펙["conditions"] == ["여름"]
    assert 나옴["refine_mode"] == 노드.재정렬
    assert 나옴["candidates"] == _후보
    assert 나옴["parent_result"]["items"][0]["productId"] == "p1"
    # 선택지 문장만 있으면 다시 해석하지 않는다
    assert 기록["해석"] == []
    assert 기록["읽기"][0] == ("parent", 노드._이전_컬럼)


@pytest.mark.asyncio
async def test_직접_쓴_문장만_다시_해석해_합친다(대역):
    기록 = 대역(_이전(budget={"max": 30000}, exclude_ingredients=["알코올"]),
               선택지=["UNSCENTED"],
               해석={"category": "base", "features": {"finish": "매트"},
                     "conditions": ["여름", "가벼운"], "exclude_ingredients": ["향료"],
                     "budget": {"max": 25000}, "use_env": True, "target": "POPULAR"})
    나옴 = await 노드.refine(_상태("무향 제품으로, 가벼운 매트로"))

    assert 기록["해석"] == ["가벼운 매트로"]
    스펙 = 나옴["query_spec"]
    assert 스펙["features"] == {"product_type": "쿠션", "finish": "매트"}
    assert 스펙["conditions"] == ["여름", "무향", "가벼운"]
    assert 스펙["exclude_ingredients"] == ["알코올", "향료"]
    assert 스펙["budget"]["max"] == 25000 and 스펙["use_env"] is True
    # 추천 기준은 이전 그대로다
    assert 스펙["target"] == "SELF"
    assert 나옴["refine_mode"] == 노드.재탐색 and "candidates" not in 나옴


@pytest.mark.asyncio
async def test_제외_성분만_더하면_재정렬이다(대역):
    대역(_이전(), 해석={"exclude_ingredients": ["향료"]})
    나옴 = await 노드.refine(_상태("향료 빼고"))
    assert 나옴["refine_mode"] == 노드.재정렬


@pytest.mark.asyncio
@pytest.mark.parametrize("해석", [
    {"budget": {"max": 40000}},           # 예산을 올렸다
    {"features": {"finish": "매트"}},     # 특징을 바꿨다
    {"category": "lip"},                 # 카테고리를 바꿨다
])
async def test_예산을_낮추거나_제외_성분을_더한_것이_아니면_재탐색이다(대역, 해석):
    대역(_이전(budget={"max": 30000}), 해석=해석)
    나옴 = await 노드.refine(_상태("직접 쓴 조건"))
    assert 나옴["refine_mode"] == 노드.재탐색


@pytest.mark.asyncio
async def test_이전_후보가_없으면_재탐색이다(대역):
    대역(_이전(후보=[], budget={"max": 30000}), 선택지=["CHEAPER"])
    나옴 = await 노드.refine(_상태())
    assert 나옴["refine_mode"] == 노드.재탐색


def _평가_이전(ref="라네즈 네오쿠션", 남긴_id=None, 카드_id=None):
    """상품 이름으로 평가한 이전 job. 질의 해석에는 이름이 그대로 남는다."""
    이전 = _이전(scenario="S1_EVALUATE")
    이전["query_spec"] = {"request_type": "EVALUATE", "base_product_ref": ref, "target": "SELF"}
    이전["result"] = {"items": [{"productId": 카드_id}] if 카드_id else []}
    이전["state_snapshot"] = {"base_product_id": 남긴_id} if 남긴_id else {}
    return 이전


@pytest.fixture
def 이름_찾기(monkeypatch):
    """상품 이름 해석을 가짜로 둔다. 불린 이름을 남긴다."""
    불린: list = []

    async def resolve(ref):
        불린.append(ref)
        return "b1" if ref == "라네즈 네오쿠션" else None

    from services import product_resolver
    monkeypatch.setattr(product_resolver, "resolve", resolve)
    return 불린


_쿠션_메타 = {"b1": {"category": "base", "feature_json": {"product_type": "쿠션"}}}


@pytest.mark.asyncio
@pytest.mark.parametrize("남긴_id, 카드_id, 이름을_찾는다", [
    ("b1", None, False),   # 스냅샷에 남긴 id
    (None, "b1", False),   # 스냅샷에 남기기 전 job 은 결과 카드
    (None, None, True),    # 둘 다 없으면 이름을 다시 찾는다
])
async def test_상품_이름으로_평가한_job도_기준_상품의_종류로_검색한다(
        대역, 이름_찾기, 남긴_id, 카드_id, 이름을_찾는다):
    """이름으로 상품 정보를 찾으면 늘 비어 카테고리와 제품 종류가 빠진다."""
    대역(_평가_이전(남긴_id=남긴_id, 카드_id=카드_id), 선택지=["CHEAPER"], 메타=_쿠션_메타)
    스펙 = (await 노드.refine(_상태()))["query_spec"]
    assert 스펙["category"] == "base" and 스펙["features"] == {"product_type": "쿠션"}
    assert bool(이름_찾기) is 이름을_찾는다


@pytest.mark.asyncio
async def test_상품_평가였으면_기준_상품의_종류로_검색한다(대역):
    이전 = _이전(scenario="S1_EVALUATE")
    이전["query_spec"] = {"request_type": "EVALUATE", "base_product_ref": "b1", "target": "SELF"}
    이전["state_snapshot"] = {"base_product_id": "b1"}
    대역(이전, 선택지=["CHEAPER"],
         메타={"b1": {"category": "base", "feature_json": {"product_type": "쿠션"}}})
    나옴 = await 노드.refine(_상태())

    스펙 = 나옴["query_spec"]
    assert 스펙["category"] == "base" and 스펙["features"] == {"product_type": "쿠션"}
    assert 스펙["base_product_ref"] is None
    # 상품 평가의 후보는 기준 상품 하나라 다시 줄 세울 것이 없다
    assert 나옴["refine_mode"] == 노드.재탐색


@pytest.mark.asyncio
async def test_세트_결과는_조건_수정할_수_없다(대역):
    대역(_이전(scenario="S6_BUNDLE"))
    with pytest.raises(ValueError, match="검색 결과에서만"):
        await 노드.refine(_상태())


@pytest.mark.asyncio
async def test_이전_job이_없으면_예외다(대역):
    대역(None)
    with pytest.raises(ValueError, match="찾지 못했다"):
        await 노드.refine(_상태())


@pytest.mark.asyncio
@pytest.mark.parametrize("상품_종류, 찾을_종류", [
    ("젤크림", "크림"),
    (["밤", "오일"], "크림"),
    ("스킨", "토너"),
])
async def test_평가한_상품의_종류는_표준_이름과_묶음으로_넓혀_찾는다(대역, 상품_종류, 찾을_종류):
    """종류가 잘게 나뉘어 있어 그대로 쓰면 결과가 지나치게 좁아진다."""
    이전 = _이전(scenario="S1_EVALUATE")
    이전["query_spec"] = {"request_type": "EVALUATE", "base_product_ref": "b1", "target": "SELF"}
    이전["state_snapshot"] = {"base_product_id": "b1"}
    대역(이전, 선택지=["CHEAPER"],
         메타={"b1": {"category": "skincare", "feature_json": {"product_type": 상품_종류}}})
    스펙 = (await 노드.refine(_상태()))["query_spec"]
    assert 스펙["features"] == {"product_type": 찾을_종류}


@pytest.mark.asyncio
async def test_평가한_상품의_종류를_모르면_종류_조건을_넣지_않는다(대역):
    이전 = _이전(scenario="S1_EVALUATE")
    이전["query_spec"] = {"request_type": "EVALUATE", "base_product_ref": "b1", "target": "SELF"}
    이전["state_snapshot"] = {"base_product_id": "b1"}
    대역(이전, 선택지=["CHEAPER"],
         메타={"b1": {"category": "skincare", "feature_json": {"product_type": "핸드크림"}}})
    스펙 = (await 노드.refine(_상태()))["query_spec"]
    assert 스펙["features"] == {}
