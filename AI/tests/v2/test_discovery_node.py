"""Discovery 노드가 지켜야 할 성질.

기준 상품이 후보 하나로 남아야 평가 카드가 나온다. 과거 맥락은 본인 기준에서만 쓴다.
"""
import sys
import types

import pytest

from graph.nodes import discovery as 노드
from services import product_meta, search_text

_기준 = "b1"


@pytest.fixture
def 대역(monkeypatch):
    def 세우기(메타: dict | None = None, 벡터=..., 맥락=("쿠션을 찾아봄",)):
        기록: dict = {"임베딩": [], "맥락": [], "벡터_조회": []}
        메타 = {_기준: {"name": "글로우 쿠션", "brand": "A", "category": "base", "price": 20000}} \
            if 메타 is None else 메타

        async def ensure(있던, ids):
            return {**있던, **{pid: 메타[pid] for pid in ids if pid in 메타}}

        async def embed(text):
            기록["임베딩"].append(text)
            return [0.1]

        def get_product_meta_with_vec(pid):
            기록["벡터_조회"].append(pid)
            if 벡터 is None:
                raise ValueError("feature_vec 없음")
            return {**메타[pid], "feature_vec": [0.5]}

        def match_user_contexts(user_id, vec, category, count):
            기록["맥락"].append((user_id, vec, category, count))
            return [{"context_text": t} for t in 맥락]

        monkeypatch.setattr(product_meta, "ensure", ensure)
        monkeypatch.setattr(search_text, "embed", embed)
        import db
        for 이름, 모듈 in (
            ("product_reader", types.SimpleNamespace(get_product_meta_with_vec=get_product_meta_with_vec)),
            ("vector_search", types.SimpleNamespace(match_user_contexts=match_user_contexts)),
        ):
            monkeypatch.setitem(sys.modules, f"db.{이름}", 모듈)
            monkeypatch.setattr(db, 이름, 모듈, raising=False)
        return 기록

    return 세우기


def _상태(**더):
    return {
        "user_id": "u1", "base_product_id": _기준, "raw_query": "이 쿠션 어때?",
        "query_spec": {"request_type": "EVALUATE", "target": "SELF"},
        "user_profile": {"skin_type": "DRY", "skin_concerns": ["DEHYDRATED"]},
        **더,
    }


@pytest.mark.asyncio
async def test_기준_상품을_후보_하나로_두고_카테고리를_채운다(대역):
    대역()
    결과 = await 노드.discovery(_상태())
    assert 결과["candidates"] == [{"product_id": _기준, "source": "base", "similarity": 1.0}]
    assert 결과["query_spec"]["category"] == "base"
    assert _기준 in 결과["product_meta"]
    assert 결과["intent_vector"] == [0.1]


@pytest.mark.asyncio
async def test_질의에_카테고리가_있으면_그대로_둔다(대역):
    대역()
    결과 = await 노드.discovery(_상태(query_spec={"request_type": "EVALUATE", "category": "sun"}))
    assert 결과["query_spec"]["category"] == "sun"


@pytest.mark.asyncio
async def test_의도_문장에_프로필_맥락_기준_상품_질의를_담는다(대역):
    기록 = 대역()
    await 노드.discovery(_상태())
    문장 = 기록["임베딩"][0]
    for 조각 in ("DRY", "쿠션을 찾아봄", "글로우 쿠션", "이 쿠션 어때?"):
        assert 조각 in 문장
    # 맥락은 기준 상품의 특징 벡터로 찾는다
    assert 기록["맥락"] == [("u1", [0.5], "base", 노드.맥락_수)]


@pytest.mark.asyncio
@pytest.mark.parametrize("기준", ["OTHER", "POPULAR"])
async def test_본인_기준이_아니면_과거_맥락을_찾지_않는다(대역, 기준):
    기록 = 대역()
    await 노드.discovery(_상태(query_spec={"request_type": "EVALUATE", "target": 기준}))
    assert 기록["벡터_조회"] == [] and 기록["맥락"] == []


@pytest.mark.asyncio
async def test_특징_벡터가_없으면_맥락_없이_간다(대역):
    기록 = 대역(벡터=None)
    결과 = await 노드.discovery(_상태())
    assert 기록["맥락"] == []
    assert 결과["candidates"][0]["product_id"] == _기준


@pytest.mark.asyncio
async def test_기준_상품_id는_질의_해석에서도_읽는다(대역):
    대역()
    상태 = _상태(base_product_id=None,
                query_spec={"request_type": "EVALUATE", "base_product_ref": _기준})
    결과 = await 노드.discovery(상태)
    assert 결과["candidates"][0]["product_id"] == _기준


@pytest.mark.asyncio
async def test_기준_상품이_없으면_예외다(대역):
    대역(메타={})
    with pytest.raises(ValueError, match="찾지 못했다"):
        await 노드.discovery(_상태())
    with pytest.raises(ValueError, match="id 가 없다"):
        await 노드.discovery(_상태(base_product_id=None))
