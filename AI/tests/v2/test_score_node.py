"""Score 노드가 지켜야 할 성질.

채점은 후보 수만큼 느려지므로 위쪽 후보만 채점한다. 상품 정보가 빠진 후보 때문에
멈추지 않아야 한다.
"""
import pytest

from graph.nodes import score as score_node
from services import product_meta, scoring


@pytest.fixture
def 대역(monkeypatch):
    """상품 정보와 채점을 가짜로 둔다. 받은 인자를 남긴다."""
    기록: dict = {"ensure": [], "채점": []}

    def 세우기(메타: dict):
        async def ensure(있던, ids):
            기록["ensure"].append(list(ids))
            return {**있던, **{pid: 메타[pid] for pid in ids if pid in 메타}}

        async def score_products(상품들, ctx, prior, *, lite):
            기록["채점"].append({"상품": 상품들, "ctx": ctx, "prior": prior, "lite": lite})
            return [{"product_id": p["product_id"], "total": 50, "breakdown": []} for p in 상품들]

        monkeypatch.setattr(product_meta, "ensure", ensure)
        monkeypatch.setattr(scoring, "score_products", score_products)
        return 기록

    return 세우기


def _상태(**값):
    return {"job_id": "j1", "user_id": "u1",
            "query_spec": {"request_type": "SEARCH", "target": "POPULAR"}, **값}


@pytest.mark.asyncio
async def test_후보가_없으면_채점하지_않는다(대역):
    기록 = 대역({})
    assert await score_node.score(_상태(candidates=[])) == {"scored": []}
    assert 기록["ensure"] == [] and 기록["채점"] == []


@pytest.mark.asyncio
async def test_유사도_순_상위_후보만_채점한다(대역):
    후보 = [{"product_id": f"p{i}", "source": "vector", "similarity": i / 100} for i in range(35)]
    기록 = 대역({f"p{i}": {"name": f"상품{i}", "category": "base"} for i in range(35)})

    결과 = await score_node.score(_상태(candidates=후보))

    채점 = 기록["채점"][0]
    assert len(채점["상품"]) == score_node.채점_상한
    assert 채점["상품"][0]["product_id"] == "p34"
    assert 채점["상품"][0]["similarity"] == 0.34
    assert 채점["상품"][0]["name"] == "상품34"
    assert "p0" not in {p["product_id"] for p in 채점["상품"]}
    assert len(결과["scored"]) == score_node.채점_상한


@pytest.mark.asyncio
async def test_상품_정보가_없는_후보는_빼고_채운_정보를_남긴다(대역):
    기록 = 대역({"p2": {"name": "토너", "category": "skincare"}})
    결과 = await score_node.score(_상태(
        candidates=[{"product_id": "p1", "similarity": 0.9},
                    {"product_id": "p2", "similarity": 0.8},
                    {"product_id": "p3", "similarity": 0.7}],
        product_meta={"p1": {"name": "쿠션", "category": "base"}},
    ))
    # 이미 있던 정보도 넘기고, 빠진 것만 채운다
    assert 기록["ensure"] == [["p1", "p2", "p3"]]
    assert [p["product_id"] for p in 기록["채점"][0]["상품"]] == ["p1", "p2"]
    assert set(결과["product_meta"]) == {"p1", "p2"}


@pytest.mark.asyncio
async def test_맥락과_선호_가중치를_넘기고_full로_채점한다(대역):
    기록 = 대역({"p1": {"name": "쿠션", "category": "base"}})
    await score_node.score(_상태(
        candidates=[{"product_id": "p1", "similarity": 0.9}],
        user_profile={"skin_type": "DRY"},
        inventory=[{"product_id": "o1", "category": "base", "price": 20000}],
        intent_vector=[0.1, 0.2],
        weight_prior={"review": 0.5},
    ))
    채점 = 기록["채점"][0]
    assert 채점["lite"] is False
    assert 채점["prior"] == {"review": 0.5}
    ctx = 채점["ctx"]
    assert ctx.job_id == "j1"
    assert ctx.query_spec.target.value == "POPULAR"
    assert ctx.user_profile == {"skin_type": "DRY"}
    assert ctx.inventory[0]["price"] == 20000
    assert ctx.intent_vector == [0.1, 0.2]


@pytest.mark.asyncio
async def test_질의_벡터가_비어_있으면_없는_것으로_본다(대역):
    기록 = 대역({"p1": {"name": "쿠션", "category": "base"}})
    await score_node.score(_상태(candidates=[{"product_id": "p1"}], intent_vector=[]))
    assert 기록["채점"][0]["ctx"].intent_vector is None
