"""홈 루틴에서 바꿀 제품을 고르고 대체 후보를 찾는 성질.

바꿀 제품을 잘못 고르면 문제없는 제품을 버리라고 권하게 된다.
대체 후보에 이미 가진 제품이 나오면 추천이 틀린다.
"""
import pytest

from graph.nodes import alternative as 노드
from tests.v2.test_alternative_node import 대역  # noqa: F401


def _쌍(a, b, level="AVOID"):
    return {"a": {"user_product_id": a, "name": f"이름{a}"},
            "b": {"user_product_id": b, "name": f"이름{b}"}, "level": level}


def _보유(upid, pid, rating=None, opened_at=None):
    return {"user_product_id": upid, "product_id": pid, "name": f"보유{upid}",
            "rating": rating, "opened_at": opened_at}


_네_개 = [_보유("u1", "p1"), _보유("u2", "p2"), _보유("u3", "p3"), _보유("u4", "p4")]


def test_함께_쓰지_않는_조합에_가장_많이_나온_제품을_고른다():
    쌍들 = [_쌍("u1", "u2"), _쌍("u2", "u3"), _쌍("u3", "u4", "SEPARATE"), _쌍("u1", "u4", "OK")]
    고른 = 노드.pick_replace_target(쌍들, _네_개)
    assert 고른 == {"user_product_id": "u2", "product_id": "p2", "name": "보유u2",
                    "reason": "함께 쓰지 않는 게 좋은 조합이 2개라 이 제품을 바꾸는 걸 권해요"}


def test_횟수가_같으면_별점이_낮은_것을_고르고_별점_문구를_쓴다():
    보유 = [_보유("u1", "p1", rating=4), _보유("u2", "p2", rating=2)]
    고른 = 노드.pick_replace_target([_쌍("u1", "u2")], 보유)
    assert 고른["user_product_id"] == "u2"
    assert 고른["reason"] == "별점이 낮은 쪽을 바꾸는 걸 먼저 권해요"


def test_별점이_없으면_3점으로_본다():
    보유 = [_보유("u1", "p1", rating=4), _보유("u2", "p2")]
    assert 노드.pick_replace_target([_쌍("u1", "u2")], 보유)["user_product_id"] == "u2"
    보유 = [_보유("u1", "p1", rating=2), _보유("u2", "p2")]
    assert 노드.pick_replace_target([_쌍("u1", "u2")], 보유)["user_product_id"] == "u1"


def test_별점도_같으면_먼저_연_것_그다음_id_순이다():
    보유 = [_보유("u1", "p1", 3, "2026-09-01"), _보유("u2", "p2", 3, "2026-03-01")]
    고른 = 노드.pick_replace_target([_쌍("u1", "u2")], 보유)
    assert 고른["user_product_id"] == "u2"
    assert 고른["reason"].startswith("함께 쓰지 않는 게 좋은 조합이 1개")
    # 연 날을 모르면 늦게 연 것으로 본다
    보유 = [_보유("u1", "p1", 3), _보유("u2", "p2", 3, "2026-03-01")]
    assert 노드.pick_replace_target([_쌍("u1", "u2")], 보유)["user_product_id"] == "u2"
    보유 = [_보유("u2", "p2", 3), _보유("u1", "p1", 3)]
    assert 노드.pick_replace_target([_쌍("u2", "u1")], 보유)["user_product_id"] == "u1"


def test_AVOID_쌍이_없으면_고르지_않는다():
    assert 노드.pick_replace_target([_쌍("u1", "u2", "SEPARATE"), _쌍("u1", "u3", "OK")], _네_개) is None
    assert 노드.pick_replace_target([], _네_개) is None


def _루틴_상태(pairs, inventory=_네_개):
    return {"scenario": "HOME_ROUTINE", "inventory": inventory, "product_meta": {},
            "routine_check": {"pairs": pairs},
            "query_spec": {"request_type": "SEARCH", "target": "SELF"}}


@pytest.mark.asyncio
async def test_바꿀_제품과_비슷한_상품을_보유_상품을_모두_빼고_찾는다(대역):
    기록 = 대역(찾은=("p3", "n1", "n2"), 메타_없는=("n2",))
    나옴 = await 노드.alternative(_루틴_상태([_쌍("u1", "u2"), _쌍("u2", "u3")]))

    assert 기록["검색"] == [("p2", 노드.루틴_찾을_수, ["p1", "p2", "p3", "p4"])]
    assert 나옴["replace_target"]["user_product_id"] == "u2"
    # 보유 상품은 검색이 빼지 못해도 여기서 빼고, 상품 정보가 없는 상품도 뺀다
    assert 나옴["candidates"] == [{"product_id": "n1", "source": "replace", "similarity": 0.8}]
    assert "alternatives" not in 나옴


@pytest.mark.asyncio
async def test_AVOID_쌍이_없으면_검색하지_않는다(대역):
    기록 = 대역()
    나옴 = await 노드.alternative(_루틴_상태([_쌍("u1", "u2", "SEPARATE")]))
    assert 나옴 == {"replace_target": None, "candidates": []}
    assert 기록["검색"] == []


@pytest.mark.asyncio
async def test_바꿀_제품의_상품을_모르면_후보_없이_넘긴다(대역, caplog):
    기록 = 대역()
    나옴 = await 노드.alternative(_루틴_상태([_쌍("x1", "x2")], inventory=[]))
    assert 나옴["replace_target"]["user_product_id"] == "x1"
    assert 나옴["replace_target"]["name"] == "이름x1"
    assert 나옴["candidates"] == [] and 기록["검색"] == []
    assert "상품 id 를 보유 제품에서 찾지 못했다" in caplog.text
