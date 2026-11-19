"""순위 변화가 지켜야 할 성질.

조건을 고친 뒤 무엇이 올라가고 새로 들어왔는지가 틀리면 사용자는 고친 조건이 반영됐는지 알 수 없다.
"""
import pytest

from graph.nodes import rerank as 노드


def _이전(*ids):
    return {"items": [{"productId": pid} for pid in ids]}


def _이번(*ids):
    return [{"product_id": pid, "total": 80, "breakdown": []} for pid in ids]


@pytest.mark.asyncio
async def test_이전_순위와_비교해_NEW_UP_DOWN_SAME을_낸다():
    나옴 = await 노드.rerank({"parent_result": _이전("a", "b", "c", "d"),
                              "scored": _이번("x", "d", "c", "a")})
    assert 나옴["rank_changes"] == {
        "x": {"change": "NEW", "rank_delta": None},
        "d": {"change": "UP", "rank_delta": 2},
        "a": {"change": "DOWN", "rank_delta": -3},
        "c": {"change": "SAME", "rank_delta": 0},
    }


@pytest.mark.asyncio
async def test_이번_상위_10개만_비교한다():
    나옴 = await 노드.rerank({"parent_result": _이전("a"),
                              "scored": _이번(*[f"p{i}" for i in range(12)])})
    assert len(나옴["rank_changes"]) == 노드.비교_수


@pytest.mark.asyncio
async def test_이전_결과가_없으면_모두_NEW다():
    나옴 = await 노드.rerank({"scored": _이번("a")})
    assert 나옴["rank_changes"] == {"a": {"change": "NEW", "rank_delta": None}}
