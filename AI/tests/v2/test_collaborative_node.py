"""비슷한 사용자 추천 노드가 지켜야 할 성질.

같은 화면에 이미 나온 상품이나 가진 제품을 다시 권하면 안 된다. 다른 사람 기준이면
받을 사람의 피부 조건으로 찾아야 한다.
"""
import sys
import types

import pytest

from graph.nodes import collaborative as 노드
from services import product_meta


@pytest.fixture
def 대역(monkeypatch):
    """협업 추천과 상품 정보를 가짜로 둔다. 받은 인자를 남긴다."""
    def 세우기(찾을: list[tuple[str, int]], 메타: dict | None = None):
        기록: dict = {"부름": []}
        메타 = 메타 or {}

        async def run_collaborative(user_id, skin_type, personal_color, exclude_ids=None, top_k=5):
            기록["부름"].append({"user_id": user_id, "skin_type": skin_type,
                               "personal_color": personal_color,
                               "exclude_ids": exclude_ids, "top_k": top_k})
            return [types.SimpleNamespace(id=pid, satisfaction_percent=만족)
                    for pid, 만족 in 찾을][:top_k]

        async def ensure(있던, ids):
            return {**있던, **{pid: 메타[pid] for pid in ids if pid in 메타}}

        모듈 = types.SimpleNamespace(run_collaborative=run_collaborative)
        import agents
        monkeypatch.setitem(sys.modules, "agents.collaborative_agent", 모듈)
        monkeypatch.setattr(agents, "collaborative_agent", 모듈, raising=False)
        monkeypatch.setattr(product_meta, "ensure", ensure)
        return 기록

    return 세우기


def _상태(**값):
    return {"user_id": "u1", "user_profile": {"skin_type": "DRY", "personal_color": "SPRING_WARM"},
            "query_spec": {"request_type": "SEARCH", "target": "SELF"}, **값}


@pytest.mark.asyncio
async def test_비슷한_사용자가_쓰는_제품을_만족도와_함께_남긴다(대역):
    기록 = 대역([("c1", 90), ("c2", 80)], {"c1": {"name": "토너"}, "c2": {"name": "크림"}})
    나옴 = await 노드.collaborative(_상태())
    assert 나옴["collaborative"] == [
        {"product_id": "c1", "satisfaction_percent": 90},
        {"product_id": "c2", "satisfaction_percent": 80},
    ]
    assert set(나옴["product_meta"]) == {"c1", "c2"}
    assert 기록["부름"][0]["skin_type"] == "DRY"
    assert 기록["부름"][0]["top_k"] == 노드.보여_줄_수


@pytest.mark.asyncio
async def test_이미_화면에_나오거나_가진_제품은_뺀다(대역):
    기록 = 대역([])
    await 노드.collaborative(_상태(
        scored=[{"product_id": f"s{i}"} for i in range(12)],
        alternatives=[{"product_id": "a1"}],
        inventory=[{"user_product_id": "u", "product_id": "o1"}],
        base_product_id="b1",
    ))
    뺄 = 기록["부름"][0]["exclude_ids"]
    # 결과 카드에 보이는 상위 10개만 뺀다
    assert 뺄 == [*(f"s{i}" for i in range(10)), "a1", "o1", "b1"]


@pytest.mark.asyncio
async def test_카테고리가_있으면_넉넉히_받아_같은_카테고리만_남긴다(대역):
    찾을 = [(f"c{i}", 90 - i) for i in range(10)]
    메타 = {f"c{i}": {"category": "base" if i % 2 else "skincare"} for i in range(10)}
    기록 = 대역(찾을, 메타)
    나옴 = await 노드.collaborative(_상태(query_spec={"request_type": "SEARCH", "category": "base"}))
    assert 기록["부름"][0]["top_k"] == 노드.보여_줄_수 * 노드.카테고리_여유_배수
    assert [c["product_id"] for c in 나옴["collaborative"]] == ["c1", "c3", "c5", "c7", "c9"]


@pytest.mark.asyncio
async def test_전체_인기_기준이면_비운다(대역):
    기록 = 대역([("c1", 90)])
    나옴 = await 노드.collaborative(_상태(query_spec={"request_type": "SEARCH", "target": "POPULAR"}))
    assert 나옴 == {"collaborative": []}
    assert 기록["부름"] == []


@pytest.mark.asyncio
async def test_다른_사람_기준이면_받을_사람의_피부_조건으로_찾는다(대역):
    """사용자 맥락 단계가 다른 사람 기준이면 user_profile 에 받을 사람의 조건을 넣어 둔다."""
    기록 = 대역([])
    await 노드.collaborative(_상태(
        query_spec={"request_type": "SEARCH", "target": "OTHER"},
        user_profile={"skin_type": "OILY", "personal_color": "SUMMER_COOL", "relation": "엄마"},
    ))
    부름 = 기록["부름"][0]
    assert (부름["skin_type"], 부름["personal_color"]) == ("OILY", "SUMMER_COOL")
    assert 부름["user_id"] == "u1"


@pytest.mark.asyncio
async def test_찾은_것이_없으면_빈_목록이다(대역):
    대역([])
    assert await 노드.collaborative(_상태()) == {"collaborative": []}


@pytest.mark.asyncio
async def test_사용자가_없으면_찾지_않는다(대역):
    기록 = 대역([("c1", 90)])
    상태 = _상태()
    del 상태["user_id"]
    assert await 노드.collaborative(상태) == {"collaborative": []}
    assert 기록["부름"] == []
