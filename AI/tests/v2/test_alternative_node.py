"""Alternative 노드가 지켜야 할 성질.

대체 후보에 보유 제품이나 함께 쓰면 안 되는 제품이 나오면 추천이 틀린다.
거르는 규칙은 PreFilter 와 같아야 한다.
"""
import sys
import types

import pytest

from graph.nodes import alternative as 노드
from services import product_meta
from tests.v2.test_prefilter_node import _보유, 부품_없음, 성분_부품  # noqa: F401

_기준 = "b1"


@pytest.fixture
def 대역(monkeypatch):
    def 세우기(찾은=("o1", "p1", "p2", "p3"), 메타_없는=()):
        기록: dict = {"검색": []}

        def match_alternatives(base_id, count, exclude_ids):
            기록["검색"].append((base_id, count, exclude_ids))
            return [{"product_id": pid, "similarity": 0.9 - i * 0.1} for i, pid in enumerate(찾은)]

        async def ensure(있던, ids):
            return {**있던, **{pid: {"name": f"상품{pid}"} for pid in ids if pid not in 메타_없는}}

        모듈 = types.SimpleNamespace(match_alternatives=match_alternatives)
        import db
        monkeypatch.setitem(sys.modules, "db.vector_search", 모듈)
        monkeypatch.setattr(db, "vector_search", 모듈, raising=False)
        monkeypatch.setattr(product_meta, "ensure", ensure)
        return 기록

    return 세우기


def _상태(**값):
    return {
        "scenario": "S1_EVALUATE", "base_product_id": _기준, "inventory": _보유,
        "product_meta": {_기준: {"name": "기준"}},
        "query_spec": {"request_type": "EVALUATE", "target": "SELF"},
        **값,
    }


def _ids(나옴):
    return [a["product_id"] for a in 나옴["alternatives"]]


@pytest.mark.asyncio
async def test_기준_상품을_빼고_비슷한_상품을_찾는다(대역, 성분_부품):
    기록 = 대역()
    await 노드.alternative(_상태())
    assert 기록["검색"] == [(_기준, 노드.찾을_수, [_기준])]


@pytest.mark.asyncio
async def test_보유와_함께_쓰면_안_되는_제품을_빼고_배지를_단다(대역, 성분_부품):
    대역()
    나옴 = await 노드.alternative(_상태())
    assert _ids(나옴) == ["p1", "p3"]
    assert 나옴["alternatives"][0] == {"product_id": "p1", "similarity": pytest.approx(0.8)}
    assert list(나옴["conflict_marks"]) == ["p3"]
    assert 나옴["product_meta"]["p2"]["ingredients"] == ["AHA"]


@pytest.mark.asyncio
async def test_이미_있던_충돌_표시는_남긴다(대역, 성분_부품):
    대역()
    나옴 = await 노드.alternative(_상태(conflict_marks={_기준: [{"level": "SEPARATE"}]}))
    assert set(나옴["conflict_marks"]) == {_기준, "p3"}


@pytest.mark.asyncio
async def test_다른_사람_기준이면_거르지_않는다(대역, 성분_부품):
    대역()
    나옴 = await 노드.alternative(_상태(query_spec={"request_type": "EVALUATE", "target": "OTHER"}))
    assert _ids(나옴) == ["o1", "p1", "p2", "p3"]
    assert 성분_부품["성분"] == []


@pytest.mark.asyncio
async def test_보유_제품_정보가_없으면_거르지_않는다(대역, 성분_부품):
    대역()
    나옴 = await 노드.alternative(_상태(inventory=None))
    assert _ids(나옴) == ["o1", "p1", "p2", "p3"]


@pytest.mark.asyncio
async def test_성분_부품이_없으면_보유_제품만_뺀다(대역, 부품_없음):
    대역()
    나옴 = await 노드.alternative(_상태())
    assert _ids(나옴) == ["p1", "p2", "p3"]
    assert 나옴["conflict_marks"] == {}


@pytest.mark.asyncio
async def test_상위_10개만_남기고_배지도_남긴_것에만_단다(대역, 성분_부품):
    대역(찾은=[f"x{i}" for i in range(12)] + ["p3"])
    나옴 = await 노드.alternative(_상태())
    assert len(나옴["alternatives"]) == 노드.남길_수
    assert "p3" not in 나옴["conflict_marks"]


@pytest.mark.asyncio
async def test_상품_정보가_없는_상품은_뺀다(대역, 부품_없음):
    대역(메타_없는={"p2"})
    나옴 = await 노드.alternative(_상태())
    assert _ids(나옴) == ["p1", "p3"]


@pytest.mark.asyncio
async def test_상품_평가가_아니면_아무것도_하지_않는다(대역, 성분_부품):
    기록 = 대역()
    assert await 노드.alternative(_상태(scenario="S2_SEARCH")) == {}
    assert 기록["검색"] == []
